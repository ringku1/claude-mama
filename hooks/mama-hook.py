#!/usr/bin/env python3
"""mama hooks. Usage (from settings.json): mama-hook.py precompact|sessionstart|stop

Reads the hook JSON on stdin. Never fails loudly: any error → exit 0 with no output,
so a broken hook can't disrupt a session.

- precompact:   logs `E compaction` in this session's goal and tells the summary to keep it (slug, paths).
- sessionstart: (matcher "compact") injects the open goals so the session can re-enter its own.
- stop:         blocks the stop once (with every problem listed) if this session's goal:
                is `running` without a final `wait` log line; reached a milestone after overview.md was written;
                has a user decision not yet followed by learning (patterns.md / `E learn` line);
                or says `done` while close-check.py fails.
"""
import datetime
import json
import os
import re
import subprocess
import sys

OPEN = {"planning", "approved", "running", "waiting", "paused", "blocked"}


def main_checkout(cwd):
    try:
        common = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return None
    return os.path.dirname(common) if common else None


def goals(store):
    out = []
    if not os.path.isdir(store):
        return out
    for slug in sorted(os.listdir(store)):
        plan = os.path.join(store, slug, "plan.md")
        if not os.path.isfile(plan):
            continue
        head = open(plan, encoding="utf-8").read(2000)
        fields = dict(re.findall(r"(\w[\w ]*?): ([^|\n]*)", head))
        out.append({
            "slug": slug,
            "status": fields.get("status", "?").strip(),
            "progress": fields.get("progress", "?").strip(),
            "worktree": fields.get("worktree", "n/a").strip(),
            "plan": plan,
        })
    return out


def _spend():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "spend.py")
    spec = importlib.util.spec_from_file_location("mama_spend", path)
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)
    return sp


def _close_check():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "close-check.py")
    spec = importlib.util.spec_from_file_location("mama_close_check", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def session_goals(inp, store):
    """Slugs of the goals in this store this session wrote to, most recent last. Recorded
    by the skill's writers (activity.log); for older sessions, read from the transcript."""
    sp = _spend()
    sid = inp.get("session_id") or os.path.splitext(os.path.basename(inp.get("transcript_path", "")))[0]
    store = sp.activity.canon(store)
    recorded = [os.path.basename(g) for g in sp.activity.goals_for(sid) if os.path.dirname(g) == store]
    try:
        data = open(inp.get("transcript_path", ""), encoding="utf-8", errors="ignore").read()
        read = sorted(sp.written_slugs(data), key=lambda s: data.rfind(s))
    except Exception:
        read = []
    # recorded writes are the newest (the record started later), so they go last
    return [s for s in read if s not in recorded] + recorded


def waiting_on_background(plan):
    """True if the goal's last log line is `E<n> HH:MM wait ...` — ending the turn to wait on
    background work (an agent, the gate) is legitimate; its notification wakes the session."""
    try:
        with open(os.path.join(os.path.dirname(plan), "log.md"), encoding="utf-8") as f:
            last = [l for l in f.read().splitlines() if l.strip()][-1]
    except Exception:
        return False
    return re.match(r"E\d+ \d\d:\d\d wait\b", last) is not None


def log_lines(plan):
    try:
        with open(os.path.join(os.path.dirname(plan), "log.md"), encoding="utf-8") as f:
            return [l for l in f.read().splitlines() if l.strip()]
    except Exception:
        return []


def unlearned(plan):
    """A `tag: user` decision with no learning after it (no `E learn` line, patterns.md older)."""
    lines = log_lines(plan)
    idx = [i for i, l in enumerate(lines) if l.startswith("D") and "tag: user" in l]
    if not idx:
        return False
    last = idx[-1]
    if any(re.match(r"E\d+ \d\d:\d\d learn\b", l) for l in lines[last + 1:]):
        return False
    m = re.match(r"D\d+ (\d\d):(\d\d) ", lines[last])
    started = re.search(r"started: (\d{4}-\d\d-\d\d \d\d:\d\d)", open(plan, encoding="utf-8").read(3000))
    if not m or not started:
        return False
    try:
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.expanduser("~/.claude/mama/patterns.md")))
    except OSError:
        return True
    start = datetime.datetime.strptime(started.group(1), "%Y-%m-%d %H:%M")
    when = start.replace(hour=int(m.group(1)), minute=int(m.group(2)))
    if when < start:
        when += datetime.timedelta(days=1)
    return mt < when


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
    check = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "close-check.py")
    r = subprocess.run([sys.executable, check, os.path.dirname(plan)], capture_output=True, text=True, timeout=10)
    return "" if r.returncode == 0 else r.stdout.strip()


def measure_budget(plan, transcript):
    """Write the measured spend into the plan header (mtime kept); return pct of ceiling or None."""
    sp = _spend()
    total = sp.measure(plan, transcript)
    if total is None:
        return None
    _, _, size = sp.window(plan)
    st = os.stat(plan)
    text = open(plan, encoding="utf-8").read()
    new = re.sub(r"(budget: )~?[^/|\n]*(/)", rf"\g<1>~{round(total / 1000)}k \g<2>", text, count=1)
    if new != text:
        sp.fileio.write_atomic(plan, new)
        os.utime(plan, (st.st_atime, st.st_mtime))
    c = sp.ceiling(size)
    return round(100 * total / c) if c else None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        inp = json.load(sys.stdin)
    except Exception:
        return
    cwd = inp.get("cwd") or os.getcwd()
    root = main_checkout(cwd)
    if not root:
        return
    store = os.path.join(root, ".claude", "mama")
    all_goals = goals(store)
    open_goals = [g for g in all_goals if g["status"] in OPEN]
    my_slugs = session_goals(inp, store)
    mine = my_slugs[-1] if my_slugs else None
    any_goal = next((g for g in all_goals if g["slug"] == mine), None)
    my_goal = any_goal if any_goal and any_goal["status"] in OPEN else None
    touched = set(my_slugs) if mode != "stop" else set()
    mine_open = [g for g in open_goals if g["slug"] in touched]
    if not my_goal and len(mine_open) == 1:
        my_goal = mine_open[0]

    if mode == "stop":
        if inp.get("stop_hook_active") or not any_goal:
            return
        g, problems = any_goal, []
        try:
            idle = datetime.datetime.now().timestamp() - os.path.getmtime(os.path.join(os.path.dirname(g["plan"]), "log.md"))
        except OSError:
            idle = 0
        if g["status"] not in OPEN and idle > 3600:
            return  # a goal closed earlier — don't nag about it in later, unrelated turns
        stale = overview_stale(g["plan"])
        pct = None
        if True:  # open goals, and goals closed within the last hour
            try:
                pct = measure_budget(g["plan"], inp.get("transcript_path", ""))
            except Exception:
                pct = None
        if g["status"] == "running" and pct is not None and pct >= 70:
            problems.append(
                f"Budget at {pct}% of its ceiling. Stop dispatching, set status waiting, and ask the user: "
                "continue / cut scope / stop. On continue, raise the ceiling with headroom — at least the measured "
                "spend + what's left estimated + 30% (e.g. budget='~…k / L 1.5M') — so it doesn't re-ask every turn.")
        if g["status"] == "running" and not waiting_on_background(g["plan"]):
            problems.append(
                f"Goal is still marked running ({g['progress']}). Continue with the next step, or set an honest "
                "status (waiting / paused / blocked) — or, to wait on your own background work, log `E wait <what>` last.")
        if stale:
            problems.append("A milestone (a step finished or blocked, the status, PR or scope changed) since overview.md "
                            "was written — regenerate overview.md (the user's only window); its Status line is synced for you.")
        elif g["status"] in OPEN:
            try:
                ov = open(os.path.join(os.path.dirname(g["plan"]), "overview.md"), encoding="utf-8").read()
                problems += _close_check().overview_problems(ov)
            except Exception:
                pass
        if unlearned(g["plan"]):
            problems.append(
                "A user decision was logged but nothing was learned since. For each answer that overrode your "
                "recommendation or stated a preference run scripts/learn.py (seen/stated/contra); if none, log `E learn none`.")
        if g["status"] == "done":
            out = close_problems(g["plan"])
            if out:
                problems.append("Status is done but the close checklist fails:\n" + out)
        if problems:
            reason = f"mama goal '{g['slug']}':\n- " + "\n- ".join(problems)
            print(json.dumps({"decision": "block", "reason": reason}))
        return

    if not open_goals:
        return

    if mode == "precompact":
        if my_goal:
            try:  # count it: the metrics line reads compactions from the log
                log_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "log.py")
                subprocess.run([sys.executable, log_py, os.path.join(os.path.dirname(my_goal["plan"]), "log.md"), "E",
                                f"compaction ({inp.get('trigger', 'auto')})"], capture_output=True, timeout=10)
            except Exception:
                pass
            print(
                f"This session is running the mama goal '{my_goal['slug']}'. In the summary, keep: "
                f"the slug '{my_goal['slug']}', its tracking folder {store}/{my_goal['slug']}/, "
                f"its worktree {my_goal['worktree']}, the current step and any unanswered user question. "
                "Its full state is on disk in plan.md and log.md."
            )
        return

    if mode == "sessionstart":
        lines = [f"- {g['slug']} — {g['status']} — {g['progress']} — worktree {g['worktree']}" for g in open_goals]
        others = [g["slug"] for g in mine_open if not my_goal or g["slug"] != my_goal["slug"]]
        hint = (
            (f"This session's goal is '{my_goal['slug']}' ({my_goal['status']})." if my_goal
             else "Check the summary for which one (if any) is this session's.")
            + (f" This session also touched open goal(s): {', '.join(others)}." if others else "")
        )
        ctx = (
            "Context was compacted. Open mama goals in this repo (store "
            f"{store}):\n" + "\n".join(lines) + f"\n{hint} If this session was running a mama goal, "
            "re-enter it per the mama skill's Re-entry section (read its plan.md, log.md tail, decisions) "
            "before doing anything else. Never adopt another session's goal by guess — ask the user if unsure."
        )
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
