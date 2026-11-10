#!/usr/bin/env python3
"""mama hooks. Usage (from settings.json): mama-hook.py precompact|sessionstart|stop

Reads the hook JSON on stdin. Never fails loudly: any error → exit 0 with no output,
so a broken hook can't disrupt a session.

- precompact:   tells the compaction summary to keep this session's mama goal (slug, paths).
- sessionstart: (matcher "compact") injects the open goals so the session can re-enter its own.
- stop:         blocks the stop once (with every problem listed) if this session's goal:
                is `running` without a final `wait` log line; has plan.md newer than overview.md;
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


def session_slug(transcript):
    """The goal this session last worked on, from its own transcript."""
    try:
        with open(transcript, encoding="utf-8", errors="ignore") as f:
            data = f.read()
    except Exception:
        return None
    hits = re.findall(r"\.claude/mama/([a-z0-9][a-z0-9-]*)/(?:plan|log|overview)\.md", data)
    return hits[-1] if hits else None


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
    try:
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.expanduser("~/.claude/mama/patterns.md")))
    except OSError:
        return True
    if not m:
        return False
    when = mt.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    return mt < when


def overview_stale(plan):
    ov = os.path.join(os.path.dirname(plan), "overview.md")
    try:
        return os.path.getmtime(plan) > os.path.getmtime(ov) + 2
    except OSError:
        return False


def close_problems(plan):
    check = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "close-check.py")
    r = subprocess.run([sys.executable, check, os.path.dirname(plan)], capture_output=True, text=True, timeout=10)
    return "" if r.returncode == 0 else r.stdout.strip()


def measure_budget(plan, transcript):
    """Write the measured spend into the plan header (mtime kept); return pct of ceiling or None."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "spend.py")
    spec = importlib.util.spec_from_file_location("mama_spend", path)
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)
    lo, hi, size = sp.window(plan)
    slug = os.path.basename(os.path.dirname(plan))
    timeline = []
    total = sp.usage_in(transcript, lo, hi, slug, timeline)
    import glob
    for p in glob.glob(os.path.join(os.path.splitext(transcript)[0], "subagents", "*.jsonl")):
        if datetime.datetime.fromtimestamp(os.path.getmtime(p)) < lo:
            continue
        first = next((t for t, _, _ in sp.messages(p) if t), None)
        if first and lo <= first <= hi and sp.slug_at(timeline, first) == slug:
            total += sp.usage_in(p, lo, hi)
    st = os.stat(plan)
    text = open(plan, encoding="utf-8").read()
    new = re.sub(r"(budget: )~?[^/|\n]*(/)", rf"\g<1>~{round(total / 1000)}k \g<2>", text, count=1)
    if new != text:
        open(plan, "w", encoding="utf-8").write(new)
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
    mine = session_slug(inp.get("transcript_path", ""))
    any_goal = next((g for g in all_goals if g["slug"] == mine), None)
    my_goal = any_goal if any_goal and any_goal["status"] in OPEN else None

    if mode == "stop":
        if inp.get("stop_hook_active") or not any_goal:
            return
        g, problems = any_goal, []
        stale = overview_stale(g["plan"])
        pct = None
        if g["status"] in OPEN:
            try:
                pct = measure_budget(g["plan"], inp.get("transcript_path", ""))
            except Exception:
                pct = None
        if g["status"] == "running" and pct is not None and pct >= 70:
            problems.append(
                f"Budget at {pct}% of its ceiling. Stop dispatching, set status waiting, and ask the user: "
                "continue (then raise the size, e.g. budget='~…k / L 1.5M') / cut scope / stop.")
        if g["status"] == "running" and not waiting_on_background(g["plan"]):
            problems.append(
                f"Goal is still marked running ({g['progress']}). Continue with the next step, or set an honest "
                "status (waiting / paused / blocked) — or, to wait on your own background work, log `E wait <what>` last.")
        if stale:
            problems.append("plan.md changed after overview.md — regenerate overview.md (the user's only window).")
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
            print(
                f"This session is running the mama goal '{my_goal['slug']}'. In the summary, keep: "
                f"the slug '{my_goal['slug']}', its tracking folder {store}/{my_goal['slug']}/, "
                f"its worktree {my_goal['worktree']}, the current step and any unanswered user question. "
                "Its full state is on disk in plan.md and log.md."
            )
        return

    if mode == "sessionstart":
        lines = [f"- {g['slug']} — {g['status']} — {g['progress']} — worktree {g['worktree']}" for g in open_goals]
        hint = (
            f"This session was most recently working on '{my_goal['slug']}'." if my_goal
            else "Check the summary for which one (if any) is this session's."
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
