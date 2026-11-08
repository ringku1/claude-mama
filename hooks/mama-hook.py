#!/usr/bin/env python3
"""mama hooks. Usage (from settings.json): mama-hook.py precompact|sessionstart|stop

Reads the hook JSON on stdin. Never fails loudly: any error → exit 0 with no output,
so a broken hook can't disrupt a session.

- precompact:   tells the compaction summary to keep this session's mama goal (slug, paths).
- sessionstart: (matcher "compact") injects the open goals so the session can re-enter its own.
- stop:         if this session's goal is still `running`, blocks the stop once with a reminder
                to continue or set an honest status (waiting / paused / blocked).
"""
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
    if not open_goals:
        return
    mine = session_slug(inp.get("transcript_path", ""))
    my_goal = next((g for g in open_goals if g["slug"] == mine), None)

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

    if mode == "stop":
        if inp.get("stop_hook_active") or not my_goal or my_goal["status"] != "running":
            return
        reason = (
            f"mama goal '{my_goal['slug']}' is still marked running ({my_goal['progress']}). "
            "Continue with the next step. If you're stopping on purpose, first set the goal status "
            "honestly in plan.md — waiting (for the user), paused, blocked, or done — and update overview.md."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
