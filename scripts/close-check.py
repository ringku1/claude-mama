#!/usr/bin/env python3
"""Check a mama goal is ready to close, and draft its lessons metrics line.

Usage: close-check.py <store>/<slug>
Prints each missing item, then a prefilled metrics line (fill the `?` fields from memory
of the run). Exit 0 = ready to set status done; exit 1 = something is missing.
"""
import datetime, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402,F401  (UTF-8 output)

OPEN_STEP = {"todo", "running", "testing", "fixing", "blocked"}


def table(text, section):
    m = re.search(rf"^## {section}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return [], []
    rows = [[c.strip() for c in l.strip().strip("|").split("|")]
            for l in m.group(1).splitlines() if l.lstrip().startswith("|")]
    if len(rows) < 2:
        return [], []
    return rows[0], [r for r in rows[2:] if r and r[0]]


def minutes(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


IDLE_GAP = 120  # minutes with no log line and no user wait open: the session sat idle (overnight, away)


def waiting_minutes(log):
    """Minutes not spent working: waiting for the user — a question (Q) or a stop for them
    (`E waiting`, `checkpoint`, `asked`) until their next live answer (`D … tag: user`, not one
    settled "from patterns") or `E resume` — plus any gap of over IDLE_GAP minutes between log
    lines (no agent runs that long without a log line; the session sat idle)."""
    lines = re.findall(r"^([EDFQ])\d+ (\d\d:\d\d) (.*)$", log, re.M)
    total, since, prev = 0, None, None
    for kind, t, text in lines:
        gap = (minutes(t) - minutes(prev)) % (24 * 60) if prev else 0
        prev = t
        if since is None and gap > IDLE_GAP:
            total += gap
        if since is None and (kind == "Q" or (kind == "E" and re.match(r"(waiting|checkpoint|ask)", text)) or
                              (kind == "E" and "asked" in text)):
            since = t
        elif since is not None and ((kind == "D" and "tag: user" in text and "from patterns" not in text) or (kind == "E" and text.startswith("resume"))):
            total += (minutes(t) - minutes(since)) % (24 * 60)
            since = None
    return total


ID_RE = re.compile(r"\b[SDCQFE]\d+\b")


def overview_problems(ov):
    """The overview is the user's window: plain words, one screen."""
    out = []
    body = re.sub(r"`[^`]*`|\([^)]*\)\[|https?://\S+", "", ov)
    ids = sorted(set(ID_RE.findall(body)) - {"S3"})  # S3 the storage service is a word, not a step
    if ids:
        out.append(f"overview.md shows internal IDs ({', '.join(ids[:4])}) — say it in plain words")
    if re.search(r"\b[\w./-]+\.\w{1,4}:\d+\b", body):
        out.append("overview.md has file:line references — those belong in log.md")
    n = len([l for l in ov.splitlines() if l.strip()])
    if n > 60:
        out.append(f"overview.md is {n} lines — keep it to one screen (≤60), detail goes to plan/log")
    return out


def commit_problems(goal, head):
    """This goal's commits: no attribution lines, no loop internals."""
    base, branch = head.get("base", ""), head.get("branch", "")
    if not base or not branch or base in ("—", "n/a") or branch in ("—", "n/a") or base == branch:
        return []
    branch = branch.split()[0]
    try:
        r = subprocess.run(["git", "-C", goal, "log", "--format=%H%x00%B%x01", f"origin/{base}..{branch}"],
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    if r.returncode != 0:
        return []
    bad = []
    for entry in r.stdout.split("\x01"):
        if "\x00" not in entry:
            continue
        sha, msg = entry.strip().split("\x00", 1)
        if re.search(r"Co-Authored-By:|Generated with \[?Claude|\bmama\b|\bplan\.md\b|\b(step|criterion) [SC]\d+\b", msg, re.I):
            bad.append(sha[:9])
    return [f"commits carry attribution or loop internals ({', '.join(bad[:5])}) — reword before push"] if bad else []


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

    hdr, steps = table(plan, "Steps")
    si = {k: i for i, k in enumerate(hdr)}
    live = [s for s in steps if s[si["status"]] not in ("obsolete", "parked")]
    for s in live:
        if s[si["status"]] in OPEN_STEP:
            missing.append(f"step {s[0]} is still {s[si['status']]}")
        if s[si["status"]] == "done" and not (s[si["start"]] and s[si["end"]]):
            missing.append(f"step {s[0]} has no start/end time (plan-set.py ... start=now / end=now)")

    for s in live:
        a, b = s[si["start"]], s[si["end"]]
        if a and b and re.fullmatch(r"\d\d:\d\d", a) and re.fullmatch(r"\d\d:\d\d", b) and b < a \
                and not (a > "20:00" and b < "04:00"):
            missing.append(f"step {s[0]} ends ({b}) before it starts ({a})")

    for name, text in (("plan.md", plan.split("## ")[0]), ("log.md", log)):
        junk = re.findall(r"<[a-z][^<>\n]*\|[^<>\n]*>|<!--|HH:MM", text)
        if junk:
            missing.append(f"{name} still has template placeholders ({', '.join(sorted(set(junk))[:3])})")

    if re.search(r"budget: ~0k", plan) and re.search(r"^E\d+ \S+ (dispatch|wait)", log, re.M):
        missing.append("budget still ~0k though work ran — the Stop hook writes it; run scripts/spend.py <transcript> <plan> --write")

    chdr, crit = table(plan, "Criteria")
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
    missing += overview_problems(ov)
    missing += commit_problems(goal, head)

    if not quick and not os.path.exists(profile_p):
        missing.append("no profile.md in the store — create it from templates/profile.md (research goals too)")

    measured = None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("mama_spend", os.path.join(os.path.dirname(os.path.abspath(__file__)), "spend.py"))
        sp = importlib.util.module_from_spec(spec); spec.loader.exec_module(sp)
        measured = sp.measure(os.path.join(goal, "plan.md"))
    except Exception:
        pass
    ml = re.search(rf"^- ?\d{{4}}-\d\d-\d\d {re.escape(slug)} .*?tokens est [^/|]*/ ~?([\d.]+)([kM])", lessons, re.M)
    if measured and ml:
        claimed = float(ml.group(1)) * (1000 if ml.group(2) == "M" else 1)
        if abs(claimed - measured / 1000) > 0.25 * (measured / 1000) + 10:
            missing.append(f"lessons metrics says ~{ml.group(1)}{ml.group(2)} tokens but measured is {round(measured / 1000)}k — use the measured number")

    times = re.findall(r"^[EDFQ]\d+ (\d\d:\d\d) ", log, re.M)
    mins = "?m"
    if times:
        a, b = (datetime.datetime.strptime(t, "%H:%M") for t in (times[0], times[-1]))
        total = int((b - a).total_seconds() // 60) % (24 * 60)
        mins = f"{total}m (active {total - waiting_minutes(log)}m)"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import estimate
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
            f"questions {questions} (changed plan: ?) | fix rounds {att} | "
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
