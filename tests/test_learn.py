#!/usr/bin/env python3
"""learn.py (contradiction streak) and list.py, in a throwaway HOME. Run: python3 tests/test_learn.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_mama import Base, S  # noqa: E402

LEARNED = "## How you like things done"
WATCH = "## Watching (fewer than 3 observations)"


class Learn(Base):
    def path(self):
        return os.path.join(self.home, ".claude", "mama", "patterns.md")

    def learn(self, kind, text="short replies", *rest):
        return self.run_s("learn.py", kind, text, *rest)

    def section(self, text="short replies"):
        with open(self.path(), encoding="utf-8") as f:
            lines = f.read().split("\n")
        i = next((i for i, l in enumerate(lines) if l.startswith(f"- {text} — ")), None)
        if i is None:
            return None, None
        return next(l for l in reversed(lines[:i]) if l.startswith("## ")), lines[i]

    def test_new_file_from_template(self):
        self.learn("seen")
        text = open(self.path(), encoding="utf-8").read()
        self.assertTrue(text.startswith("# How you work"), text)
        for h in ("## Choices you make", LEARNED, "## Corrections you've made", "## Goals and estimates", WATCH):
            self.assertIn(h, text)
        self.assertNotIn("<!--", text)
        self.assertNotIn("<e.g.", text)
        self.assertEqual(self.section()[0], WATCH)

    def test_one_contra_keeps_learned(self):
        for _ in range(4):
            self.learn("seen")
        self.assertEqual(self.section()[0], LEARNED)
        self.learn("contra")
        sec, line = self.section()
        self.assertEqual(sec, LEARNED)
        self.assertIn(" — 3/5 — contradicted last time — last ", line)

    def test_two_contras_in_a_row_demote(self):
        for _ in range(4):
            self.learn("seen")
        self.learn("contra")
        self.learn("contra")
        sec, line = self.section()
        self.assertEqual(sec, WATCH)
        self.assertIn(" — 2/6 — last ", line)
        self.assertNotIn("contradicted", line)

    def test_seen_resets_streak(self):
        for _ in range(3):
            self.learn("seen")
        for _ in range(3):
            self.learn("contra")
            self.learn("seen")
        sec, line = self.section()
        self.assertEqual(sec, LEARNED)
        self.assertIn(" — 3/9 — last ", line)
        self.assertNotIn("contradicted", line)

    def test_old_line_without_marker_parses(self):
        with open(self.path(), "w", encoding="utf-8") as f:
            f.write(f"# How you work\n\n{LEARNED}\n\n- short replies — 5/5 — last 2026-01-01\n\n{WATCH}\n")
        self.learn("contra")
        self.assertEqual(self.section()[0], LEARNED)
        self.learn("contra")
        sec, line = self.section()
        self.assertEqual(sec, WATCH)
        self.assertIn(" — 3/7 — last ", line)

    def test_watching_drops_and_promotes(self):
        self.learn("seen")
        self.learn("contra")
        self.assertEqual(self.section(), (None, None))
        for _ in range(3):
            self.learn("seen", "tabs")
        self.assertEqual(self.section("tabs")[0], LEARNED)

    def test_stated_keeps_status(self):
        self.learn("stated")
        out = self.learn("contra")
        self.assertIn("NOTE", out)
        self.learn("contra")
        sec, line = self.section()
        self.assertEqual(sec, LEARNED)
        self.assertIn(" — stated — last ", line)


class List(Base):
    def test_lists_open_first(self):
        self.new_goal("old-one")
        self.new_goal("live-one")
        plan = os.path.join(self.store, "old-one", "plan.md")
        with open(plan, encoding="utf-8") as f:
            text = f.read().replace("status: planning", "status: done")
        with open(plan, "w", encoding="utf-8") as f:
            f.write(text)
        os.makedirs(os.path.join(self.store, "stray"))
        out = self.run_s("list.py", self.store).strip().split("\n")
        self.assertEqual(len(out), 3, out)
        self.assertTrue(out[-1].startswith("old-one ") and " done " in out[-1], out)
        live = next(l for l in out if l.startswith("live-one "))
        self.assertIn("planning", live)
        self.assertIn("0/0 (0%)", live)
        self.assertTrue(any(l.startswith("stray ") and "no plan.md" in l for l in out[:2]), out)

    def test_usage_and_empty(self):
        self.run_s("list.py", ok=False)
        os.makedirs(self.store)
        self.assertEqual(self.run_s("list.py", self.store).strip(), "no goals")


if __name__ == "__main__":
    unittest.main()
