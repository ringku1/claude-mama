#!/usr/bin/env python3
"""overview.py's generated block (between the mama:auto markers) and log.py's U lines."""
import datetime
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import S, SKILL, Base  # noqa: E402,F401

sys.path.insert(0, S)
import overview  # noqa: E402

START, END = "<!-- mama:auto:start -->", "<!-- mama:auto:end -->"

PLAN = """goal: demo | type: build | status: {status} | mode: checkpointed
progress: 1/4 (25%) | blocked: 0 | budget: ~10k / M | approved: M
base: main | branch: x | worktree: n/a | pr: none | deliverable commit: yes | trello: none
started: 2026-01-05 09:00

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1  | filters by price | S1 | tests for price filter pass @10:40 |
| C2  | panel shows filters | S3 | — |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1  | build | filter API | — | a.go | go test | done | 0 | 15m | 10:00 | 10:40 | |
| S2  | build | filter store | — | b.go | go test | running | 0 | 15m | 10:41 | | |
| S3  | build | filter panel | S1 | c.tsx | vitest | todo | 0 | 15m | | | |
| S4  | build | sort panel | S2 | d.tsx | vitest | todo | 0 | 15m | | | |
| S5  | build | old idea | — | e.tsx | vitest | obsolete | 0 | 15m | | | |
"""

LOG = """E1 09:00 start build from test
E2 09:30 research: 2 findings, 1 cases, 0 open
D1 09:40 decision | Q1 x | y | why: z | tag: user
E3 09:50 approve checkpointed
U1 10:40 Filter API done and tested
Q1 10:50 question | Should sorting be on by default? | options: a / b | recommended: a
"""

HAND = """# Course filters

{block}

## Goal

Let students filter courses.

## Key decisions

- Prices round down, because the shop does.
"""


class Regenerate(Base):
    def goal(self, status="running", log=LOG, block=None):
        g = os.path.join(self.tmp, "g")
        os.makedirs(g, exist_ok=True)
        open(os.path.join(g, "plan.md"), "w", encoding="utf-8").write(PLAN.format(status=status))
        open(os.path.join(g, "log.md"), "w", encoding="utf-8").write(log)
        if block is None:
            block = f"{START}\n**Status:** Planning\n\nold generated text\n{END}"
        open(os.path.join(g, "overview.md"), "w", encoding="utf-8").write(HAND.format(block=block))
        return g

    def ov(self, g):
        return self.read(os.path.join(g, "overview.md"))

    def block(self, g):
        t = self.ov(g)
        return t[t.index(START):t.index(END)]

    def test_rewrites_only_the_block(self):  # failing-first: test_rewrites_only_the_block
        g = self.goal()
        overview.regenerate(g)
        t = self.ov(g)
        self.assertTrue(t.startswith("# Course filters\n\n" + START))
        self.assertIn("## Goal\n\nLet students filter courses.", t)
        self.assertIn("- Prices round down, because the shop does.", t)
        self.assertNotIn("old generated text", t)
        b = self.block(g)
        self.assertIn("**Status:** Working · 1 of 4 parts done", b)
        self.assertIn("- [x] filters by price — tests for price filter pass", b)
        self.assertIn("- [ ] panel shows filters", b)

    def test_where_we_are_and_timeline(self):  # failing-first: test_where_we_are_and_timeline
        g = self.goal()
        overview.regenerate(g)
        b = self.block(g)
        self.assertIn("1 of 4 parts done", b)
        self.assertIn("filter store", b.split("## Where we are")[1])
        nxt = b.split("## Where we are")[1]
        self.assertIn("filter panel", nxt)
        self.assertNotIn("sort panel", nxt)  # its dep isn't done
        tl = b.split("## Timeline")[1].split("## Where we are")[0]
        self.assertRegex(tl, r"\| 09:00 \| Started")
        self.assertRegex(tl, r"\| 09:50 \| Plan approved")
        self.assertRegex(tl, r"\| 10:40 \| Filter API done and tested")
        self.assertNotIn("## Needs your input", b)  # not waiting

    def test_no_ids_or_file_refs(self):  # failing-first: test_no_ids_or_file_refs
        log = LOG + "U2 11:00 Fixed S2 in a.go:12 after E3\n"
        g = self.goal(status="waiting", log=log)
        overview.regenerate(g)
        b = self.block(g)
        for tok in ("S1", "S2", "S3", "C1", "E3", "Q1", "U1", "a.go:12"):
            self.assertNotRegex(b, rf"\b{re.escape(tok)}\b", tok)

    def test_keeps_words_shaped_like_ids(self):  # failing-first: test_keeps_words_shaped_like_ids
        log = LOG + "U2 11:00 Upload images to S9\nU3 11:05 Q4 report and P1 plan sent\n"
        g = self.goal(log=log)
        overview.regenerate(g)
        tl = self.block(g).split("## Timeline")[1]
        self.assertIn("Upload images to S9", tl)
        self.assertIn("Q4 report and P1 plan sent", tl)

    def test_needs_input_when_waiting(self):  # failing-first: test_needs_input_when_waiting
        g = self.goal(status="waiting")
        overview.regenerate(g)
        b = self.block(g)
        self.assertIn("**Status:** Waiting for you", b)
        self.assertIn("## Needs your input\n\n- Should sorting be on by default?", b)

    def test_answered_question_not_shown(self):
        log = LOG + "D2 11:00 decision | Q1 default | a | why: x | tag: user\n"
        g = self.goal(status="waiting", log=log)
        overview.regenerate(g)
        self.assertNotIn("Should sorting", self.block(g))

    def test_timeline_capped(self):  # failing-first: test_timeline_capped
        log = LOG + "".join(f"U{n} 11:{n:02d} update number {n}\n" for n in range(2, 40))
        g = self.goal(log=log)
        overview.regenerate(g)
        b = self.block(g)
        rows = [l for l in b.split("## Timeline")[1].split("## Where")[0].splitlines() if l.startswith("| ") and "When" not in l and "----" not in l]
        self.assertLessEqual(len(rows), 12)
        self.assertIn("Started", rows[0])
        self.assertIn("update number 39", rows[-1])
        self.assertLessEqual(len([l for l in self.ov(g).splitlines() if l.strip()]), 60)

    def test_keeps_status_detail_and_mtime(self):
        g = self.goal(block=f"{START}\n**Status:** Working · 0 of 4 parts done · panel next\n{END}")
        ov = os.path.join(g, "overview.md")
        os.utime(ov, (1000000, 1000000))
        overview.regenerate(g)
        self.assertIn("**Status:** Working · 1 of 4 parts done · panel next", self.ov(g))
        self.assertAlmostEqual(os.path.getmtime(ov), 1000000, delta=1)  # the prose still counts as unrefreshed

    def test_no_markers_syncs_status_only(self):  # failing-first: test_no_markers_syncs_status_only
        g = self.goal(block="**Status:** Planning\n\n## Where we are\n\nhand text")
        overview.regenerate(g)
        t = self.ov(g)
        self.assertIn("**Status:** Working · 1 of 4 parts done", t)
        self.assertIn("hand text", t)
        self.assertNotIn("## Done means", t)
        self.assertNotIn(START, t)

    def test_sync_regenerates_with_markers(self):  # failing-first: test_sync_regenerates_with_markers
        g = self.goal()
        overview.sync(g)
        self.assertIn("- [x] filters by price", self.block(g))


class Template(Base):
    def test_template_has_markers_around_generated_sections(self):  # failing-first: test_template_has_markers_around_generated_sections
        t = open(os.path.join(SKILL, "templates", "overview.md"), encoding="utf-8").read()
        self.assertIn(START, t)
        self.assertIn(END, t)
        inside = t[t.index(START):t.index(END)]
        for s in ("**Status:**", "## Done means", "## Timeline", "## Where we are"):
            self.assertIn(s, inside)
        outside = t[:t.index(START)] + t[t.index(END):]
        for s in ("# <Goal title", "## Goal", "## Key decisions", "## Final report"):
            self.assertIn(s, outside)


class UserLines(Base):
    def test_u_lines_numbered_and_stamped(self):  # failing-first: test_u_lines_numbered_and_stamped
        g = self.new_goal()
        log = os.path.join(g, "log.md")
        self.assertRegex(self.run_s("log.py", log, "U", "Plan  approved"), r"^U1 \d\d:\d\d Plan approved$")
        self.run_s("log.py", log, "E", "dispatch S1")
        self.assertRegex(self.run_s("log.py", log, "U", "API done"), r"^U2 \d\d:\d\d API done")
        text = self.read(log)
        self.assertRegex(text, r"\nE2 \d\d:\d\d dispatch S1\n")
        self.assertLessEqual(len(re.findall(r"^-- ", text, re.M)), 1)

    def test_u_line_shows_in_generated_timeline(self):
        g = self.new_goal()
        ov = os.path.join(g, "overview.md")
        open(ov, "w", encoding="utf-8").write(f"# T\n\n{START}\n{END}\n")
        self.run_s("log.py", os.path.join(g, "log.md"), "U", "Research done")
        overview.regenerate(g)
        b = self.read(ov)
        self.assertRegex(b, r"\| \d\d:\d\d \| Research done")
        self.assertRegex(b, r"\| \d\d:\d\d \| Started")

    def test_u_line_refreshes_overview(self):  # failing-first: test_u_line_refreshes_overview
        g = self.new_goal()
        ov = os.path.join(g, "overview.md")
        open(ov, "w", encoding="utf-8").write(f"# T\n\n{START}\n{END}\n")
        os.utime(ov, (1000000, 1000000))
        self.run_s("log.py", os.path.join(g, "log.md"), "U", "Research done")
        self.assertRegex(self.read(ov), r"\| \d\d:\d\d \| Research done")
        self.assertAlmostEqual(os.path.getmtime(ov), 1000000, delta=1)

    def test_u_line_written_when_overview_fails(self):
        g = self.new_goal()
        import log as logmod
        orig = overview.regenerate
        def boom(goal):
            raise RuntimeError("boom")
        overview.regenerate = boom
        try:
            line = logmod.write(os.path.join(g, "log.md"), "U", "Still logged")
        finally:
            overview.regenerate = orig
        self.assertRegex(line, r"^U1 \d\d:\d\d Still logged$")
        self.assertIn("Still logged", self.read(os.path.join(g, "log.md")))


class NewGoalKeepsMarkers(Base):
    def test_new_goal_overview_has_the_generated_block(self):
        goal = self.run_s("new-goal.py", self.store, "demo", "build", "t").splitlines()[0]
        ov = open(os.path.join(goal, "overview.md"), encoding="utf-8").read()
        self.assertIn(START, ov)
        self.assertIn(END, ov)
        self.assertNotIn("Overview rules", ov)  # the rules comment is still stripped

if __name__ == "__main__":
    unittest.main()
