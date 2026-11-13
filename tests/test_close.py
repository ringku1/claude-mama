#!/usr/bin/env python3
"""close-check.py: this goal's commits only, overview flags, placeholders, metrics and clock time.
Run: python3 tests/test_close.py
"""
import datetime
import importlib.util
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import SKILL, S, HOOK, NOW, utc, Base  # noqa: E402,F401


def load_cc():
    sys.path.insert(0, S)
    spec = importlib.util.spec_from_file_location("cc", os.path.join(S, "close-check.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CloseBase(Base):
    def ready_goal(self, base="main", branch="feat/x"):
        g = self.new_goal()
        self.fill_steps(g)
        p = self.plan(g)
        self.run_s("plan-set.py", p, "--header", "mode=autonomous", f"base={base}", f"branch={branch}",
                   "worktree=n/a", "pr=none", "deliverable commit=n/a", "trello=none", "budget=~0k / S")
        self.run_s("plan-set.py", p, "S1", "status=running")
        self.run_s("plan-set.py", p, "S1", "status=done")
        self.run_s("plan-set.py", p, "C1", "evidence=go test ok")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "hunt 1: 2 found, 0 real, 0 fixed — /code-review high")
        open(os.path.join(g, "overview.md"), "w", encoding="utf-8").write(
            "# Demo\n\n**Status:** Done\n\n## Final report\n\nok\n")
        open(os.path.join(self.store, "lessons.md"), "w", encoding="utf-8").write(
            f"- {datetime.date.today()} demo build | steps 1 | tokens est S / ~0k\n")
        open(os.path.join(self.store, "profile.md"), "w", encoding="utf-8").write("repo facts\n")
        open(os.path.join(self.home, ".claude", "mama", "patterns.md"), "a", encoding="utf-8").write("# How you work\n")
        return g

    def test_bug_hunt_must_end_clean(self):
        g = self.ready_goal()
        log = os.path.join(g, "log.md")
        self.run_s("log.py", log, "E", "hunt 2: 4 found, 2 real, 2 fixed — /code-review high")
        out = self.close(g, ok=False)
        self.assertIn("the last bug hunt (round 2) found 2 real bug(s)", out)
        self.run_s("log.py", log, "E", "hunt 3: 1 found, 0 real, 0 fixed — /code-review high")
        out = self.close(g, ok=True)
        self.assertIn("hunt rounds 3 (real bugs 2)", out)  # metrics draft

    def test_known_issues_accepted_by_the_user_close(self):
        g = self.ready_goal()
        log = os.path.join(g, "log.md")
        self.run_s("log.py", log, "E", "hunt 4: 3 found, 1 real, 0 fixed — /code-review high")
        self.close(g, ok=False)
        self.run_s("log.py", log, "D", "deliver with 1 known issue listed in the report (tag: user)")
        self.assertIn("known issue", self.read(log))
        self.close(g, ok=False)  # "known issue" singular isn't the agreed marker
        self.run_s("log.py", log, "D", "deliver with known issues listed in the report (tag: user)")
        self.close(g, ok=True)

    def test_hunt_round_names_code_review(self):
        g = self.ready_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "hunt 2: 0 found, 0 real, 0 fixed (full suites pass)")
        self.assertIn("hunt round 2 doesn't name /code-review", self.close(g, ok=False))

    def test_push_before_the_hunt_refused_until_pushed_again(self):
        g = self.ready_goal()
        log = os.path.join(g, "log.md")
        self.run_s("log.py", log, "E", "pushed abc1234 to feat/x")
        self.run_s("log.py", log, "E", "hunt 2: 1 found, 0 real, 0 fixed — /code-review high")
        self.assertIn("the last push came before the last hunt", self.close(g, ok=False))
        self.run_s("log.py", log, "E", "push: feat/x up to date after the clean hunt")
        self.close(g, ok=True)

    def test_hunt_none_and_research_goals(self):
        g = self.ready_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "hunt none: no code changed")
        self.close(g, ok=True)
        r = self.run_s("new-goal.py", self.store, "study", "research", "t").splitlines()[0]
        self.assertNotIn("bug hunt", self.close(r))

    def close(self, g, ok=None):
        r = subprocess.run([sys.executable, os.path.join(S, "close-check.py"), g], capture_output=True,
                           text=True, env=self.env())
        if ok is True:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        elif ok is False:
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout + r.stderr


class Commits(CloseBase):
    BAD = "fix: S3 per plan.md\n\nCo-Authored-By: Claude <x@y>"

    def git(self, *a, when=None):
        env = dict(os.environ)
        if when:
            stamp = when.strftime("%Y-%m-%dT%H:%M:%S")
            env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
        return subprocess.run(["git", "-C", self.repo, *a], check=True, capture_output=True, env=env)

    def setup_repo(self):
        origin = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        old = NOW - datetime.timedelta(days=2)
        self.git("commit", "-q", "--allow-empty", "-m", "init", when=old)
        self.git("branch", "-M", "main")
        self.git("remote", "add", "origin", origin)
        self.git("push", "-q", "origin", "main")
        return old

    def problems(self, g):
        return [l for l in self.close(g).splitlines() if "attribution" in l]

    def test_continued_branch_ignores_commits_before_the_goal(self):
        old = self.setup_repo()
        self.git("checkout", "-q", "-b", "feat/x")
        self.git("commit", "-q", "--allow-empty", "-m", self.BAD, when=old)  # an earlier goal's, already pushed
        self.git("push", "-q", "origin", "feat/x")
        g = self.ready_goal()
        self.assertEqual(self.problems(g), [])
        self.assertIn("OK", self.close(g, ok=True))
        self.git("commit", "-q", "--allow-empty", "-m", self.BAD)
        self.assertEqual(len(self.problems(g)), 1)

    def test_work_on_base_branch_is_checked(self):
        old = self.setup_repo()
        self.git("commit", "-q", "--allow-empty", "-m", self.BAD, when=old)
        self.git("push", "-q", "origin", "main")
        g = self.ready_goal(base="main", branch="main")
        self.git("commit", "-q", "--allow-empty", "-m", "feat(api): add filter")
        self.assertEqual(self.problems(g), [])
        self.git("commit", "-q", "--allow-empty", "-m", self.BAD)
        out = self.problems(g)
        self.assertEqual(len(out), 1, out)
        self.assertEqual(len(re.findall(r"[0-9a-f]{9}", out[0])), 1, out)  # only the new one

    def test_loop_words_that_name_tracked_files_are_allowed(self):
        self.setup_repo()
        g = self.ready_goal(base="main", branch="main")
        self.git("commit", "-q", "--allow-empty", "-m", "fix: the plan.md parser")
        self.assertEqual(len(self.problems(g)), 1)  # plan.md isn't this repo's file: a loop internal
        os.makedirs(os.path.join(self.repo, "templates"), exist_ok=True)
        with open(os.path.join(self.repo, "templates", "plan.md"), "w") as f:
            f.write("x\n")
        self.git("add", "templates/plan.md")
        self.git("commit", "-q", "-m", "feat: add the plan template")
        self.assertEqual(self.problems(g), [])  # now it names a tracked file: product vocabulary

    def test_no_branch_skips(self):
        self.setup_repo()
        g = self.ready_goal(base="n/a", branch="n/a")
        self.git("commit", "-q", "--allow-empty", "-m", self.BAD)
        self.assertEqual(self.problems(g), [])


class Overview(CloseBase):
    def test_ids_only_when_the_goal_has_them(self):
        cc = load_cc()
        g = self.new_goal()
        self.fill_steps(g)  # plan has S1, C1; log has E1, E2
        clean = ("# Goal\n\n**Status:** Working\nQ4 numbers are in. Files go to S3.\n"
                 "Running at 127.0.0.1:8088, http://localhost:8088/x and api.example.com:443; "
                 "see [docs](https://x.io/a.md:12).\n")
        self.assertEqual(cc.overview_problems(clean, g), [])
        out = cc.overview_problems("# Goal\nS1 is done, see store.go:185\n" + "line\n" * 70, g)
        self.assertEqual(len(out), 3, out)
        self.assertIn("(S1)", out[0])
        self.assertEqual(cc.overview_problems("S1 and E2 done", None), [])  # no goal: IDs unchecked
        self.assertEqual(cc.overview_problems("`S1` in code, S1x, S1-alpha", g), [])

    def test_close_reports_known_ids(self):
        g = self.ready_goal()
        open(os.path.join(g, "overview.md"), "w", encoding="utf-8").write(
            "# Demo\n\n**Status:** Done\n\n## Final report\n\nC1 proven; server on localhost:8088 for Q4.\n")
        out = self.close(g, ok=False)
        self.assertIn("internal IDs (C1)", out)
        self.assertNotIn("file:line", out)


class Placeholders(CloseBase):
    def test_quoted_hh_mm_in_a_finding_is_fine(self):
        g = self.ready_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "F", "finding | template line reads `E1 HH:MM start` | t.md:1")
        self.assertIn("OK", self.close(g, ok=True))

    def test_template_line_flagged(self):
        g = self.ready_goal()
        with open(os.path.join(g, "log.md"), "a", encoding="utf-8") as f:
            f.write("E1 HH:MM start <goal type> from <input source>\n")
        self.assertIn("log.md still has template placeholders", self.close(g, ok=False))


class Metrics(CloseBase):
    def test_latest_metrics_line_for_the_slug(self):
        cc = load_cc()
        lessons = ("- 2026-01-01 demo build | steps 1 | tokens est S / ~40k\n"
                   "- 2026-01-02 demo-2 build | steps 1 | tokens est S / ~9k\n"
                   "- 2026-02-01 demo build | steps 3 | tokens est M / ~1.2M\n")
        self.assertEqual(cc.claimed_tokens(lessons, "demo"), ("1.2", "M"))
        self.assertIsNone(cc.claimed_tokens(lessons, "other"))

    def test_actual_time_across_days(self):
        cc = load_cc()
        start = datetime.datetime(2026, 1, 1, 22, 0)
        log = ("E1 22:00 start\nE2 23:50 wait agent\nE3 00:10 agent done\n"
               "-- 2026-01-03\nD1 09:00 go | tag: user\nE4 09:30 done\n")
        self.assertEqual(cc.actual_minutes(log, start), 2 * 1440 - 22 * 60 + 9 * 60 + 30)
        # 00:10 Jan 2 → 09:00 Jan 3 is one idle gap, not 8h50m
        self.assertEqual(cc.waiting_minutes(log, start), 1440 + 8 * 60 + 50)
        self.assertIsNone(cc.actual_minutes("", start))

    def test_metrics_line_uses_the_clock(self):
        g = self.ready_goal()
        p, log = self.plan(g), os.path.join(g, "log.md")
        started = datetime.datetime.strptime(re.search(r"started: (\S+ \S+)", self.read(p)).group(1), "%Y-%m-%d %H:%M")
        first = re.search(r"^E1 (\d\d:\d\d)", self.read(log), re.M).group(1)
        e1 = datetime.datetime.combine(started.date(), datetime.datetime.strptime(first, "%H:%M").time())
        nxt = e1 + datetime.timedelta(days=1, minutes=30)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"-- {nxt:%Y-%m-%d}\nE99 {nxt:%H:%M} done\n")
        minutes = int((nxt - e1).total_seconds() // 60)
        self.assertIn(f"actual {minutes}m", self.close(g))

    def test_step_end_before_start_left_to_plan_set(self):
        g = self.ready_goal()
        p = self.plan(g)
        s = re.sub(r"^(\| S1 .*)$", lambda m: re.sub(r"\| \d\d:\d\d \| \d\d:\d\d \|", "| 23:50 | 00:20 |", m.group(1)),
                   self.read(p), flags=re.M)
        open(p, "w", encoding="utf-8").write(s)
        self.assertNotIn("before it starts", self.close(g))


class Tables(unittest.TestCase):
    def test_one_parser(self):
        sys.path.insert(0, S)
        import estimate
        plan = ("## Criteria\n\n| id | criterion | evidence |\n| -- | -- | -- |\n| C1 | works | ok |\n|  | blank | |\n"
                "## Steps\n\n| id | deps | est | status |\n| -- | -- | -- | -- |\n| S1 | — | 5m | done |\n| S2 | S1 | 10m |\n")
        self.assertEqual(estimate.table(plan, "Criteria"), (["id", "criterion", "evidence"], [["C1", "works", "ok"]]))
        self.assertEqual(estimate.steps_of(plan), [("S1", "—", "5m", "done"), ("S2", "S1", "10m", "")])
        self.assertEqual(estimate.table(plan, "Parked"), ([], []))
        self.assertFalse(hasattr(load_cc(), "table"))  # close-check reuses estimate's parser


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore", ResourceWarning)
    unittest.main(verbosity=1, warnings="ignore")
