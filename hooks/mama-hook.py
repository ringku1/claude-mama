#!/usr/bin/env python3
"""mama hooks. Usage (from settings.json): mama-hook.py precompact|sessionstart|stop

Reads the hook JSON on stdin. Never fails loudly: any error → exit 0 with no output, plus one
line (time, mode, error) appended to ~/.claude/mama/hook-errors.log.

This session's goals are the ones it recorded writing to (activity.log, any store). No record,
no goal — the hooks never read transcripts to guess ownership.

- MAMA_VIA=<plugin root> (set by hooks/hooks.json): the one-liner's skills/mama also loads as plugin
                mama@skills-dir, and a marketplace install may sit beside the one-liner, so each hook can be
                registered twice; when <claude folder>/settings.json holds, for this same event, install.py's
                exec-form entry exactly (interpreter and mama-hook.py both existing files, args [script, mode]),
                this plugin copy exits at once and leaves the work to that one. Anything else (a command string,
                a hand edit, a stale entry) runs the plugin: a double run is the accepted worst case.
- precompact:   logs `E compaction` in this session's open goal (not recorded as a write) and
                tells the summary to keep it (slug, paths).
- every mode:   at most once a day starts scripts/self-update.py in the background (git installs;
                MAMA_AUTO_UPDATE=0 turns it off).
- sessionstart: (matcher "compact") injects the open goals so the session can re-enter its own.
- stop:         measures the goal's spend into plan.md (a closed goal's cache is then deleted, also
                for the session's earlier closed goals);
                blocks the stop (with every problem listed) if this session's goal:
                is `running` at ≥70% of its budget ceiling (first, while the ceiling is under the approved
                size × the header's `auto-raise: <f>x`, the hook raises it there itself, logs
                `D budget auto-raised to <size> (tag: auto)` and doesn't block; then autonomous: raise it
                within 2× and go on; otherwise ask: continue / cut scope / stop); is a quick goal past 300k
                tokens or 30 active minutes with no `D … quick …` answer yet (offer a full goal); has a
                bug-hunt round at or past its tier's cap (quick/standard 1, full 2, plus one per
                `D hunt: extra round`) with real bugs and no `D hunt: …` / `… deliver with known issues …`
                decision after it (ask: deliver with known issues / one more low round);
                is `running` without a final `wait`/`dispatch` log line; reached a milestone after
                overview.md was written (an overview with a generated block: only a scope change, the
                status going to waiting, or an abort count — see overview_stale);
                has a user decision not yet followed by learning (patterns.md / `E learn` line; not quick mode);
                or says `done` while close-check.py fails (the hook's close check skips commit checks:
                plan-set's close check at status=done runs them in full). The same problem list blocks only once
                (kept in the goal's .last-block); a changed list blocks again. A cut run (past the deadline, or
                a close check that didn't finish or had its spend measure cut) has a partial list: it blocks only
                for a problem the last block didn't name, and then keeps the last block's problems plus its own,
                so a run of cut Stops doesn't block every turn.
                Claude Code kills the hook at 10s, counted from before bash, the launcher's Python probe and
                the imports: all its work shares one deadline (HOOK_BUDGET from this file's first statement,
                the rest kept for that start-up and for work past the deadline); a done goal's close check runs before the hook's own measure; a measure cut by the
                deadline is not the spend, so it is neither written nor judged that turn; past the deadline no
                optional check starts (quick, hunt, overview, learning, closed goals' measures): the block lists
                what was found by then.
                Every Stop on an open goal writes <goal>/.heartbeat (`<ISO time> <spend>k`, or `-` when the
                measure was cut or failed). Loud guards: every caught error is appended to hook-errors.log, and
                a spend measure that raises is itself a problem ("spend not measured: …").
"""
import time

T0 = time.time()  # first: the clock runs from before the imports (1-2.5s with bash and the probe on cold Windows)
# seconds of work from T0. Claude Code kills the hook at 10s from before bash started: up to ~2.5s before T0
# (bash, the launcher's probe, Python start on cold Windows) + 6s = 8.5s, leaving ~1.5s for work past the
# deadline (a block's print, a cache write, a subprocess's timeout overshoot); the close check gets ~4s of it
HOOK_BUDGET = 6.0
DEADLINE = T0 + HOOK_BUDGET  # time.time() epoch, shared by every measure and the close check

import datetime  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
OPEN = {"planning", "approved", "running", "waiting", "paused", "blocked"}
ERRORS = os.path.expanduser("~/.claude/mama/hook-errors.log")
UPDATE_STAMP = os.path.expanduser("~/.claude/mama/.update-check")
UPDATE_EVERY = 24 * 3600
CLOSE_CHECK_RESERVE = 1.0  # seconds of DEADLINE kept for the hook's own measure after the close check
CLOSE_CHECK_SPEND_MARGIN = 1.5  # the close check's own spend read stops this long before its timeout
MIN_WORK = 0.5  # seconds: less than this left before DEADLINE, a close check or a closed goal's measure is skipped
EVENTS = {"stop": "Stop", "precompact": "PreCompact", "sessionstart": "SessionStart"}  # mode -> settings.json event

try:
    sys.path.insert(0, SCRIPTS)
    import activity  # noqa: E402
    import clock  # noqa: E402
    import fileio  # noqa: E402
    import log as mama_log  # noqa: E402
    IMPORT_ERROR = None
except Exception as e:  # reported by __main__, so a broken install still exits 0
    IMPORT_ERROR = e


def claude_dir():
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join("~", ".claude"))


def _install_entry(h, mode):
    """h is install.py's exec-form entry for mode, and both its files exist: command the interpreter (a file,
    not the bare WindowsApps stub — a Microsoft Store Python's own folder under WindowsApps is real), args
    exactly [<…/mama-hook.py>, mode]. Command strings are never parsed."""
    if not isinstance(h, dict):
        return False
    cmd, args = h.get("command"), h.get("args")
    if not (isinstance(cmd, str) and isinstance(args, list) and len(args) == 2 and args[1] == mode
            and isinstance(args[0], str)):
        return False
    parts = cmd.replace("\\", "/").lower().split("/")
    return ((len(parts) < 2 or parts[-2] != "windowsapps") and os.path.isfile(cmd)
            and args[0].replace("\\", "/").split("/")[-1] == "mama-hook.py" and os.path.isfile(args[0]))


def step_aside(mode):
    """This is a plugin copy (MAMA_VIA = its plugin root, set by hooks.json) and settings.json runs, for this
    mode's event, the one-liner's entry exactly as install.py writes it: running both would do the work twice.
    Anything else (a command string, a hand edit, a stale entry, unreadable settings) runs the plugin copy:
    a double run is the accepted worst case. (Either copy's close check skips commit checks; plan-set's close
    check at status=done runs them in full.)"""
    if not os.environ.get("MAMA_VIA") or mode not in EVENTS:
        return False
    try:
        with open(os.path.join(claude_dir(), "settings.json"), encoding="utf-8") as f:
            settings = json.load(f)
        entries = settings["hooks"][EVENTS[mode]]
        return any(_install_entry(h, mode) for e in entries for h in e["hooks"])
    except (OSError, ValueError, KeyError, TypeError):
        return False  # no settings or no such hook: the usual case, nothing to report
    except Exception as e:
        report(mode, e)
        return False


def main_checkout(cwd):
    """The main checkout's root (worktrees share it). Git < 2.31 has no --path-format: there
    rev-parse fails or echoes the flag back, so fall back to the plain (maybe relative) path."""
    def rev_parse(*args):
        try:
            r = subprocess.run(["git", "-C", cwd, "rev-parse", *args, "--git-common-dir"],
                               capture_output=True, text=True, timeout=5)
        except Exception as e:
            report("sessionstart", e)
            return None
        lines = r.stdout.strip().splitlines()
        return lines[-1].strip() if r.returncode == 0 and lines and not lines[-1].startswith("--") else None

    common = rev_parse("--path-format=absolute")
    if not common or not os.path.isabs(common):
        common = rev_parse()
    if not common:
        return None
    return os.path.dirname(os.path.abspath(os.path.join(cwd, common)))


def read_goal(goal_dir):
    plan = os.path.join(goal_dir, "plan.md")
    try:
        with open(plan, encoding="utf-8") as f:
            head = f.read(2000)
    except OSError:
        return None
    fields = dict(re.findall(r"(\w[\w ]*?): ([^|\n]*)", head))
    return {
        "slug": os.path.basename(goal_dir),
        "dir": goal_dir,
        "store": os.path.dirname(goal_dir),
        "status": fields.get("status", "?").strip(),
        "mode": fields.get("mode", "—").strip(),
        "progress": fields.get("progress", "?").strip(),
        "worktree": fields.get("worktree", "n/a").strip(),
        "approved": fields.get("approved", "—").strip(),
        "tier": tier_of(fields),
        "plan": plan,
    }


TIERS = {"quick", "standard", "full"}
HUNT_CAP = {"quick": 1, "standard": 1, "full": 2}


def tier_of(fields):
    """The header's `tier:`; missing or unset (old goals, — before research picks it): full, or quick for
    a `mode: quick` goal."""
    t = fields.get("tier", "").strip()
    if t in TIERS:
        return t
    return "quick" if fields.get("mode", "").strip() == "quick" else "full"


def goals(store):
    if not store or not os.path.isdir(store):
        return []
    found = (read_goal(os.path.join(store, s)) for s in sorted(os.listdir(store)))
    return [g for g in found if g]


_LOADED = {}


def _load(name, file):
    if name in _LOADED:
        return _LOADED[name]
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _LOADED[name] = m
    return m


def session_id(inp):
    return inp.get("session_id") or os.path.splitext(os.path.basename(inp.get("transcript_path") or ""))[0]


def session_goals(inp):
    """Goals (dicts) this session wrote to, most recent last, in any store — only from
    activity.log, which every goal write records. No record, no goal: guessing from the
    transcript misattributed goals and read huge transcripts on every turn."""
    sid = session_id(inp)
    order = getattr(activity, "goals_for", None) or activity.goals_of
    return [g for g in map(read_goal, order(sid) if sid else []) if g]


def log_text(plan):
    try:
        with open(os.path.join(os.path.dirname(plan), "log.md"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


AUTO_RAISED = re.compile(r"D\d+ \d\d:\d\d budget auto-raised to .*\(tag: auto\)$")  # the hook's own line


def waiting_on_background(plan):
    """True if the goal's last log line is `E<n> HH:MM wait|dispatch ...` — ending the turn to
    wait on background work (agents just dispatched, the gate) is legitimate; its notification
    wakes the session. A dispatch line counts, so no extra `wait` line is needed after it. The hook's own
    `D budget auto-raised …` line is skipped: it was written after the session's last line."""
    lines = [l.strip() for l in log_text(plan).splitlines()
             if re.match(r"\s*[EDFQ]\d+ ", l) and not AUTO_RAISED.match(l.strip())]
    return bool(lines) and re.match(r"E\d+ \d\d:\d\d (wait|dispatch)\b", lines[-1]) is not None


def unlearned(plan):
    """A `tag: user` decision with no learning after it (no `E learn` line, patterns.md older)."""
    try:
        with open(plan, encoding="utf-8") as f:
            start = clock.start_of(f.read(3000))
    except OSError:
        return False
    tl = clock.timeline(log_text(plan), start)
    idx = [i for i, (_, kind, _, text) in enumerate(tl) if kind == "D" and "tag: user" in text]
    if not idx:
        return False
    last = idx[-1]
    if any(kind == "E" and re.match(r"learn\b", text) for _, kind, _, text in tl[last + 1:]):
        return False
    try:
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.expanduser("~/.claude/mama/patterns.md")))
    except OSError:
        return True
    return mt < tl[last][0]


AUTO_START = "<!-- mama:auto:start -->"
WATCH = ".overview-watch"  # what the last Stop saw: status, scope, when the prose last became due
ROW_ID = re.compile(r"^\|\s*([SC]\d+)\s*\|", re.M)


def overview_stale(plan):
    """The overview's prose is older than the last milestone. An overview with a generated block
    (between the mama:auto markers, regenerated from state) needs its hand-written parts refreshed only
    for a scope change (steps or criteria added), the status going to waiting, or an abort — never for a
    ★ step done (the block shows progress); these are tracked by watched_milestone. Older overviews: the
    last milestone plan-set marked (step done/blocked, status or PR changed, scope added); goals from
    before milestones: plan.md newer than overview.md. The Status line is synced on every write."""
    goal = os.path.dirname(plan)
    ov = os.path.join(goal, "overview.md")
    try:
        with open(ov, encoding="utf-8") as f:
            generated = AUTO_START in f.read()
        if generated:
            return watched_milestone(plan) > os.path.getmtime(ov) + 2
        mark = os.path.join(goal, ".milestone")
        ref = os.path.getmtime(mark) if os.path.exists(mark) else os.path.getmtime(plan)
        return ref > os.path.getmtime(ov) + 2
    except OSError:
        return False


def watched_milestone(plan):
    """When the prose last became due (epoch, 0 = never): compares the plan's status and scope (step and
    criterion IDs) with what the last Stop saw (<goal>/.overview-watch); a change to waiting or aborted,
    or new rows once past planning, dates a milestone at plan.md's mtime (the write that made it). Done
    doesn't count: the close check already demands the final report."""
    path = os.path.join(os.path.dirname(plan), WATCH)
    with open(plan, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"status: (\w+)", text[:3000])
    status = m.group(1) if m else "?"
    scope = sorted(set(ROW_ID.findall(text)))
    try:
        with open(path, encoding="utf-8") as f:
            seen = json.load(f)
    except (OSError, ValueError):
        seen = None
    at = seen.get("at", 0) if isinstance(seen, dict) else 0
    due = status in ("waiting", "aborted")
    if isinstance(seen, dict):
        due = (due and status != seen.get("status")) or (
            scope != seen.get("scope") and status != "planning" and seen.get("status") != "planning")
    if due:
        at = max(at, os.path.getmtime(plan))
    if not isinstance(seen, dict) or due or seen.get("status") != status or seen.get("scope") != scope:
        try:
            fileio.write_atomic(path, json.dumps({"status": status, "scope": scope, "at": at}))
        except Exception as e:
            report("stop", e)
    return at


PARTIAL = "PARTIAL: spend measure cut"  # close-check's line when MAMA_SPEND_DEADLINE cut its measure


def close_problems(plan):
    """(the close checklist's failures or "" if it passes, partial). A close check that runs out of the
    hook's time budget, crashes or can't start is a problem itself — never a silent pass, and never an
    error that drops the other problems. partial: it didn't finish, or its spend measure was cut (its
    PARTIAL line, dropped from the text), so its list may be short. It skips commit checks (the hook
    sets MAMA_SPEND_DEADLINE); plan-set's close check at status=done runs them."""
    goal = os.path.dirname(plan)
    unfinished = f"close check didn't finish — run scripts/close-check.py {goal}"
    left = DEADLINE - CLOSE_CHECK_RESERVE - time.time()
    if left < MIN_WORK:
        return unfinished, True
    # its spend measure must fit too: stop reading transcripts before its time ends
    env = dict(os.environ, MAMA_SPEND_DEADLINE=str(time.time() + max(0.0, left - CLOSE_CHECK_SPEND_MARGIN)))
    try:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "close-check.py"), goal],
                           capture_output=True, text=True, timeout=left, env=env)
    except Exception as e:
        report("stop", e)
        return unfinished, True
    lines = r.stdout.strip().splitlines()
    partial = PARTIAL in (l.strip() for l in lines)
    out = "\n".join(l for l in lines if l.strip() != PARTIAL).strip()
    if r.returncode == 0:
        return "", partial
    return (out, partial) if out else (unfinished, True)


QUICK_TOKENS, QUICK_MINUTES = 300_000, 30  # past either, a quick goal has outgrown quick mode


def quick_outgrown(g, spent):
    """A running quick goal past QUICK_TOKENS or QUICK_MINUTES active, not yet put to the user
    (no `D … quick …` decision logged since it started) — offer to continue as a full goal."""
    if g["mode"] != "quick" or g["status"] != "running":
        return False
    log = log_text(g["plan"])
    if re.search(r"^D\d+ \S+ .*\bquick\b", log, re.M):
        return False
    if spent is not None and spent >= QUICK_TOKENS:
        return True
    cc = _load("mama_close_check", "close-check.py")
    with open(g["plan"], encoding="utf-8") as f:
        start = clock.start_of(f.read(3000))
    total = cc.actual_minutes(log, start)
    return total is not None and total - cc.waiting_minutes(log, start) >= QUICK_MINUTES


HUNT_LINE = re.compile(r"^E\d+ \S+ hunt (\d+):.*$", re.M)
HUNT_DECISION = re.compile(r"^D\d+ \S+ (?:hunt:|.*\bdeliver with known issues\b)", re.M)


def hunt_capped(g):
    """(round, real bugs, cap) when the last bug-hunt round is at or past the tier's cap (quick/standard 1,
    full 2; each `D hunt: extra round` allows one more) and found real bugs (trade-offs aren't real), with
    no hunt decision (`D hunt: …`, or the old `D … deliver with known issues …`) after it. Else None."""
    log = log_text(g["plan"])
    by_round = {k: real for k, real in _load("mama_close_check", "close-check.py").hunt_rounds(log)
                if real is not None}  # a round logged twice (found, then fixed): its last count
    if not by_round:
        return None
    k = max(by_round)
    cap = HUNT_CAP[g["tier"]]
    if k < cap or not by_round[k]:
        return None
    last = [m.end() for m in HUNT_LINE.finditer(log) if int(m.group(1)) == k][-1]
    if HUNT_DECISION.search(log[last:]):
        return None
    return k, by_round[k], cap


def measure_budget(plan, transcript, closed=False):
    """Write the measured spend into the plan header (mtime kept); return (pct of ceiling or None,
    tokens or None). A closed goal is measured once more (its final spend), then its cache is
    deleted, so later turns skip it and no done goal keeps a cache on disk; with less than MIN_WORK
    left it is not measured at all and keeps its cache for a later Stop. A measure cut by the
    hook's DEADLINE is only part of the spend: not written, not judged (None, None); the next Stop
    resumes from the cache."""
    sp = _load("mama_spend", "spend.py")
    cache = os.path.join(os.path.dirname(plan), sp.CACHE)
    if closed and (not os.path.exists(cache) or time.time() >= DEADLINE - MIN_WORK):
        return None, None
    total = sp.measure(plan, transcript, deadline=DEADLINE)
    if getattr(sp.measure, "partial", False):  # cut by the deadline: the next Stop finishes it
        return None, None
    if closed:
        try:
            os.remove(cache)
        except OSError:
            pass
    if total is None:
        return None, None
    _, _, size = sp.window(plan)
    with fileio.plan_lock(plan):
        st = os.stat(plan)
        with open(plan, encoding="utf-8") as f:
            text = f.read()
        new = re.sub(r"(budget: )~?[^/|\n]*(/)", rf"\g<1>~{round(total / 1000)}k \g<2>", text, count=1)
        if new != text:
            fileio.write_atomic(plan, new)
            os.utime(plan, (st.st_atime, st.st_mtime))
    c = sp.ceiling(size)
    return (round(100 * total / c) if c else None), total


def drop_closed_caches(inp, earlier):
    """The session's earlier goals that are closed but still hold a spend cache (the session moved
    on to another goal before the Stop hook saw them closed): measure each once more, so the plan
    keeps its final spend, and delete the cache. Out of time: left for a later Stop."""
    for g in earlier:
        if time.time() >= DEADLINE - MIN_WORK:
            return
        if g["status"] in OPEN or not os.path.exists(os.path.join(g["dir"], ".spend-cache.json")):
            continue
        try:
            measure_budget(g["plan"], inp.get("transcript_path", ""), closed=True)
        except Exception as e:
            report("stop", e)


def size_text(tokens):
    """A budget size for tokens, as plan-set accepts it: `L 1.5M`, `L 450k`."""
    if tokens >= 1_000_000 and tokens % 100_000 == 0:
        return f"L {tokens / 1_000_000:g}M"
    return f"L {round(tokens / 1000)}k"


def auto_raise(g):
    """While the ceiling is under the approved size × the header's `auto-raise: <f>x` (1.0–2.0; missing:
    1x, never), raise it there (plan header, under plan_lock, mtime kept) and log
    `D budget auto-raised to <size> (tag: auto)`; return the new size, else None."""
    with open(g["plan"], encoding="utf-8") as f:
        head = f.read(3000).split("\n## ")[0]
    m = re.search(r"auto-raise: ([\d.]+)\s*x", head)
    try:
        f_ = min(2.0, float(m.group(1))) if m else 1.0
    except ValueError:
        f_ = 1.0
    sp = _load("mama_spend", "spend.py")
    approved = sp.ceiling(g["approved"])
    if f_ <= 1.0 or not approved:
        return None
    target = int(round(approved * f_))
    size = size_text(target)
    with fileio.plan_lock(g["plan"]):
        _, _, cur = sp.window(g["plan"])
        c = sp.ceiling(cur)
        if not c or c >= target:
            return None
        st = os.stat(g["plan"])
        with open(g["plan"], encoding="utf-8") as f:
            text = f.read()
        new = re.sub(r"(budget: [^/|\n]*/ ?)[^|\n]*?(?=\s*(?:\||$))", lambda mm: mm.group(1) + size, text,
                     count=1, flags=re.M)
        if new == text:
            return None
        fileio.write_atomic(g["plan"], new)
        os.utime(g["plan"], (st.st_atime, st.st_mtime))
    # not recorded as a write: the hook's own line never claims a goal for a session
    mama_log.write(os.path.join(g["dir"], "log.md"), "D", f"budget auto-raised to {size} (tag: auto)", record=False)
    return size


def heartbeat(g, spent):
    """<goal>/.heartbeat: this Stop ran (close-check and plan-set check it). `-`: no spend measured."""
    k = f"{round(spent / 1000)}k" if spent is not None else "-"
    try:
        fileio.write_atomic(os.path.join(g["dir"], ".heartbeat"),
                            f"{datetime.datetime.now().isoformat(timespec='seconds')} {k}\n")
    except Exception as e:
        report("stop", e)


def block_once(goal_dir, reason, problems, cut):
    """Print the block unless it repeats the last block for this goal word for word. A cut run's list is
    partial: it blocks only for a problem the last block didn't name, and then remembers the last block's
    problems plus its own, so the next cut run stays quiet (a later full run blocks at most once more)."""
    last = os.path.join(goal_dir, ".last-block")
    try:
        with open(last, encoding="utf-8") as f:
            before = f.read()
    except OSError:
        before = ""
    if cut:
        new = [p for p in problems if f"\n- {p}\n- " not in before + "\n- "]
        if not new:
            return
        print(json.dumps({"decision": "block", "reason": reason}), flush=True)
        old = before.split("\n- ")[1:] if before else []
        reason = "\n- ".join([reason.split("\n- ", 1)[0]] + old + new)
    elif before == reason:
        return
    else:
        print(json.dumps({"decision": "block", "reason": reason}), flush=True)  # out before any later kill
    try:
        fileio.write_atomic(last, reason)
    except OSError:
        pass  # can't remember it: the block repeats next turn, but this one still stands and the hook ends cleanly


def stop(inp, g):
    try:
        idle = datetime.datetime.now().timestamp() - os.path.getmtime(os.path.join(g["dir"], "log.md"))
    except OSError:
        idle = 0
    if g["status"] not in OPEN and idle > 3600:
        return  # a goal closed earlier — don't nag about it in later, unrelated turns
    problems = []
    # a done goal's close check first: it warms the spend cache, and the hook's own measure can't starve it
    close_out, close_partial = close_problems(g["plan"]) if g["status"] == "done" else ("", False)
    pct, spent = None, None
    if g["status"] in OPEN:  # a closed goal's final measure judges nothing: optional, after the checks
        try:
            pct, spent = measure_budget(g["plan"], inp.get("transcript_path", ""))
        except Exception as e:
            report("stop", e)
            problems.append(f"spend not measured: {one_line(e)} — see ~/.claude/mama/hook-errors.log")
        heartbeat(g, spent)
    def late():  # past DEADLINE no optional check starts: the block goes out with what was gathered
        return time.time() >= DEADLINE

    cut = late()
    try:
        if not cut and quick_outgrown(g, spent):
            problems.append(
                f"This quick goal has outgrown quick mode (past {QUICK_TOKENS // 1000}k tokens or {QUICK_MINUTES} "
                "active minutes). Tell the user and ask: continue as a full goal (set mode checkpointed/autonomous "
                "and a budget; the close check then asks for everything) or keep it quick — log the answer as "
                "`D … quick … (tag: user)`.")
    except Exception as e:
        report("stop", e)
    if g["status"] == "running" and pct is not None and pct >= 70:
        try:
            if auto_raise(g):
                pct = None  # raised itself within what the user allowed: no block for the budget
        except Exception as e:
            report("stop", e)
    if g["status"] == "running" and pct is not None and pct >= 70:
        raise_to = ("raise the ceiling with headroom — measured spend + what's left estimated + 30% "
                    "(e.g. budget='~…k / L 1.5M') — so it doesn't come back every turn")
        if g["mode"] == "autonomous":
            problems.append(
                f"Budget at {pct}% of its ceiling. If what's left is in the approved plan and the new ceiling stays "
                f"within 2× the approved {g['approved']} (plan-set refuses past it): {raise_to}, log `D budget raised to … (tag: auto)`, say so in the "
                "overview, and continue. Otherwise (new scope, or past 2×) stop dispatching, set status waiting, "
                "and ask the user: continue / cut scope / stop.")
        else:
            problems.append(
                f"Budget at {pct}% of its ceiling. Stop dispatching, set status waiting, and ask the user: "
                f"continue / cut scope / stop. On continue, {raise_to}.")
    try:
        cut = cut or late()
        capped = hunt_capped(g) if g["status"] in OPEN and not cut else None
    except Exception as e:
        report("stop", e)
        capped = None
    if capped:
        k, real, cap = capped
        problems.append(
            f"Bug hunt round {k} found {real} real bug(s) and the {g['tier']} tier's cap is {cap} round(s). Fix them "
            "(fix steps, failing-first), then set status waiting and ask the user: deliver with known issues / one "
            "more low round — log the answer as `D hunt: deliver with known issues … (tag: user)` or "
            "`D hunt: extra round … (tag: user)` (rules/loop.md → Bug hunt).")
    if g["status"] == "running" and not waiting_on_background(g["plan"]):
        problems.append(
            f"Goal is still marked running ({g['progress']}). Continue with the next step, or set an honest "
            "status (waiting / paused / blocked) — or, to wait on your own background work, make `E dispatch …` "
            "or `E wait <what>` the last log line.")
    cut = cut or late()
    if cut:
        pass
    elif overview_stale(g["plan"]):
        problems.append("A milestone (the scope or status changed, or a ★ step finished or a step blocked on an older "
                        "overview) since overview.md was written — refresh overview.md (the user's only window); its "
                        "Status line is synced for you.")
    elif g["status"] in OPEN:
        try:
            with open(os.path.join(g["dir"], "overview.md"), encoding="utf-8") as f:
                problems += _load("mama_close_check", "close-check.py").overview_problems(f.read(), g["dir"])
        except Exception as e:
            report("stop", e)
    cut = cut or late()
    if not cut and g["mode"] != "quick" and unlearned(g["plan"]):
        problems.append(
            "A user decision was logged but nothing was learned since. For each answer that overrode your "
            "recommendation or stated a preference run scripts/learn.py (seen/stated/contra); if none, log `E learn none`.")
    if close_out.startswith("close check didn't finish"):
        problems.append(close_out)
    elif close_out:
        problems.append("Status is done but the close checklist fails:\n" + close_out)
    cut = cut or close_partial  # a partial close check: its list may be short, as a cut run's
    if problems:
        block_once(g["dir"], f"mama goal '{g['slug']}':\n- " + "\n- ".join(problems), problems, cut)
    elif not cut:  # a cut run doesn't know the list is empty: the last block stays remembered
        try:
            os.remove(os.path.join(g["dir"], ".last-block"))
        except OSError:
            pass
    if g["status"] not in OPEN:
        try:
            measure_budget(g["plan"], inp.get("transcript_path", ""), closed=True)
        except Exception as e:
            report("stop", e)


def maybe_self_update():
    """At most once a day, start scripts/self-update.py detached (it checks everything else and
    updates a git install). Off with MAMA_AUTO_UPDATE=0; plugin installs update through Claude Code."""
    if os.environ.get("MAMA_AUTO_UPDATE", "1") == "0" or os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return
    try:
        if datetime.datetime.now().timestamp() - os.path.getmtime(UPDATE_STAMP) < UPDATE_EVERY:
            return
    except OSError:
        pass
    os.makedirs(os.path.dirname(UPDATE_STAMP), exist_ok=True)
    with open(UPDATE_STAMP, "w", encoding="utf-8"):
        pass
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        detach = {"creationflags": flags}
    else:
        detach = {"start_new_session": True}
    subprocess.Popen([sys.executable, os.path.join(SCRIPTS, "self-update.py")], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, **detach)


def main(mode):
    if IMPORT_ERROR:
        raise IMPORT_ERROR
    try:
        maybe_self_update()
    except Exception as e:
        report(mode, e)  # updating is a convenience; the hook's own job comes first
    try:
        inp = json.load(sys.stdin)
    except ValueError:
        return
    mine = session_goals(inp)
    mine_open = [g for g in mine if g["status"] in OPEN]
    my_goal = mine_open[-1] if mine_open else None

    if mode == "stop":
        if not inp.get("stop_hook_active") and mine:
            stop(inp, mine[-1])
            drop_closed_caches(inp, mine[:-1])
        return

    if mode == "precompact":
        if my_goal:
            # counted (the metrics line reads compactions from the log), but not recorded as this
            # session's write: an event line never makes a goal anyone's
            mama_log.write(os.path.join(my_goal["dir"], "log.md"), "E",
                           f"compaction ({inp.get('trigger', 'auto')})", record=False)
            print(
                f"This session is running the mama goal '{my_goal['slug']}'. In the summary, keep: "
                f"the slug '{my_goal['slug']}', its tracking folder {my_goal['dir']}/, "
                f"its worktree {my_goal['worktree']}, the current step and any unanswered user question. "
                "Its full state is on disk in plan.md and log.md."
            )
        return

    if mode == "sessionstart":
        root = main_checkout(inp.get("cwd") or os.getcwd())  # git: only here, never on every Stop
        store = activity.canon(os.path.join(root, ".claude", "mama")) if root else None
        listed = [g for g in goals(store) if g["status"] in OPEN]
        seen = {g["dir"] for g in listed}
        listed += [g for g in mine_open if g["dir"] not in seen]  # own goals in other stores
        if not listed:
            return
        lines = [f"- {g['slug']} — {g['status']} — {g['progress']} — worktree {g['worktree']}"
                 + ("" if g["store"] == store else f" — store {g['store']}") for g in listed]
        others = [g["slug"] for g in mine_open if g is not my_goal]
        hint = (
            (f"This session's goal is '{my_goal['slug']}' ({my_goal['status']}, folder {my_goal['dir']})."
             if my_goal else "None of them is recorded as this session's; check the summary for which one (if any) is.")
            + (f" This session also touched open goal(s): {', '.join(others)}." if others else "")
        )
        ctx = (
            "Context was compacted. Open mama goals" + (f" in this repo (store {store})" if store else "")
            + ":\n" + "\n".join(lines) + f"\n{hint} If this session was running a mama goal, "
            "re-enter it per the mama skill's Re-entry section (read its plan.md, log.md tail, decisions) "
            "before doing anything else. Never adopt another session's goal by guess — ask the user if unsure."
        )
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))


def one_line(err):
    return " ".join(f"{type(err).__name__}: {err}".split())


def report(mode, err):
    """Append `<time> <mode> <Type>: <msg>` to hook-errors.log; never raises."""
    try:
        os.makedirs(os.path.dirname(ERRORS), exist_ok=True)
        msg = one_line(err)
        with open(ERRORS, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {mode or '-'} {msg}\n")
    except Exception:  # noqa: the error log itself can't be written: nowhere left to report
        pass


if __name__ == "__main__":
    _mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if not step_aside(_mode):  # else the settings.json hook does this work; running both would do it twice
            main(_mode)
    except Exception as e:
        report(_mode, e)
    sys.exit(0)
