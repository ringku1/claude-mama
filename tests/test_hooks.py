#!/usr/bin/env python3
"""mama-hook.py: whose goal a session is on, event lines, Stop nags. Run: python3 tests/test_hooks.py"""
import datetime
import json
import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import HOOK, NOW, S, SKILL, Base, utc  # noqa: E402,F401


class HookBase(Base):
    def transcript(self, sid):
        return os.path.join(self.home, ".claude", "projects", "p", f"{sid}.jsonl")

    def hook(self, mode, sid="sess-a", cwd=None, env_sid=None, path=None, raw=None):
        inp = raw if raw is not None else json.dumps(
            {"cwd": cwd or self.repo, "session_id": sid, "trigger": "auto", "transcript_path": self.transcript(sid)})
        env = self.env(env_sid)
        if path:
            env["PATH"] = path + os.pathsep + env.get("PATH", "")
        r = subprocess.run([sys.executable, HOOK, mode], input=inp, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def running_goal(self, slug="demo", sid="sess-a", store=None):
        if store:
            g = self.run_s("new-goal.py", store, slug, "build", "test", sid=sid).splitlines()[0]
        else:
            g = self.new_goal(slug, sid=sid)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "research none: test", sid=sid)
        self.run_s("plan-set.py", self.plan(g), "S+", "title=a", "verify=v", sid=sid)
        self.run_s("plan-set.py", self.plan(g), "--header", "status=running", "mode=autonomous", "budget=M", sid=sid)
        os.utime(os.path.join(g, "overview.md"))  # overview fresh
        return g

    def write_transcript(self, sid, goal, extra=0):
        """A transcript whose session ran log.py on goal (a write, as spend.written_slugs reads it)."""
        os.makedirs(os.path.dirname(self.transcript(sid)), exist_ok=True)
        call = {"type": "assistant", "timestamp": utc(NOW), "message": {"id": "m0", "content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": f"python3 log.py {os.path.join(goal, 'log.md')} E go"}}]}}
        with open(self.transcript(sid), "w", encoding="utf-8") as f:
            f.write(json.dumps(call) + "\n")
            filler = json.dumps({"type": "user", "timestamp": utc(NOW), "message": {"content": "x" * 400}})
            for _ in range(extra):
                f.write(filler + "\n")

    def activity(self):
        try:
            return self.read(os.path.join(self.home, ".claude", "mama", "activity.log"))
        except OSError:
            return ""


class WhoseGoal(HookBase):
    def test_never_claims_another_sessions_goal(self):
        g = self.running_goal(sid="sess-a")
        self.write_transcript("sess-b", g)  # sess-b wrote to it too, per its transcript, but never recorded
        before = self.read(os.path.join(g, "log.md"))
        self.assertEqual(self.hook("precompact", sid="sess-b", env_sid="sess-b"), "")
        self.assertEqual(self.read(os.path.join(g, "log.md")), before)  # no `E compaction` in a's goal
        self.assertNotIn("This session's goal", self.hook("sessionstart", sid="sess-b"))
        self.assertEqual(self.hook("stop", sid="sess-b"), "")
        self.assertIn("This session's goal is 'demo'", self.hook("sessionstart", sid="sess-a"))

    def test_own_goal_in_another_store(self):
        other = os.path.join(self.tmp, "other-repo")
        subprocess.run(["git", "init", "-q", other], check=True)
        g = self.running_goal(slug="far", store=os.path.join(other, ".claude", "mama"))
        self.running_goal(slug="near", sid="sess-x")  # someone else's, in the cwd's store
        ctx = json.loads(self.hook("sessionstart"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("This session's goal is 'far'", ctx)
        self.assertIn("- near", ctx)
        self.assertIn("still marked running", json.loads(self.hook("stop"))["reason"])
        self.assertIn("keep: the slug 'far'", self.hook("precompact"))
        self.assertRegex(self.read(os.path.join(g, "log.md")), r"E\d+ \d\d:\d\d compaction \(auto\)\n")

    def test_most_recent_open_goal_is_this_sessions(self):
        self.running_goal(slug="first")
        self.running_goal(slug="second")
        ctx = json.loads(self.hook("sessionstart"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("This session's goal is 'second'", ctx)
        self.assertIn("also touched open goal(s): first", ctx)

    def test_transcript_fallback_only_for_unrecorded_goals(self):
        g = self.running_goal(slug="old", sid=None)  # from before activity records
        self.write_transcript("sess-b", g)
        ctx = json.loads(self.hook("sessionstart", sid="sess-b"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("This session's goal is 'old'", ctx)
        # the compaction line is an event, not a write: it records nothing, even with a session id set
        self.assertIn("keep: the slug 'old'", self.hook("precompact", sid="sess-b", env_sid="sess-b"))
        self.assertIn("compaction (auto)", self.read(os.path.join(g, "log.md")))
        self.assertNotIn("sess-b", self.activity())

    def test_old_git_without_path_format(self):
        if os.name == "nt":
            self.skipTest("shell shim")
        real = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
        self.running_goal(sid=None)  # found only via the cwd's store, so main_checkout must work
        self.write_transcript("sess-b", os.path.join(self.store, "demo"))
        shims = {  # git < 2.31: rejects --path-format, or (rev-parse) echoes it back unparsed
            "fail": 'for a in "$@"; do case "$a" in --path-format=*) echo "unknown" >&2; exit 129;; esac; done',
            "echo": 'n=$#; for a in "$@"; do case "$a" in --path-format=*) echo "$a";; *) set -- "$@" "$a";; esac; done; shift $n',
        }
        for name, body in shims.items():
            d = os.path.join(self.tmp, f"git-{name}")
            os.makedirs(d)
            with open(os.path.join(d, "git"), "w") as f:
                f.write(f'#!/bin/sh\n{body}\nexec {real} "$@"\n')
            os.chmod(os.path.join(d, "git"), 0o755)
            out = self.hook("sessionstart", sid="sess-b", cwd=os.path.join(self.repo, ".claude"), path=d)
            self.assertIn("This session's goal is 'demo'", out, name)


class Stop(HookBase):
    def test_same_problems_block_once_changed_block_again(self):
        g = self.running_goal()
        self.assertIn("still marked running", json.loads(self.hook("stop"))["reason"])
        self.assertEqual(self.hook("stop"), "")  # nothing changed: no second block
        self.run_s("log.py", os.path.join(g, "log.md"), "D", "pick x | tag: user")
        reason = json.loads(self.hook("stop"))["reason"]  # the list changed
        self.assertIn("nothing was learned", reason)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "learn none")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.assertEqual(self.hook("stop"), "")
        self.assertFalse(os.path.exists(os.path.join(g, ".last-block")))
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "agent back")
        self.assertIn("still marked running", json.loads(self.hook("stop"))["reason"])  # came back: blocks again

    def test_quick_goal_has_no_learn_nag(self):
        g = self.run_s("new-goal.py", self.store, "q", "fix", "t", "--quick").splitlines()[0]
        self.run_s("log.py", os.path.join(g, "log.md"), "D", "pick x | tag: user")
        self.run_s("plan-set.py", self.plan(g), "--header", "status=waiting")
        os.utime(os.path.join(g, "overview.md"))
        out = self.hook("stop")
        self.assertNotIn("nothing was learned", out)

    def test_budget_written_under_plan_lock(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        os.makedirs(os.path.dirname(self.transcript("sess-a")), exist_ok=True)
        with open(self.transcript("sess-a"), "w") as f:
            now = datetime.datetime.now()  # not NOW: the goal started after this module loaded
            f.write(json.dumps({"type": "assistant", "timestamp": utc(now), "message": {
                "id": "m1", "usage": {"input_tokens": 40000, "output_tokens": 2000}, "content": []}}) + "\n")
        self.hook("stop")
        self.assertRegex(self.read(self.plan(g)), r"budget: ~42k /")
        self.assertTrue(os.path.exists(os.path.join(g, ".plan.lock")))

    def test_errors_exit_0_and_are_logged(self):
        self.assertEqual(self.hook("stop", raw="[1, 2]"), "")
        errs = self.read(os.path.join(self.home, ".claude", "mama", "hook-errors.log")).splitlines()
        self.assertEqual(len(errs), 1)
        self.assertRegex(errs[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d stop AttributeError: ")

    def test_fast_on_a_big_transcript(self):
        g = self.running_goal()
        self.write_transcript("sess-a", g, extra=60000)  # ~30 MB
        t = time.time()
        for mode in ("stop", "sessionstart", "precompact"):
            self.hook(mode)
        self.assertLess((time.time() - t) / 3, 3)


if __name__ == "__main__":
    unittest.main()
