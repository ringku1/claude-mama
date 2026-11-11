#!/usr/bin/env python3
"""mama's scripts and hooks, tested in a throwaway HOME. Run: python3 tests/test_mama.py

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

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(SKILL, "scripts")
HOOK = os.path.join(SKILL, "hooks", "mama-hook.py")
NOW = datetime.datetime.now()


def utc(dt):
    return dt.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".claude", "mama"))
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.store = os.path.join(self.repo, ".claude", "mama")

    def env(self, sid="sess-a"):
        e = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_SESSION")}
        e["HOME"] = self.home
        if sid:
            e["CLAUDE_CODE_SESSION_ID"] = sid
        return e

    def run_s(self, script, *args, sid="sess-a", ok=True):
        r = subprocess.run([sys.executable, os.path.join(S, script), *args],
                           capture_output=True, text=True, env=self.env(sid))
        if ok is True:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        elif ok is False:
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def new_goal(self, slug="demo", kind="build", sid="sess-a"):
        out = self.run_s("new-goal.py", self.store, slug, kind, "test", sid=sid)
        return out.splitlines()[0]

    def plan(self, goal):
        return os.path.join(goal, "plan.md")

    def read(self, path):
        return open(path, encoding="utf-8").read()

    def fill_steps(self, goal):
        """Replace the template step/criterion rows with real ones."""
        p = self.plan(goal)
        s = self.read(p)
        s = re.sub(r"^\| C1 .*$", "| C1  | it works | S1 | — |", s, flags=re.M)
        s = re.sub(r"^\| S1 .*$", "| S1  | build | thing | — | a.go | go test | todo | 0 | 10m |  |  |  |", s, flags=re.M)
        open(p, "w", encoding="utf-8").write(s)


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
        self.assertTrue(self.new_goal().endswith("/demo-2"))

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
        self.assertEqual([l.split()[1:] for l in lines],
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
        open(os.path.join(g, "overview.md"), "w").write("# Demo\n\n**Status:** Done\n\n## Final report\n\nok\n")
        open(os.path.join(self.store, "lessons.md"), "w").write(
            f"- {datetime.date.today()} demo build | steps 1 | tokens est S / ~0k\n")
        open(os.path.join(self.store, "profile.md"), "w").write("repo facts\n")
        open(os.path.join(self.home, ".claude", "mama", "patterns.md"), "a").write("# How you work\n")
        return g

    def test_ready_goal_passes_and_closes(self):
        g = self.ready_goal()
        self.assertIn("OK", self.run_s("close-check.py", g))
        self.run_s("plan-set.py", self.plan(g), "--header", "status=done")

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

    def test_overview_problems(self):
        cc = self.cc()
        self.assertEqual(cc.overview_problems("# Goal\n\n**Status:** Working\nFiles stored in S3."), [])
        out = cc.overview_problems("# Goal\nS4 is done, see store.go:185\n" + "line\n" * 70)
        self.assertEqual(len(out), 3, out)

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

        self.run_s("plan-set.py", p, "S1", "status=done")  # a milestone
        self.assertGreater(os.path.getmtime(mark), old)
        self.run_s("plan-set.py", p, "--header", "status=waiting")
        self.assertIn("**Status:** Waiting for you · 1 of 1 parts done\n", self.read(ov))  # stale detail dropped

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
        g = self.new_goal()
        self.fill_steps(g)
        out = self.run_s("plan-set.py", self.plan(g), "S+", "title=t", "verify=v", "est=20m")
        self.assertIn("estimate: critical path 20m (sum 30m)", out)
        cc = subprocess.run([sys.executable, os.path.join(S, "close-check.py"), g], capture_output=True,
                            text=True, env=self.env())
        self.assertIn("time est 20m critical path (sum 30m)", cc.stdout)


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore", ResourceWarning)
    unittest.main(verbosity=1)
