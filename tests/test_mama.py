#!/usr/bin/env python3
"""mama's scripts and hooks, tested in a throwaway HOME. Run: python3 tests/test_mama.py
(runs every tests/test_*.py; scaffolding lives in tests/helpers.py).

Never touches the real ~/.claude: every script runs with HOME set to a temp dir and a fake
CLAUDE_CODE_SESSION_ID.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

if __name__ == "__main__" and os.name == "nt" and not sys.flags.utf8_mode:  # goal files are UTF-8; Windows defaults to cp1252
    sys.exit(subprocess.call([sys.executable, "-X", "utf8", *sys.argv]))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import HOOK, NOW, S, SKILL, Base, utc  # noqa: E402,F401


class NewGoalAndLog(Base):
    def test_clean_plan_and_first_log_line(self):
        g = self.new_goal()
        head = self.read(self.plan(g)).split("## ")[0]
        self.assertNotIn("<", head, head)
        self.assertIn("status: planning", head)
        self.assertRegex(self.read(os.path.join(g, "log.md")), r"^E1 \d\d:\d\d start build from test\n$")
        self.assertNotIn("<!--", self.read(os.path.join(g, "overview.md")))

    def test_taken_slug_gets_suffix(self):
        self.new_goal()
        self.assertEqual(os.path.basename(self.new_goal()), "demo-2")

    def test_log_ids_per_kind(self):
        g = self.new_goal()
        log = os.path.join(g, "log.md")
        self.run_s("log.py", log, "D", "pick x | tag: user")
        self.run_s("log.py", log, "E", "dispatch S1")
        out = self.run_s("log.py", log, "D", "pick y")
        self.assertRegex(out, r"^D2 \d\d:\d\d pick y")
        self.assertIn("E2 ", self.read(log))


class PlanSet(Base):
    def setUp(self):
        super().setUp()
        self.g = self.new_goal()
        self.fill_steps(self.g)
        self.p = self.plan(self.g)

    def test_running_needs_mode(self):
        self.assertIn("REFUSED", self.run_s("plan-set.py", self.p, "--header", "status=running", ok=False))
        self.run_s("plan-set.py", self.p, "--header", "status=running", "mode=autonomous")
        self.assertIn("status: running", self.read(self.p))

    def test_step_times_stamped(self):
        self.run_s("plan-set.py", self.p, "S1", "status=running")
        row = next(l for l in self.read(self.p).splitlines() if l.startswith("| S1"))
        self.assertRegex(row, r"\| running \| 0 \| 10m \| \d\d:\d\d \|")

    def test_end_before_start_refused(self):
        self.run_s("plan-set.py", self.p, "S1", "start=10:00")
        self.assertIn("REFUSED", self.run_s("plan-set.py", self.p, "S1", "end=09:00", ok=False))

    def test_add_rows(self):
        out = self.run_s("plan-set.py", self.p, "S+", "kind=fix", "title=t", "deps=S1", "verify=go test")
        self.assertIn("ADDED | S2 |", out)
        self.assertIn("needs verify", self.run_s("plan-set.py", self.p, "S+", "title=t", ok=False))
        self.assertIn("unknown deps", self.run_s("plan-set.py", self.p, "S+", "title=t", "verify=v", "deps=S9", ok=False))
        self.assertIn("ADDED | C2 |", self.run_s("plan-set.py", self.p, "C+", "criterion=c", "proven by=S2"))
        self.assertIn("progress: 0/2", self.read(self.p))

    def test_dep_warning(self):
        self.run_s("plan-set.py", self.p, "S+", "title=t", "deps=S1", "verify=v")
        self.assertIn("WARNING", self.run_s("plan-set.py", self.p, "S2", "status=running"))

    def test_budget_keeps_measured_spend(self):
        s = self.read(self.p).replace("budget: ~0k", "budget: ~120k")
        open(self.p, "w").write(s)
        self.run_s("plan-set.py", self.p, "--header", "budget=~5k / M")
        self.assertIn("budget: ~120k / M", self.read(self.p))
        self.assertIn("REFUSED", self.run_s("plan-set.py", self.p, "--header", "budget=~0k / L", ok=False))

    def test_done_refused_until_close_check_passes(self):
        out = self.run_s("plan-set.py", self.p, "--header", "status=done", ok=False)
        self.assertIn("can't close", out)


class Activity(Base):
    def test_writes_record_session_switches_once(self):
        a, b = self.new_goal("one"), self.new_goal("two")
        self.run_s("log.py", os.path.join(a, "log.md"), "E", "x")
        self.run_s("log.py", os.path.join(a, "log.md"), "E", "y")
        self.run_s("log.py", os.path.join(b, "log.md"), "E", "z", sid="sess-b")
        lines = self.read(os.path.join(self.home, ".claude", "mama", "activity.log")).splitlines()
        # one: created (a) · two: created (a) · one: back to it (a) · two (b)
        a, b = os.path.realpath(a), os.path.realpath(b)  # recorded resolved (macOS /var, Windows 8.3 names)
        self.assertEqual([l.split(" ", 2)[1:] for l in lines],
                         [["sess-a", a], ["sess-a", b], ["sess-a", a], ["sess-b", b]])

    def test_no_session_id_records_nothing(self):
        self.new_goal(sid=None)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "mama", "activity.log")))


class Learn(Base):
    def learn(self, *a, ok=True):
        return self.run_s("learn.py", *a, ok=ok)

    def patterns(self):
        return self.read(os.path.join(self.home, ".claude", "mama", "patterns.md"))

    def test_promoted_at_three(self):
        for _ in range(2):
            self.learn("seen", "Picks autonomous mode")
        self.assertRegex(self.patterns(), r"## Watching.*\n- Picks autonomous mode — 2/2")
        self.learn("seen", "Picks autonomous mode")
        self.assertRegex(self.patterns(), r"## How you like things done\n+- Picks autonomous mode — 3/3")

    def test_stated_survives_contra(self):
        self.learn("stated", "No co-author lines")
        out = self.learn("contra", "No co-author lines")
        self.assertIn("NOTE", out)
        self.assertIn("No co-author lines — stated", self.patterns())

    def test_contra_unknown_and_drop(self):
        self.assertIn("not found", self.learn("contra", "never seen", ok=False))
        self.learn("seen", "X")
        self.assertIn("dropped", self.learn("contra", "X"))  # 1/1 then contradicted → 0/2 → gone
        self.assertNotIn("- X —", self.patterns())


class Spend(Base):
    def transcript(self, sid, msgs, sub=None):
        d = os.path.join(self.home, ".claude", "projects", "p")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{sid}.jsonl")
        with open(path, "w") as f:
            for t, mid, tokens in msgs:
                f.write(json.dumps({"type": "assistant", "timestamp": utc(t), "message": {"id": mid, "usage": {
                    "input_tokens": tokens, "cache_creation_input_tokens": 0, "output_tokens": 0,
                    "cache_read_input_tokens": 999999}}}) + "\n")
        if sub:
            sd = os.path.join(d, sid, "subagents")
            os.makedirs(sd, exist_ok=True)
            with open(os.path.join(sd, "agent-1.jsonl"), "w") as f:
                for t, mid, tokens in sub:
                    f.write(json.dumps({"type": "assistant", "timestamp": utc(t), "message": {"id": mid, "usage": {
                        "input_tokens": tokens}}}) + "\n")
        return path

    def activity(self, rows):
        with open(os.path.join(self.home, ".claude", "mama", "activity.log"), "w") as f:
            for t, sid, goal in rows:
                f.write(f"{t.isoformat(timespec='seconds')} {sid} {goal}\n")

    def measure(self, goal):
        code = (f"import sys; sys.path.insert(0, {S!r}); import spend; "
                f"print(spend.measure({self.plan(goal)!r}))")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=self.env(None))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_counts_only_while_goal_is_current(self):
        a, b = self.new_goal("one", sid=None), self.new_goal("two", sid=None)
        start = NOW - datetime.timedelta(minutes=30)
        for g in (a, b):
            p = self.plan(g)
            s = re.sub(r"started: .*", f"started: {start:%Y-%m-%d %H:%M}", self.read(p))
            open(p, "w").write(s)
        m = lambda k: start + datetime.timedelta(minutes=k)
        self.activity([(m(1), "sess-a", a), (m(10), "sess-a", b)])
        self.transcript("sess-a", [(m(2), "m1", 100), (m(3), "m1", 100), (m(5), "m2", 50), (m(12), "m3", 7000)],
                        sub=[(m(4), "s1", 30)])
        self.assertEqual(self.measure(a), "180")   # m1 once + m2 + subagent; cache reads excluded
        self.assertEqual(self.measure(b), "7000")

    def test_session_older_than_the_record(self):
        """Goals written before activity.log existed keep their spend (read from the transcript)."""
        a, b = self.new_goal("old", sid=None), self.new_goal("new", sid=None)
        start = NOW - datetime.timedelta(minutes=30)
        for g in (a, b):
            p = self.plan(g)
            text = re.sub(r"started: .*", f"started: {start:%Y-%m-%d %H:%M}", self.read(p))
            open(p, "w").write(text)
        m = lambda k: start + datetime.timedelta(minutes=k)
        path = self.transcript("sess-a", [(m(2), "m1", 100), (m(12), "m2", 5000)])
        with open(path, "a") as f:  # an old-style write to goal `old` at m1, before any record
            f.write(json.dumps({"type": "assistant", "timestamp": utc(m(1)), "message": {"id": "w", "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": f"python3 x/log.py {a}/log.md E go"}}]}}) + "\n")
        lines = open(path).read().splitlines()
        open(path, "w").write("\n".join([lines[-1]] + lines[:-1]) + "\n")
        self.activity([(m(10), "sess-a", b)])
        self.assertEqual(self.measure(a), "100")
        self.assertEqual(self.measure(b), "5000")

    def test_unrecorded_goal_has_no_spend(self):
        self.assertEqual(self.measure(self.new_goal(sid=None)), "None")


class WrittenSlugs(unittest.TestCase):
    def slugs(self, name, inp):
        sys.path.insert(0, S)
        import spend
        line = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "input": inp}]}})
        return spend.written_slugs(line + "\n")

    def test_shell_forms(self):
        G = "/r/.claude/mama/goal-a"
        self.assertEqual(self.slugs("Bash", {"command": f'G={G}; python3 x/log.py $G/log.md E "a"'}), ["goal-a"])
        self.assertEqual(self.slugs("Bash", {"command": f'cd {G} && python3 x/log.py log.md E "a"'}), ["goal-a"])
        self.assertEqual(self.slugs("Bash", {"command": f"tail -5 {G}/log.md 2>&1"}), [])
        self.assertEqual(self.slugs("Bash", {"command": f"cd ~/.claude/skills/mama && python3 scripts/plan-set.py {G}/plan.md S1 a=b"}), [])
        self.assertEqual(self.slugs("Bash", {"command": "cat /r/.claude/mama/profile.md > /tmp/x"}), [])

    def test_windows_paths(self):
        self.assertEqual(self.slugs("Write", {"file_path": "C:\\Users\\A B\\r\\.claude\\mama\\goal-w\\plan.md"}), ["goal-w"])
        self.assertEqual(self.slugs("Bash", {"command": "python x\\log.py C:\\r\\.claude\\mama\\goal-x\\log.md E go"}), ["goal-x"])
        self.assertEqual(self.slugs("Bash", {"command": "cat C:\\r\\.claude\\mama\\goal-z\\log.md"}), [])

    def test_file_tools(self):
        self.assertEqual(self.slugs("Write", {"file_path": "/r/.claude/mama/goal-b/overview.md"}), ["goal-b"])
        self.assertEqual(self.slugs("Write", {"file_path": "/r/.claude/mama/goal-b/tests.md"}), [])


class Hook(Base):
    def hook(self, mode, sid="sess-a"):
        inp = {"cwd": self.repo, "session_id": sid,
               "transcript_path": os.path.join(self.home, ".claude", "projects", "p", f"{sid}.jsonl")}
        r = subprocess.run([sys.executable, HOOK, mode], input=json.dumps(inp), capture_output=True,
                           text=True, env=self.env(None))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def running_goal(self):
        g = self.new_goal()
        self.fill_steps(g)
        self.run_s("plan-set.py", self.plan(g), "--header", "status=running", "mode=autonomous")
        os.utime(os.path.join(g, "overview.md"))  # overview fresh
        return g

    def test_blocks_running_without_wait(self):
        self.running_goal()
        out = json.loads(self.hook("stop"))
        self.assertEqual(out["decision"], "block")
        self.assertIn("still marked running", out["reason"])

    def test_wait_line_lets_turn_end(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait S1 agent")
        os.utime(os.path.join(g, "overview.md"))
        self.assertEqual(self.hook("stop"), "")

    def test_other_session_is_left_alone(self):
        self.running_goal()
        self.assertEqual(self.hook("stop", sid="sess-other"), "")
        self.assertNotIn("This session's goal", self.hook("sessionstart", sid="sess-other"))

    def test_stale_overview_and_unlearned(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "D", "pick x | tag: user")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        old = time.time() - 60
        os.utime(os.path.join(g, "overview.md"), (old, old))
        reason = json.loads(self.hook("stop"))["reason"]
        self.assertIn("regenerate overview.md", reason)
        self.assertIn("nothing was learned", reason)

    def test_sessionstart_names_own_goal(self):
        self.running_goal()
        out = json.loads(self.hook("sessionstart"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("This session's goal is 'demo'", out)

    def test_closed_goal_idle_is_silent(self):
        g = self.running_goal()
        p = self.plan(g)
        open(p, "w").write(self.read(p).replace("status: running", "status: done"))
        old = time.time() - 7200
        os.utime(os.path.join(g, "log.md"), (old, old))
        self.assertEqual(self.hook("stop"), "")


class CloseCheck(Base):
    def ready_goal(self):
        g = self.new_goal()
        self.fill_steps(g)
        p = self.plan(g)
        self.run_s("plan-set.py", p, "--header", "mode=autonomous", "base=main", "branch=feat/x",
                   "worktree=n/a", "pr=none", "deliverable commit=n/a", "trello=none", "budget=~0k / S")
        self.run_s("plan-set.py", p, "S1", "status=running")
        self.run_s("plan-set.py", p, "S1", "status=done")
        self.run_s("plan-set.py", p, "C1", "evidence=go test ok")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "hunt 1: 2 found, 0 real, 0 fixed — /code-review high")
        open(os.path.join(g, "overview.md"), "w").write("# Demo\n\n**Status:** Done\n\n## Final report\n\nok\n")
        open(os.path.join(self.store, "lessons.md"), "w").write(
            f"- {datetime.date.today()} demo build | steps 1 | tokens est S / ~0k\n")
        open(os.path.join(self.store, "profile.md"), "w").write("repo facts\n")
        open(os.path.join(self.home, ".claude", "mama", "patterns.md"), "a").write("# How you work\n")
        return g

    def test_ready_goal_passes_and_closes(self):
        g = self.ready_goal()
        self.assertIn("OK", self.run_s("close-check.py", g))
        mark, old = os.path.join(g, ".milestone"), time.time() - 30
        os.utime(mark, (old, old))
        self.run_s("plan-set.py", self.plan(g), "--header", "status=done")
        self.assertIn("**Status:** Done · 1 of 1 parts done", self.read(os.path.join(g, "overview.md")))
        self.assertAlmostEqual(os.path.getmtime(mark), old, delta=1)  # closing asks for no overview rewrite

    def test_missing_evidence_and_report(self):
        g = self.ready_goal()
        self.run_s("plan-set.py", self.plan(g), "C1", "evidence=—")
        open(os.path.join(g, "overview.md"), "w").write("# Demo\n")
        out = self.run_s("close-check.py", g, ok=False)
        self.assertIn("C1 has no evidence", out)
        self.assertIn("no **Status:**", out)
        self.assertIn("no ## Final report", out)


class Lean(Base):
    def cc(self):
        sys.path.insert(0, S)
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", os.path.join(S, "close-check.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_quick_goal_closes_without_bookkeeping(self):
        out = self.run_s("new-goal.py", self.store, "tiny", "fix", "t", "--quick")
        g = out.splitlines()[0]
        self.assertNotIn("Overview rules", out)
        self.assertIn("mode: quick", self.read(self.plan(g)))
        self.fill_steps(g)
        p = self.plan(g)
        self.run_s("plan-set.py", p, "--header", "base=n/a", "branch=n/a", "worktree=n/a", "pr=none",
                   "deliverable commit=n/a", "trello=none", "budget=~0k / S")
        self.run_s("plan-set.py", p, "S1", "status=running")
        self.run_s("plan-set.py", p, "S1", "status=done")
        self.run_s("plan-set.py", p, "C1", "evidence=go test ok")
        open(os.path.join(g, "overview.md"), "w").write("# Tiny\n\n**Status:** Done · 1 of 1\n")
        self.assertIn("no bug hunt logged", self.run_s("close-check.py", g, ok=False))
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "hunt 1: 1 found, 1 real, 1 fixed — /code-review low")  # one light round
        self.assertIn("OK", self.run_s("close-check.py", g))  # no lessons, profile or patterns needed

    def test_waiting_minutes(self):
        log = ("E1 09:40 start\nQ1 09:46 base?\nD1 09:46 PR ask (tag: user, from patterns)\n"
               "D2 09:57 main (tag: user)\nE2 10:00 waiting for the user\nE3 10:20 resume\n")
        self.assertEqual(self.cc().waiting_minutes(log), 31)

    def test_waiting_and_resume_are_logged(self):
        g = self.new_goal()
        self.fill_steps(g)
        p = self.plan(g)
        self.run_s("plan-set.py", p, "--header", "status=running", "mode=autonomous")
        self.run_s("plan-set.py", p, "--header", "status=waiting")
        self.run_s("plan-set.py", p, "--header", "status=running")
        log = self.read(os.path.join(g, "log.md"))
        self.assertRegex(log, r"E\d+ \d\d:\d\d waiting for the user\nE\d+ \d\d:\d\d resume\n")

    def test_commit_problems(self):
        origin = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
        git = lambda *a: subprocess.run(["git", "-C", self.repo, *a], check=True, capture_output=True)
        git("config", "user.email", "t@t"); git("config", "user.name", "t")
        git("commit", "-q", "--allow-empty", "-m", "init"); git("branch", "-M", "main")
        git("remote", "add", "origin", origin); git("push", "-q", "origin", "main")
        git("checkout", "-q", "-b", "feat/x")
        git("commit", "-q", "--allow-empty", "-m", "feat(api): add filter")
        g = self.new_goal()
        head = {"base": "main", "branch": "feat/x"}
        self.assertEqual(self.cc().commit_problems(g, head), [])
        git("commit", "-q", "--allow-empty", "-m", "fix: S3 per plan.md\n\nCo-Authored-By: Claude <x@y>")
        self.assertEqual(len(self.cc().commit_problems(g, head)), 1)


class Upgrades(Base):
    def mod(self, name, file):
        import importlib.util
        sys.path.insert(0, S)
        spec = importlib.util.spec_from_file_location(name, os.path.join(S, file))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_failed_write_keeps_old_file(self):
        fio = self.mod("fileio", "fileio.py")
        p = os.path.join(self.tmp, "patterns.md")
        open(p, "w").write("precious\n")

        real = os.fsync
        os.fsync = lambda fd: (_ for _ in ()).throw(OSError(28, "No space left on device"))
        try:
            with self.assertRaises(OSError):
                fio.write_atomic(p, "new text")
        finally:
            os.fsync = real
        self.assertEqual(self.read(p), "precious\n")
        self.assertEqual([f for f in os.listdir(self.tmp) if f.startswith(".tmp-")], [])
        fio.write_atomic(p, "new text")
        self.assertEqual(self.read(p), "new text")

    def test_overnight_gap_is_idle(self):
        cc = self.mod("cc", "close-check.py")
        log = ("E1 17:00 start\nE2 17:30 wait agent\nE3 18:28 agent done\n"
               "D1 09:11 continue | tag: user\nE4 09:40 done\n")
        self.assertEqual(cc.waiting_minutes(log), (24 * 60 - 18 * 60 - 28) + 9 * 60 + 11)
        # a long agent run with log lines inside two hours is work, not idle
        self.assertEqual(cc.waiting_minutes("E1 13:26 wait merge agent\nE2 14:52 merge done\n"), 0)

    def test_repeated_wait_line_written_once(self):
        g = self.new_goal()
        log = os.path.join(g, "log.md")
        for _ in range(3):
            self.run_s("log.py", log, "E", "wait S5 API agent")
        self.run_s("log.py", log, "E", "wait final gate")
        self.assertEqual(len(re.findall(r"wait S5 API agent", self.read(log))), 1)
        self.assertEqual(len(re.findall(r"wait final gate", self.read(log))), 1)

    def test_precompact_logs_compaction(self):
        g = self.new_goal()
        self.fill_steps(g)
        self.run_s("plan-set.py", self.plan(g), "--header", "status=running", "mode=autonomous")
        inp = {"cwd": self.repo, "session_id": "sess-a", "trigger": "auto",
               "transcript_path": os.path.join(self.home, ".claude", "projects", "p", "sess-a.jsonl")}
        r = subprocess.run([sys.executable, HOOK, "precompact"], input=json.dumps(inp), capture_output=True,
                           text=True, env=self.env(None))
        self.assertIn("keep: the slug 'demo'", r.stdout)
        self.assertRegex(self.read(os.path.join(g, "log.md")), r"E\d+ \d\d:\d\d compaction \(auto\)\n")
        cc = subprocess.run([sys.executable, os.path.join(S, "close-check.py"), g], capture_output=True,
                            text=True, env=self.env())
        self.assertIn("compactions 1", cc.stdout)


class PlanAndOverview(Base):
    def rows(self, p, prefix):
        return [l for l in self.read(p).splitlines() if re.match(rf"\| {prefix}\d", l)]

    def test_added_rows_fill_the_blank_template_row(self):
        g = self.new_goal()
        p = self.plan(g)
        self.assertIn("ADDED | C1 | works |", self.run_s("plan-set.py", p, "C+", "criterion=works", "proven by=S1"))
        self.assertIn("ADDED | S1 | build | a |", self.run_s("plan-set.py", p, "S+", "kind=build", "title=a", "verify=v", "est=10m"))
        self.assertIn("ADDED | S2 |", self.run_s("plan-set.py", p, "S+", "title=b", "deps=S1", "verify=v"))
        self.assertEqual(len(self.rows(p, "C")), 1)
        self.assertEqual(len(self.rows(p, "S")), 2)
        self.assertIn("progress: 0/2", self.read(p))

    def test_park(self):
        g = self.new_goal()
        p = self.plan(g)
        self.run_s("plan-set.py", p, "P+", "text=student side: no design yet")
        self.run_s("plan-set.py", p, "P+", "text=categories")
        parked = self.read(p).split("## Parked", 1)[1]
        self.assertEqual(re.findall(r"^- .*$", parked, re.M), ["- student side: no design yet", "- categories"])
        self.assertNotIn("<", parked)
        self.assertIn("REFUSED", self.run_s("plan-set.py", p, "P+", "text= ", ok=False))

    def test_approval_needs_research(self):
        g = self.new_goal()
        p, log = self.plan(g), os.path.join(g, "log.md")
        self.run_s("plan-set.py", p, "S+", "title=a", "verify=v")
        self.run_s("plan-set.py", p, "--header", "status=waiting")
        out = self.run_s("plan-set.py", p, "--header", "status=running", "mode=autonomous", ok=False)
        self.assertIn("no research recorded", out)
        self.run_s("log.py", log, "E", "research none: one-line config change")
        self.run_s("log.py", log, "E", "expectations: 9 settled, 0 asked")
        self.run_s("log.py", log, "E", "playback: confirmed")
        self.run_s("plan-set.py", p, "--header", "status=running", "mode=autonomous", "budget=S")
        q = self.new_goal("tiny")  # quick goals skip research and expectations
        self.run_s("plan-set.py", self.plan(q), "S+", "title=a", "verify=v")
        self.run_s("log.py", os.path.join(q, "log.md"), "E", "playback: confirmed")
        self.run_s("plan-set.py", self.plan(q), "--header", "status=running", "mode=quick")

    def test_added_row_stamps_now_and_runs_guards(self):
        g = self.new_goal()
        self.fill_steps(g)
        p = self.plan(g)
        out = self.run_s("plan-set.py", p, "S+", "title=t", "verify=v", "status=running", "deps=S1")
        self.assertIn("WARNING: S2 started before its deps", out)
        self.assertRegex(self.rows(p, "S")[1], r"\| running \| 0 \|  \| \d\d:\d\d \|")
        self.run_s("plan-set.py", p, "S+", "title=t", "verify=v", "start=now")
        self.assertNotIn("now", self.rows(p, "S")[2])
        self.assertIn("REFUSED", self.run_s("plan-set.py", p, "S+", "title=t", "verify=v", "start=10:00", "end=09:00", ok=False))

    def test_status_line_synced_milestones_marked(self):
        g = self.new_goal()
        self.fill_steps(g)
        p, ov, mark = self.plan(g), os.path.join(g, "overview.md"), os.path.join(g, ".milestone")
        self.assertTrue(os.path.exists(mark))
        self.run_s("plan-set.py", p, "--header", "status=running", "mode=autonomous")
        self.assertIn("**Status:** Working · 0 of 1 parts done\n", self.read(ov))

        s = self.read(ov).replace("0 of 1 parts done", "0 of 1 parts done · building the thing")
        open(ov, "w").write(s)
        old = time.time() - 60
        os.utime(ov, (old, old))
        os.utime(mark, (old - 60, old - 60))
        self.run_s("plan-set.py", p, "S1", "status=running")  # not a milestone
        self.run_s("plan-set.py", p, "S1", "notes=x")
        self.assertIn("· building the thing", self.read(ov))
        self.assertAlmostEqual(os.path.getmtime(ov), old, delta=1)  # synced, prose still counts as old
        self.assertLess(os.path.getmtime(mark), old)

        self.run_s("plan-set.py", p, "S1", "notes=x ★")
        self.run_s("plan-set.py", p, "S1", "status=done")  # a ★ step done: a milestone
        self.assertGreater(os.path.getmtime(mark), old)
        self.run_s("plan-set.py", p, "--header", "status=waiting")
        self.assertIn("**Status:** Waiting for you · 1 of 1 parts done\n", self.read(ov))  # stale detail dropped

        m = time.time() - 30
        os.utime(mark, (m, m))
        self.run_s("plan-set.py", p, "--header", "status=running")
        self.assertGreater(os.path.getmtime(mark), m + 1)  # a status change is a milestone

    def test_hook_asks_for_overview_only_after_a_milestone(self):
        g = self.new_goal()
        self.fill_steps(g)
        p, ov, mark = self.plan(g), os.path.join(g, "overview.md"), os.path.join(g, ".milestone")
        self.run_s("plan-set.py", p, "--header", "status=running", "mode=autonomous")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        old = time.time() - 60
        os.utime(mark, (old - 60, old - 60))
        os.utime(ov, (old, old))
        self.run_s("plan-set.py", p, "S1", "status=running")
        hook = Hook.hook.__get__(self)
        self.assertEqual(hook("stop"), "")
        self.run_s("plan-set.py", p, "S1", "status=blocked")
        self.assertIn("regenerate overview.md", json.loads(hook("stop"))["reason"])

    def test_resource_limits(self):
        r = subprocess.run([sys.executable, os.path.join(S, "resources.py"), "20"], capture_output=True, text=True)
        m = dict(re.findall(r"(\w+)=([\d.]+)", r.stdout))
        self.assertEqual(m["read_limit"], "8")
        self.assertTrue(1 <= int(m["limit"]) <= 8)
        r = subprocess.run([sys.executable, os.path.join(S, "resources.py"), "2"], capture_output=True, text=True)
        self.assertIn("read_limit=2", r.stdout)

    def test_critical_path_not_sum(self):
        sys.path.insert(0, S)
        import estimate
        steps = [("S1", "—", "10m", "done"), ("S2", "S1", "20m", "todo"), ("S3", "—", "30m", "todo"),
                 ("S4", "S2,S3", "5m", "todo"), ("S5", "S1-S4", "1h", "obsolete"), ("S6", "S7", "5m", "todo"),
                 ("S7", "S6", "5m", "todo")]
        self.assertEqual(estimate.critical_path(steps), 35)  # max(10+20, 30) + 5; S6<->S7 cycle cut
        self.assertEqual(estimate.total(steps), 75)
        self.assertEqual(estimate.critical_path(steps, left=True), 35)
        self.assertEqual(estimate.minutes("1h 20m"), 80)
        self.assertEqual(estimate.width(steps), 3)  # S1, S3 and S7 (its cycle with S6 cut) at once
        wide = [("S1", "—", "5m", "todo")] + [(f"S{i}", "S1", "20m", "todo") for i in range(2, 7)]
        self.assertEqual((estimate.width(wide), estimate.critical_path(wide)), (5, 25))
        self.assertEqual(estimate.width([("S1", "—", "5m", "todo"), ("S2", "S1", "5m", "todo")]), 1)
        g = self.new_goal()
        self.fill_steps(g)
        out = self.run_s("plan-set.py", self.plan(g), "S+", "title=t", "verify=v", "est=20m")
        self.assertIn("estimate: critical path 20m (sum 30m, up to 2 at once)", out)
        cc = subprocess.run([sys.executable, os.path.join(S, "close-check.py"), g], capture_output=True,
                            text=True, env=self.env())
        self.assertIn("time est 20m critical path (sum 30m)", cc.stdout)



class Install(Base):
    def test_install_is_idempotent_and_removable(self):
        settings = os.path.join(self.home, ".claude", "settings.json")
        open(settings, "w").write(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo other"}]}]}}))
        run = lambda *a: subprocess.run([sys.executable, os.path.join(SKILL, "install.py"), *a], capture_output=True, text=True, env=self.env(None))
        for _ in range(2):
            self.assertEqual(run().returncode, 0)
        s = json.load(open(settings))
        self.assertEqual(s["model"], "x")
        self.assertEqual([sum("mama-hook.py" in json.dumps(e) for e in s["hooks"][k]) for k in ("PreCompact", "SessionStart", "Stop")], [1, 1, 1])
        self.assertEqual(len(s["hooks"]["Stop"]), 2)
        mine = s["hooks"]["SessionStart"][0]
        self.assertEqual((mine["matcher"], mine["hooks"][0]["command"], mine["hooks"][0]["args"][1]),
                         ("compact", sys.executable, "sessionstart"))  # exec form: no shell, no ~
        self.assertEqual(os.path.realpath(os.path.join(self.home, ".claude", "skills", "mama")), os.path.realpath(SKILL))
        self.assertEqual(run("--remove").returncode, 0)
        self.assertEqual(json.load(open(settings))["hooks"], {"Stop": [{"hooks": [{"type": "command", "command": "echo other"}]}]})


class Portable(Base):
    @unittest.skipIf(os.name == "nt", "symlinked folders are a POSIX case")
    def test_goal_found_through_a_symlinked_path(self):
        # macOS: /var is /private/var — git reports the resolved path, scripts may get the other one
        link = os.path.join(self.tmp, "link")
        os.symlink(self.repo, link)
        g = self.run_s("new-goal.py", os.path.join(link, ".claude", "mama"), "demo", "build", "t").splitlines()[0]
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "research none: test")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "expectations: 9 settled, 0 asked")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "playback: confirmed")
        self.run_s("plan-set.py", os.path.join(g, "plan.md"), "S+", "title=a", "verify=v")
        self.run_s("plan-set.py", os.path.join(g, "plan.md"), "--header", "status=running", "mode=autonomous", "budget=S")
        out = json.loads(Hook.hook.__get__(self)("sessionstart"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("This session's goal is 'demo'", out)

    def test_lock_serializes_and_passes_exit_code(self):
        lock, out = os.path.join(self.tmp, "x.lock"), os.path.join(self.tmp, "order.txt")
        writer = "import sys,time;f=open(sys.argv[1],'a');f.write(sys.argv[2]+'-in ');f.flush();time.sleep(float(sys.argv[3]));f.write(sys.argv[2]+'-out ')"
        a = subprocess.Popen([sys.executable, os.path.join(S, "lock.py"), lock, sys.executable, "-c", writer, out, "A", "0.8"])
        time.sleep(0.3)
        subprocess.run([sys.executable, os.path.join(S, "lock.py"), lock, sys.executable, "-c", writer, out, "B", "0"])
        a.wait()
        self.assertEqual(self.read(out).split(), ["A-in", "A-out", "B-in", "B-out"])
        r = subprocess.run([sys.executable, os.path.join(S, "lock.py"), lock, sys.executable, "-c", "raise SystemExit(3)"])
        self.assertEqual(r.returncode, 3)

if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore", ResourceWarning)
    here = os.path.dirname(os.path.abspath(__file__))
    suite = unittest.defaultTestLoader.discover(here, pattern="test_*.py", top_level_dir=here)
    sys.exit(not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful())
