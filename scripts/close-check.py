#!/usr/bin/env python3
"""Check a mama goal is ready to close, and draft its lessons metrics line.

Usage: close-check.py <store>/<slug>
Checks evidence, step times, placeholders, Trello, metrics, patterns, profile, commits, and —
for build/fix/mixed goals — that the last bug-hunt round found 0 real bugs.
Prints each missing item, then a prefilled metrics line (fill the `?` fields from memory
of the run). Exit 0 = ready to set status done; exit 1 = something is missing.
"""
import datetime, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clock  # noqa: E402
import estimate  # noqa: E402
import fileio  # noqa: E402,F401  (UTF-8 output)

OPEN_STEP = {"todo", "running", "testing", "fixing", "blocked"}


IDLE_GAP = 120  # minutes with no log line and no user wait open: the session sat idle (overnight, away)


def _timeline(log, start=None):
    """clock.timeline, with a stand-in start day when the plan has none (the rollover rule)."""
    if start is None:
        m = re.search(r"^[EDFQ]\d+ (\d\d):(\d\d) ", log or "", re.M)
        start = datetime.datetime(2000, 1, 1, int(m.group(1)) % 24, int(m.group(2)) % 60) if m else None
    return clock.timeline(log, start)


def waiting_minutes(log, start=None):
    """Minutes not spent working: waiting for the user — a question (Q) or a stop for them
    (`E waiting`, `checkpoint`, `asked`) until their next live answer (`D … tag: user`, not one
    settled "from patterns") or `E resume` — plus any gap of over IDLE_GAP minutes between log
    lines (no agent runs that long without a log line; the session sat idle). Lines are dated by
    clock.timeline, so waits across days count in full."""
    total, since, prev = 0, None, None
    for dt, kind, _, text in _timeline(log, start):
        gap = int((dt - prev).total_seconds() // 60) if prev else 0
        prev = dt
        if since is None and gap > IDLE_GAP:
            total += gap
        if since is None and (kind == "Q" or (kind == "E" and re.match(r"(waiting|checkpoint|ask)", text)) or
                              (kind == "E" and "asked" in text)):
            since = dt
        elif since is not None and ((kind == "D" and "tag: user" in text and "from patterns" not in text) or (kind == "E" and text.startswith("resume"))):
            total += int((dt - since).total_seconds() // 60)
            since = None
    return total


def actual_minutes(log, start=None):
    """First to last log line, in minutes (multi-day aware), or None with no dated line."""
    tl = _timeline(log, start)
    return int((tl[-1][0] - tl[0][0]).total_seconds() // 60) if tl else None


ID_TOKEN = re.compile(r"(?<![\w./:#-])([SDCQFE]\d+[a-z]?)(?![\w/:-]|\.\w)")
HOST_TLD = r"(?:com|org|net|io|dev|app|ai|co|cloud|local|localhost|internal|test|lan|me|sh|xyz)"
FILE_LINE = re.compile(r"\b[\w./-]*\.[A-Za-z]\w{0,3}:\d+\b")


def goal_ids(goal):
    """The IDs this goal uses: step and criterion rows in plan.md, E/D/F/Q lines in log.md."""
    ids = set()
    for name, rx in (("plan.md", r"^\| *([SC]\d+[a-z]?) *\|"), ("log.md", r"^([EDFQ]\d+) ")):
        try:
            ids |= set(re.findall(rx, open(os.path.join(goal, name), encoding="utf-8").read(), re.M))
        except OSError:
            pass
    return ids


def overview_problems(ov, goal=None):
    """The overview is the user's window: plain words, one screen. Internal IDs are flagged only
    when this goal's plan or log has them (pass the goal dir; without it, IDs aren't checked)."""
    out = []
    body = re.sub(r"`[^`]*`|\]\([^)]*\)|\b[a-z][\w+.-]*://\S+", "", ov)
    body = re.sub(rf"\b(?:\d{{1,3}}(?:\.\d{{1,3}}){{3}}|localhost|[\w-]+(?:\.[\w-]+)*\.{HOST_TLD}):\d+\b", "", body)
    known = goal_ids(goal) if goal else set()
    ids = sorted({t for t in ID_TOKEN.findall(body) if t in known})
    if ids:
        out.append(f"overview.md shows internal IDs ({', '.join(ids[:4])}) — say it in plain words")
    if FILE_LINE.search(body):
        out.append("overview.md has file:line references — those belong in log.md")
    n = len([l for l in ov.splitlines() if l.strip()])
    if n > 60:
        out.append(f"overview.md is {n} lines — keep it to one screen (≤60), detail goes to plan/log")
    return out


def _git(goal, *args):
    try:
        r = subprocess.run(["git", "-C", goal, *args], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def commit_problems(goal, head):
    """This goal's commits — those on the branch (past origin/<base> when base differs) committed
    since the plan's `started:` — carry no attribution lines and no loop internals. Commits pushed
    before this goal began (a continued branch, or work straight on the base) are not its own."""
    base, branch = head.get("base", "").split(" ")[0], head.get("branch", "").split(" ")[0]
    if not branch or branch in ("—", "n/a"):
        return []
    rev = branch
    if base and base not in ("—", "n/a") and base != branch and _git(goal, "rev-parse", "-q", "--verify", f"origin/{base}") is not None:
        rev = f"origin/{base}..{branch}"
    start = clock.start_of("started: " + head.get("started", ""))
    since = []
    if start:
        since = [f"--since={(start - datetime.timedelta(days=1)):%Y-%m-%d %H:%M}"]  # cheap prefilter; exact below
    out = _git(goal, "log", "--format=%H%x00%ct%x00%B%x01", *since, rev)
    if out is None:
        return []
    # loop words that name files this repo tracks (mama's own repo has templates/plan.md) are its vocabulary
    tracked = (_git(goal, "ls-files", "--full-name", ":/") or "").lower()
    internal = [w for w in (r"\bmama\b", r"\bplan\.md\b") if not re.search(w, tracked)]
    pattern = "|".join([r"Co-Authored-By:", r"Generated with \[?Claude", r"\b(step|criterion) [SC]\d+\b"] + internal)
    bad = []
    for entry in out.split("\x01"):
        if entry.count("\x00") < 2:
            continue
        sha, ct, msg = entry.strip().split("\x00", 2)
        if start and int(ct) < start.timestamp():
            continue
        if re.search(pattern, msg, re.I):
            bad.append(sha[:9])
    return [f"commits carry attribution or loop internals ({', '.join(bad[:5])}) — reword before push"] if bad else []


def claimed_tokens(lessons, slug):
    """(number, k|M) from the slug's latest metrics line — a reopened goal has several, and the
    latest is the one this close writes — or None."""
    found = re.findall(rf"^- ?\d{{4}}-\d\d-\d\d {re.escape(slug)} .*?tokens est [^/|]*/ ~?([\d.]+)([kM])", lessons, re.M)
    return found[-1] if found else None


HUNT = re.compile(r"^E\d+ \S+ hunt (\d+|none)\b(.*)$", re.M)
PUSH = re.compile(r"^E\d+ \S+ push(ed)?\b", re.M)


def hunt_problems(log, head, quick):
    """Code goals close only after a bug hunt came back clean (rules/loop.md → Bug hunt): each
    round names its method (`/code-review …`); the last `E hunt <k>: … <r> real …` line has 0 real
    bugs, or the user accepted known issues after it; and the last push comes after the last hunt,
    so what was delivered was hunted.
    Quick goals need one light round; `E hunt none: <why>` when no code changed."""
    if head.get("type") not in ("build", "fix", "mixed"):
        return []
    hunts = list(HUNT.finditer(log))
    if not hunts:
        return ["no bug hunt logged — run rules/loop.md → Bug hunt and log each round as "
                "`E hunt <k>: <n> found, <r> real, <x> fixed — /code-review <level> …` "
                "(or `E hunt none: <why>` if no code changed)"]
    out = []
    rounds = [h for h in hunts if h.group(1) != "none"]
    unnamed = [h.group(1) for h in rounds if "/code-review" not in h.group(2)]
    if unnamed:
        out.append(f"hunt round {unnamed[0]} doesn't name /code-review — a test run is verify, not a hunt; run "
                   "/code-review (rules/loop.md → Bug hunt) and log `E hunt <k>: … — /code-review <level> …`")
    last = hunts[-1]
    pushes = list(PUSH.finditer(log))
    if pushes and pushes[-1].start() < last.start() and last.group(1) != "none":
        out.append("the last push came before the last hunt, so what was delivered wasn't hunted — the hunt "
                   "goes before delivery; once it's clean, push again and log `E pushed …`")
    if quick or last.group(1) == "none":
        return out
    m = re.search(r"(\d+) real", last.group(2))
    if m is None:
        return out + [f"hunt line has no real-bug count: {last.group(0)!r} — log `E hunt <k>: <n> found, <r> real, <x> fixed`"]
    if int(m.group(1)) and not re.search(r"^D\d+ \S+ .*known issues.*tag: user", log[last.end():], re.M):
        out.append(f"the last bug hunt (round {last.group(1)}) found {m.group(1)} real bug(s) — fix them and hunt "
                   "again until a round is clean, or the user accepts them (`D … known issues … (tag: user)`)")
    return out


def hunt_summary(log):
    rounds = [h for h in HUNT.finditer(log) if h.group(1) != "none"]
    real = sum(int(m.group(1)) for h in rounds for m in [re.search(r"(\d+) real", h.group(2))] if m)
    return f"hunt rounds {len(rounds)} (real bugs {real})"


def measured_spend(goal, head):
    """The goal's measured token spend. A closed goal whose cache the Stop hook already deleted
    reads the final number from the plan header instead of rebuilding the cache."""
    if head.get("status") in ("done", "aborted") and not os.path.exists(os.path.join(goal, ".spend-cache.json")):
        m = re.match(r"~(\d+)k", head.get("budget", ""))
        return int(m.group(1)) * 1000 if m else None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("mama_spend", os.path.join(os.path.dirname(os.path.abspath(__file__)), "spend.py"))
        sp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sp)
        return sp.measure(os.path.join(goal, "plan.md"))
    except Exception:
        return None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    goal = sys.argv[1].rstrip("/")
    slug, store = os.path.basename(goal), os.path.dirname(goal)
    plan = open(os.path.join(goal, "plan.md"), encoding="utf-8").read()
    log = open(os.path.join(goal, "log.md"), encoding="utf-8").read()
    head = dict(re.findall(r"(\w[\w ]*?): ([^|\n]*)", plan.split("## ")[0]))
    head = {k.strip(): v.strip() for k, v in head.items()}
    missing = []

    start = clock.start_of(plan)
    hdr, steps = estimate.table(plan, "Steps")
    si = {k: i for i, k in enumerate(hdr)}
    live = [s for s in steps if s[si["status"]] not in ("obsolete", "parked")]
    for s in live:
        if s[si["status"]] in OPEN_STEP:
            missing.append(f"step {s[0]} is still {s[si['status']]}")
        if s[si["status"]] == "done" and not (s[si["start"]] and s[si["end"]]):
            missing.append(f"step {s[0]} has no start/end time (plan-set.py ... start=now / end=now)")

    # the templates' own placeholders: `<a|b>` header fields and comments; the log's `E1 HH:MM` line
    for name, text, rx in (("plan.md", plan.split("## ")[0], r"<[a-z][^<>\n]*\|[^<>\n]*>|<YYYY-MM-DD HH:MM>|<!--"),
                           ("log.md", log, r"(?m)^<!--|^[EDFQ]\d+ HH:MM\b")):
        junk = re.findall(rx, text)
        if junk:
            missing.append(f"{name} still has template placeholders ({', '.join(sorted(set(junk))[:3])})")

    if re.search(r"budget: ~0k", plan) and re.search(r"^E\d+ \S+ (dispatch|wait)", log, re.M):
        missing.append("budget still ~0k though work ran — the Stop hook writes it; run scripts/spend.py <transcript> <plan> --write")

    chdr, crit = estimate.table(plan, "Criteria")
    ci = {k: i for i, k in enumerate(chdr)}
    for c in crit:
        if c[ci["evidence"]] in ("", "—", "-"):
            missing.append(f"criterion {c[0]} has no evidence (plan-set.py <plan> {c[0]} \"evidence=...\")")

    if head.get("trello", "none") not in ("none", "—", "") and not re.search(r"^E\d+ \d\d:\d\d trello", log, re.M):
        missing.append("Trello card linked but no `trello` log line")

    quick = head.get("mode") == "quick"
    lessons_p = os.path.join(store, "lessons.md")
    lessons = open(lessons_p, encoding="utf-8").read() if os.path.exists(lessons_p) else ""
    if not quick and not re.search(rf"^- ?\d{{4}}-\d\d-\d\d {re.escape(slug)} \S+ \| steps ", lessons, re.M):
        missing.append(f"no metrics line for {slug} in lessons.md (draft below)")

    started = head.get("started", "")
    patterns_p = os.path.expanduser("~/.claude/mama/patterns.md")
    try:
        start_ts = datetime.datetime.strptime(started, "%Y-%m-%d %H:%M").timestamp()
        if not quick and os.path.getmtime(patterns_p) < start_ts:
            missing.append("patterns.md not updated during this goal (choices, size, real time/tokens)")
    except (ValueError, OSError):
        pass

    profile_p = os.path.join(store, "profile.md")
    try:
        start_ts = datetime.datetime.strptime(started, "%Y-%m-%d %H:%M").timestamp()
        if not quick and os.path.getmtime(profile_p) < start_ts and not re.search(r"^E\d+ \S+ profile\b", log, re.M):
            missing.append("profile.md not refreshed — update facts this goal changed, or log `E profile none`")
    except (ValueError, OSError):
        pass

    ov_p = os.path.join(goal, "overview.md")
    ov = open(ov_p, encoding="utf-8").read() if os.path.exists(ov_p) else ""
    if "**Status:**" not in ov:
        missing.append("overview.md has no **Status:** line — write it from templates/overview.md")
    if not quick and "## Final report" not in ov:
        missing.append("overview.md has no ## Final report (what was done, how verified, decisions, follow-ups)")
    missing += overview_problems(ov, goal)
    missing += commit_problems(goal, head)
    missing += hunt_problems(log, head, quick)

    if not quick and not os.path.exists(profile_p):
        missing.append("no profile.md in the store — create it from templates/profile.md (research goals too)")

    measured = measured_spend(goal, head)
    ml = claimed_tokens(lessons, slug)
    if measured and ml:
        claimed = float(ml[0]) * (1000 if ml[1] == "M" else 1)
        if abs(claimed - measured / 1000) > 0.25 * (measured / 1000) + 10:
            missing.append(f"lessons metrics says ~{ml[0]}{ml[1]} tokens but measured is {round(measured / 1000)}k — use the measured number")

    total = actual_minutes(log, start)
    mins = "?m" if total is None else f"{total}m (active {total - waiting_minutes(log, start)}m)"
    rows = [(s[0], s[si["deps"]], s[si["est"]], s[si["status"]]) for s in live]
    est, est_sum = estimate.critical_path(rows), estimate.total(rows)
    att = sum(int(s[si["att"]] or 0) for s in live if s[si["att"]].isdigit())
    budget = head.get("budget", "?")
    size = budget.split("/")[-1].strip() if "/" in budget else "?"
    spent = f"{round(measured / 1000)}k" if measured else (budget.split("/")[0].strip().lstrip("~") if "/" in budget else "?")
    questions = len(re.findall(r"^Q", log, re.M))
    compactions = len(re.findall(r"^E\d+ \S+ compaction", log, re.M))
    reversed_ = len(re.findall(r"supersedes", log))
    line = (f"- {datetime.date.today()} {slug} {head.get('type', '?')} | steps {len(live)} | "
            f"time est {est}m critical path (sum {est_sum}m) / actual {mins} | tokens est {size} / ~{spent} | "
            f"questions {questions} (changed plan: ?) | fix rounds {att} | {hunt_summary(log)} | "
            f"checker findings ? | compactions {compactions} | "
            f"wrong assumptions ? | reversed decisions {reversed_}")

    for m in missing:
        print("MISSING:", m)
    print("METRICS:", line)
    print(f'LEARN: learn.py goal "<what it was> ({head.get("type", "?")}, {len(live)} steps): est {est}m critical path / {size}, actual {mins} / {spent} measured"')
    print("OK — ready to close" if not missing else f"NOT READY — {len(missing)} missing")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
