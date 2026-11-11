#!/usr/bin/env python3
"""plan-set.py guards: lock, budget forms, approval ceiling, midnight, PR values. Run: python3 tests/test_plan.py"""
import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import SKILL, S, HOOK, NOW, utc, Base  # noqa: E402,F401

sys.path.insert(0, S)
import fileio  # noqa: E402

HOOK_BUDGET = re.compile(r"(budget: )~?[^/|\n]*(/)")  # the Stop hook's write (hooks/mama-hook.py)


class PlanBase(Base):
    def setUp(self):
        super().setUp()
        self.g = self.new_goal()
        self.p = self.plan(self.g)
        self.run_s("log.py", os.path.join(self.g, "log.md"), "E", "research none: test")
        self.run_s("plan-set.py", self.p, "S+", "title=a", "verify=v")

    def ps(self, *args, ok=True):
        return self.run_s("plan-set.py", self.p, *args, ok=ok)

    def budget(self):
        return re.search(r"budget: ([^|\n]*)", self.read(self.p)).group(1).strip()

    def row(self, i="S1"):
        return next(l for l in self.read(self.p).splitlines() if l.startswith(f"| {i} "))


class Pipes(PlanBase):
    def test_pipe_in_a_cell_is_kept(self):
        self.ps("S1", "verify=pytest -q | grep passed")
        self.ps("S1", "status=running")  # a rewrite keeps the escaped pipe and the columns
        sys.path.insert(0, S)
        import estimate
        head, rows = estimate.table(self.read(self.p), "Steps")
        self.assertEqual(rows[0][head.index("verify")], "pytest -q | grep passed")
        self.assertEqual(rows[0][head.index("status")], "running")


class Budget(PlanBase):
    def test_every_form_keeps_spend_and_size(self):
        for typed, want in [("M", "~0k / M"), ("S", "~0k / S"), ("L 1.5M", "~0k / L 1.5M"),
                            ("~9k / L 800k", "~0k / L 800k"), ("/ M", "~0k / M")]:
            self.ps("--header", f"budget={typed}")
            self.assertEqual(self.budget(), want, typed)
            self.assertTrue(HOOK_BUDGET.search(self.read(self.p)), typed)

    def test_measured_spend_kept(self):
        text = self.read(self.p).replace("budget: ~0k / —", "budget: ~120k / S")
        with open(self.p, "w", encoding="utf-8") as f:
            f.write(text)
        self.ps("--header", "budget=M")
        self.assertEqual(self.budget(), "~120k / M")

    def test_no_way_to_drop_the_ceiling(self):
        for typed in ("L", "~0k / L", "—", "none", "", "L big", "X"):
            out = self.ps("--header", f"budget={typed}", ok=False)
            self.assertIn("REFUSED", out, typed)
        self.assertIn("L needs a number", self.ps("--header", "budget=L", ok=False))
        self.assertEqual(self.budget(), "~0k / —")


class Approval(PlanBase):
    def test_first_approval_needs_a_ceiling(self):
        out = self.ps("--header", "status=approved", "mode=checkpointed", ok=False)
        self.assertIn("no budget ceiling", out)
        self.assertIn("status: planning", self.read(self.p))
        self.ps("--header", "status=approved", "mode=checkpointed", "budget=L 2M")
        self.assertIn("status: approved", self.read(self.p))

    def test_running_needs_a_ceiling_too(self):
        self.assertIn("no budget ceiling", self.ps("--header", "status=running", "mode=autonomous", ok=False))
        self.ps("--header", "budget=M")
        self.ps("--header", "status=running", "mode=autonomous")

    def test_quick_goal_needs_none(self):
        q = self.new_goal("tiny")
        self.run_s("plan-set.py", self.plan(q), "S+", "title=a", "verify=v")
        self.run_s("plan-set.py", self.plan(q), "--header", "status=running", "mode=quick")


class Midnight(PlanBase):
    def test_end_now_always_valid(self):
        if NOW.strftime("%H:%M") >= "23:58":
            self.skipTest("needs a start later than now")
        self.ps("S1", "start=23:59")
        self.ps("S1", "end=now")  # ran past midnight
        self.ps("S1", "end=")
        self.ps("S1", "status=done")  # end stamped now
        self.assertRegex(self.row(), r"\| done \| .* \| 23:59 \| \d\d:\d\d \|")

    def test_typed_end_before_start_refused(self):
        self.ps("S1", "start=15:00")
        out = self.ps("S1", "end=09:00", ok=False)
        self.assertIn("end=now", out)
        self.assertIn("REFUSED", self.ps("S1", "start=21:00", "end=02:00", ok=False))  # no late-night guess
        self.ps("S1", "end=16:00")


class Pr(PlanBase):
    def test_values(self):
        for v in ("ask-at-end", "auto", "none", "declined", "https://github.com/o/r/pull/7"):
            self.ps("--header", f"pr={v}")
            self.assertIn(f"pr: {v} |", self.read(self.p))
        for v in ("ask at end", "automatic", "yes"):
            self.assertIn("REFUSED", self.ps("--header", f"pr={v}", ok=False), v)


class Lock(PlanBase):
    def test_waits_for_the_plan_lock(self):
        with fileio.plan_lock(self.p):
            proc = subprocess.Popen([sys.executable, os.path.join(S, "plan-set.py"), self.p, "S1", "notes=x"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env())
            time.sleep(0.8)
            self.assertIsNone(proc.poll(), "plan-set wrote without the lock")
            self.assertNotIn("| x |", self.row())
        out, err = proc.communicate(timeout=20)
        self.assertEqual(proc.returncode, 0, out + err)
        self.assertTrue(self.row().endswith("| x |"))


if __name__ == "__main__":
    unittest.main()
