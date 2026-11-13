#!/usr/bin/env python3
"""mama hooks. Usage (from settings.json): mama-hook.py precompact|sessionstart|stop

Reads the hook JSON on stdin. Never fails loudly: any error → exit 0 with no output, plus one
line (time, mode, error) appended to ~/.claude/mama/hook-errors.log.

This session's goals are the ones it recorded writing to (activity.log, any store). No record,
no goal — the hooks never read transcripts to guess ownership.

- precompact:   logs `E compaction` in this session's open goal (not recorded as a write) and
                tells the summary to keep it (slug, paths).
- sessionstart: (matcher "compact") injects the open goals so the session can re-enter its own.
- stop:         measures the goal's spend into plan.md (a closed goal's cache is then deleted, also
                for the session's earlier closed goals);
                blocks the stop (with every problem listed) if this session's goal:
                is `running` at ≥70% of its budget ceiling (autonomous: raise it within 2× and go on;
                otherwise ask: continue / cut scope / stop); is a quick goal past 300k tokens or 30
                active minutes with no `D … quick …` answer yet (offer a full goal);
                is `running` without a final `wait`/`dispatch` log line; reached a milestone after
                overview.md was written;
                has a user decision not yet followed by learning (patterns.md / `E learn` line; not quick mode);
                or says `done` while close-check.py fails. The same problem list blocks only once
                (kept in the goal's .last-block); a changed list blocks again.
"""
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
OPEN = {"planning", "approved", "running", "waiting", "paused", "blocked"}
ERRORS = os.path.expanduser("~/.claude/mama/hook-errors.log")

try:
    sys.path.insert(0, SCRIPTS)
    import activity  # noqa: E402
    import clock  # noqa: E402
    import fileio  # noqa: E402
    import log as mama_log  # noqa: E402
    IMPORT_ERROR = None
except Exception as e:  # reported by __main__, so a broken install still exits 0
    IMPORT_ERROR = e


def main_checkout(cwd):
    """The main checkout's root (worktrees share it). Git < 2.31 has no --path-format: there
    rev-parse fails or echoes the flag back, so fall back to the plain (maybe relative) path."""
    def rev_parse(*args):
        try:
            r = subprocess.run(["git", "-C", cwd, "rev-parse", *args, "--git-common-dir"],
                               capture_output=True, text=True, timeout=5)
        except Exception:
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
        "plan": plan,
    }


def goals(store):
    if not store or not os.path.isdir(store):
        return []
    found = (read_goal(os.path.join(store, s)) for s in sorted(os.listdir(store)))
    return [g for g in found if g]


def _load(name, file):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
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


def waiting_on_background(plan):
    """True if the goal's last log line is `E<n> HH:MM wait|dispatch ...` — ending the turn to
    wait on background work (agents just dispatched, the gate) is legitimate; its notification
    wakes the session. A dispatch line counts, so no extra `wait` line is needed after it."""
    lines = [l.strip() for l in log_text(plan).splitlines() if re.match(r"\s*[EDFQ]\d+ ", l)]
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


def overview_stale(plan):
    """The overview's prose is older than the last milestone plan-set marked (step done/blocked,
    status or PR changed, scope added). Its Status line is synced on every write, so ordinary
    plan writes don't count. Goals from before milestones: plan.md newer than overview.md."""
    goal = os.path.dirname(plan)
    ov = os.path.join(goal, "overview.md")
    try:
        mark = os.path.join(goal, ".milestone")
        ref = os.path.getmtime(mark) if os.path.exists(mark) else os.path.getmtime(plan)
        return ref > os.path.getmtime(ov) + 2
    except OSError:
        return False


def close_problems(plan):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "close-check.py"), os.path.dirname(plan)],
                       capture_output=True, text=True, timeout=10)
    return "" if r.returncode == 0 else r.stdout.strip()


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


def measure_budget(plan, transcript, closed=False):
    """Write the measured spend into the plan header (mtime kept); return (pct of ceiling or None,
    tokens or None). A closed goal is measured once more (its final spend), then its cache is
    deleted, so later turns skip it and no done goal keeps a cache on disk."""
    sp = _load("mama_spend", "spend.py")
    cache = os.path.join(os.path.dirname(plan), sp.CACHE)
    if closed and not os.path.exists(cache):
        return None, None
    total = sp.measure(plan, transcript)
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
    keeps its final spend, and delete the cache."""
    for g in earlier:
        if g["status"] in OPEN or not os.path.exists(os.path.join(g["dir"], ".spend-cache.json")):
            continue
        try:
            measure_budget(g["plan"], inp.get("transcript_path", ""), closed=True)
        except Exception:
            pass


def block_once(goal_dir, reason):
    """Print the block unless it repeats the last block for this goal word for word."""
    last = os.path.join(goal_dir, ".last-block")
    try:
        with open(last, encoding="utf-8") as f:
            if f.read() == reason:
                return
    except OSError:
        pass
    fileio.write_atomic(last, reason)
    print(json.dumps({"decision": "block", "reason": reason}))


def stop(inp, g):
    try:
        idle = datetime.datetime.now().timestamp() - os.path.getmtime(os.path.join(g["dir"], "log.md"))
    except OSError:
        idle = 0
    if g["status"] not in OPEN and idle > 3600:
        return  # a goal closed earlier — don't nag about it in later, unrelated turns
    problems = []
    try:
        pct, spent = measure_budget(g["plan"], inp.get("transcript_path", ""), closed=g["status"] not in OPEN)
    except Exception:
        pct, spent = None, None
    try:
        if quick_outgrown(g, spent):
            problems.append(
                f"This quick goal has outgrown quick mode (past {QUICK_TOKENS // 1000}k tokens or {QUICK_MINUTES} "
                "active minutes). Tell the user and ask: continue as a full goal (set mode checkpointed/autonomous "
                "and a budget; the close check then asks for everything) or keep it quick — log the answer as "
                "`D … quick … (tag: user)`.")
    except Exception:
        pass
    if g["status"] == "running" and pct is not None and pct >= 70:
        raise_to = ("raise the ceiling with headroom — measured spend + what's left estimated + 30% "
                    "(e.g. budget='~…k / L 1.5M') — so it doesn't come back every turn")
        if g["mode"] == "autonomous":
            problems.append(
                f"Budget at {pct}% of its ceiling. If what's left is in the approved plan and the new ceiling stays "
                f"within 2× the approved one: {raise_to}, log `D budget raised to … (tag: auto)`, say so in the "
                "overview, and continue. Otherwise (new scope, or past 2×) stop dispatching, set status waiting, "
                "and ask the user: continue / cut scope / stop.")
        else:
            problems.append(
                f"Budget at {pct}% of its ceiling. Stop dispatching, set status waiting, and ask the user: "
                f"continue / cut scope / stop. On continue, {raise_to}.")
    if g["status"] == "running" and not waiting_on_background(g["plan"]):
        problems.append(
            f"Goal is still marked running ({g['progress']}). Continue with the next step, or set an honest "
            "status (waiting / paused / blocked) — or, to wait on your own background work, make `E dispatch …` "
            "or `E wait <what>` the last log line.")
    if overview_stale(g["plan"]):
        problems.append("A milestone (a ★ step finished, a step blocked, the status, PR or scope changed) since overview.md "
                        "was written — regenerate overview.md (the user's only window); its Status line is synced for you.")
    elif g["status"] in OPEN:
        try:
            with open(os.path.join(g["dir"], "overview.md"), encoding="utf-8") as f:
                problems += _load("mama_close_check", "close-check.py").overview_problems(f.read(), g["dir"])
        except Exception:
            pass
    if g["mode"] != "quick" and unlearned(g["plan"]):
        problems.append(
            "A user decision was logged but nothing was learned since. For each answer that overrode your "
            "recommendation or stated a preference run scripts/learn.py (seen/stated/contra); if none, log `E learn none`.")
    if g["status"] == "done":
        out = close_problems(g["plan"])
        if out:
            problems.append("Status is done but the close checklist fails:\n" + out)
    if problems:
        block_once(g["dir"], f"mama goal '{g['slug']}':\n- " + "\n- ".join(problems))
    else:
        try:
            os.remove(os.path.join(g["dir"], ".last-block"))
        except OSError:
            pass


def main(mode):
    if IMPORT_ERROR:
        raise IMPORT_ERROR
    try:
        inp = json.load(sys.stdin)
    except ValueError:
        return
    cwd = inp.get("cwd") or os.getcwd()
    root = main_checkout(cwd)
    store = activity.canon(os.path.join(root, ".claude", "mama")) if root else None
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


def report(mode, err):
    try:
        os.makedirs(os.path.dirname(ERRORS), exist_ok=True)
        msg = " ".join(f"{type(err).__name__}: {err}".split())
        with open(ERRORS, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {mode or '-'} {msg}\n")
    except Exception:
        pass


if __name__ == "__main__":
    _mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        main(_mode)
    except Exception as e:
        report(_mode, e)
    sys.exit(0)
