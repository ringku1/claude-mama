#!/usr/bin/env python3
"""step.py: one state call per step — plan row, log line, criteria evidence, overview."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Base  # noqa: E402

START, END = "<!-- mama:auto:start -->", "<!-- mama:auto:end -->"


class Step(Base):
    def setUp(self):
        super().setUp()
        self.g = self.new_goal()
        self.fill_steps(self.g)
        self.p = self.plan(self.g)
        self.log = os.path.join(self.g, "log.md")

    def row(self, rid):
        return next(l for l in self.read(self.p).splitlines() if l.startswith(f"| {rid} "))

    def test_running_then_done(self):  # failing-first: test_running_then_done
        out = self.run_s("step.py", self.p, "S1", "running")
        self.assertRegex(self.row("S1"), r"\| running \| 0 \| 10m \| \d\d:\d\d \|")
        self.assertIn("progress: 0/1", out)
        self.assertRegex(self.read(self.log), r"\nE\d+ \d\d:\d\d running S1\n")
        out = self.run_s("step.py", self.p, "S1", "done", "tests pass", "--commit", "abc1234",
                         "--crit", "C1=go test ok")
        row = self.row("S1")
        self.assertIn("| done |", row)
        self.assertIn("tests pass · commit abc1234", row)
        self.assertRegex(row, r"\| \d\d:\d\d \| \d\d:\d\d \| tests pass")
        self.assertIn("| C1 | it works | S1 | go test ok |", self.read(self.p))
        self.assertIn("progress: 1/1 (100%)", out)
        self.assertNotIn("WARNING: C1", out)  # evidence set in the same call
        lines = [l for l in self.read(self.log).splitlines() if re.match(r"E\d+ ", l)]
        self.assertRegex(lines[-1], r"^E\d+ \d\d:\d\d done S1 — tests pass · commit abc1234$")
        self.assertEqual(sum("S1" in l for l in lines), 2)  # one E line per call

    def test_notes_append(self):  # failing-first: test_notes_append
        self.run_s("step.py", self.p, "S1", "running", "first")
        self.run_s("step.py", self.p, "S1", "fixing", "a | b")
        self.assertIn("first · a \\| b", self.row("S1"))
        self.assertIn("| fixing | 1 |", self.row("S1"))  # plan-set's guard counted the fix round

    def test_refused_write_exits_nonzero_and_logs_nothing(self):  # failing-first: test_refused_write_exits_nonzero_and_logs_nothing
        before = self.read(self.log)
        out = self.run_s("step.py", self.p, "S9", "done", "x", ok=False)
        self.assertIn("S9 not found", out)
        self.assertEqual(self.read(self.log), before)

    def test_bad_args(self):
        self.run_s("step.py", self.p, "S1", ok=False)
        self.run_s("step.py", self.p, "S1", "done", "--crit", "nonsense", ok=False)

    def test_regenerates_overview(self):  # failing-first: test_regenerates_overview
        ov = os.path.join(self.g, "overview.md")
        open(ov, "w", encoding="utf-8").write(f"# Demo\n\n{START}\n**Status:** Planning\n{END}\n\n## Goal\n\nx\n")
        self.run_s("step.py", self.p, "S1", "done", "--crit", "C1=go test ok")
        t = self.read(ov)
        self.assertIn("1 of 1 parts done", t)
        self.assertIn("- [x] it works — go test ok", t)
        self.assertIn("## Goal\n\nx", t)


if __name__ == "__main__":
    unittest.main()
