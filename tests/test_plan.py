#!/usr/bin/env python3
"""plan-set.py guards: lock, budget forms, approval ceiling, midnight, PR values. Run: python3 tests/test_plan.py"""
import datetime
import json
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
        self.run_s("log.py", os.path.join(self.g, "log.md"), "E", "expectations: 9 settled, 0 asked")
        self.run_s("log.py", os.path.join(self.g, "log.md"), "E", "db: none — test")
        self.run_s("log.py", os.path.join(self.g, "log.md"), "E", "playback: confirmed")
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

    def test_quick_goal_needs_only_a_one_line_playback(self):
        q = self.new_goal("tiny")
        self.run_s("plan-set.py", self.plan(q), "S+", "title=a", "verify=v")
        out = self.run_s("plan-set.py", self.plan(q), "--header", "status=running", "mode=quick", ok=False)
        self.assertIn("in one line", out)
        self.run_s("log.py", os.path.join(q, "log.md"), "E", "playback: confirmed")
        self.run_s("plan-set.py", self.plan(q), "--header", "status=running", "mode=quick")


class Approved(PlanBase):
    def approved(self):
        return re.search(r"approved: ([^|\n]*)", self.read(self.p)).group(1).strip()

    def test_raise_past_2x_needs_the_user(self):
        self.ps("--header", "status=running", "mode=autonomous", "budget=L 1M")
        self.assertEqual(self.approved(), "L 1M")
        log = os.path.join(self.g, "log.md")
        self.run_s("log.py", log, "D", "budget raised to L 1.8M (tag: auto)")
        self.ps("--header", "budget=L 1.8M")
        self.assertEqual(self.approved(), "L 1M")  # an auto raise doesn't move the anchor
        self.run_s("log.py", log, "D", "budget raised to L 3M (tag: auto)")
        self.assertIn("past 2× the approved L 1M", self.ps("--header", "budget=L 3M", ok=False))
        self.run_s("log.py", log, "D", "budget: continue to ~3M (tag: user)")
        self.ps("--header", "budget=L 3M")
        self.assertEqual(self.approved(), "L 3M")
        self.assertIn("budget set L 1.8M → L 3M (approved L 3M)", self.read(log))
        self.assertIn("past 2× the approved L 3M", self.ps("--header", "budget=L 7M", ok=False))  # that answer is used up

    def test_plan_from_before_approved_gets_it(self):
        self.ps("--header", "status=running", "mode=autonomous", "budget=M")
        s = re.sub(r" \| (approved|auto-raise): [^|\n]*?(?= \||$)", "", self.read(self.p), flags=re.M)  # from before both
        open(self.p, "w", encoding="utf-8").write(s)
        self.ps("--header", "budget=L 1.5M")
        self.assertEqual(self.approved(), "M")
        self.assertIn("past 2× the approved M", self.ps("--header", "budget=L 2.5M", ok=False))


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


class Expectations(Base):
    def test_approval_needs_expectations_then_playback(self):
        g = self.new_goal()
        p, log = self.plan(g), os.path.join(g, "log.md")
        self.run_s("plan-set.py", p, "S+", "title=a", "verify=v")
        self.run_s("log.py", log, "E", "research none: test")
        go = ("plan-set.py", p, "--header", "status=approved", "mode=autonomous", "budget=S")
        self.assertIn("expectations not covered", self.run_s(*go, ok=False))
        self.run_s("log.py", log, "E", "expectations: 7 settled, 2 asked")
        self.assertIn("no database decision", self.run_s(*go, ok=False))
        self.run_s("log.py", log, "E", "db: agreed 2 changes")
        self.assertIn("no playback", self.run_s(*go, ok=False))
        self.run_s("log.py", log, "E", "playback: corrected 1")
        self.run_s(*go)

    def test_playback_must_follow_the_database_decision(self):
        g = self.new_goal()
        p, log = self.plan(g), os.path.join(g, "log.md")
        self.run_s("plan-set.py", p, "S+", "title=a", "verify=v")
        for line in ("research none: test", "expectations: 9 settled, 0 asked", "db: agreed 1 changes",
                     "playback: confirmed", "db: agreed 2 changes"):
            self.run_s("log.py", log, "E", line)
        go = ("plan-set.py", p, "--header", "status=approved", "mode=autonomous", "budget=S")
        self.assertIn("predates the database decision", self.run_s(*go, ok=False))
        self.run_s("log.py", log, "E", "playback: confirmed")
        self.run_s(*go)

    def test_research_goal_needs_no_database_decision(self):
        g = self.run_s("new-goal.py", self.store, "r", "research", "t").splitlines()[0]
        p, log = self.plan(g), os.path.join(g, "log.md")
        self.run_s("plan-set.py", p, "S+", "title=a", "verify=v")
        for line in ("research none: test", "expectations: 9 settled, 0 asked", "playback: confirmed"):
            self.run_s("log.py", log, "E", line)
        self.run_s("plan-set.py", p, "--header", "status=approved", "mode=autonomous", "budget=S")

    def test_quick_goal_needs_no_expectations(self):
        g = self.run_s("new-goal.py", self.store, "q", "fix", "t", "--quick").splitlines()[0]
        self.run_s("plan-set.py", self.plan(g), "S+", "title=a", "verify=v")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "playback: confirmed")
        self.run_s("plan-set.py", self.plan(g), "--header", "status=running")


class Lean(PlanBase):
    def test_plain_step_done_is_no_milestone_starred_is(self):
        mark = os.path.join(self.g, ".milestone")
        self.ps("S+", "title=b", "verify=v", "notes=end to end ★")
        old = time.time() - 60
        os.utime(mark, (old, old))
        self.ps("S1", "status=done")
        self.assertAlmostEqual(os.path.getmtime(mark), old, delta=1)
        self.ps("S2", "status=done")
        self.assertGreater(os.path.getmtime(mark), old + 30)

    def test_fixing_counts_a_fix_round(self):
        self.ps("S1", "status=running")
        self.ps("S1", "status=fixing")
        self.ps("S1", "notes=still fixing")
        self.ps("S1", "status=running")
        self.ps("S1", "status=fixing")
        row = next(l for l in self.read(self.p).splitlines() if l.startswith("| S1"))
        self.assertRegex(row, r"\| fixing \| 2 \|")

    def test_estimate_scaled_by_past_goals(self):
        sys.path.insert(0, S)
        import estimate
        self.ps("S1", "est=100m")
        self.assertIn("no past goals to calibrate yet", self.ps("S1", "notes=n"))
        with open(os.path.join(self.store, "lessons.md"), "w", encoding="utf-8") as f:
            f.write("- d a fix | time est 100m critical path (sum 150m) / actual 71m (active 50m) | x\n"
                    "- d b fix | time est 109m (sum of steps) / actual 29m | x\n"  # a sum, not a critical path: skipped
                    "- d c fix | time est 40m critical path (sum 40m) / actual 20m (active 20m) | x\n")
        pat = os.path.join(self.home, ".claude", "mama", "patterns.md")
        with open(pat, "w", encoding="utf-8") as f:
            f.write("## Goals and estimates\n\n- x (mixed, 12 steps): est 200m critical path / L 3M, actual 50m (active 40m) / 1900k\n"
                    "- a fix (fix, 2 steps): est 100m critical path / M, actual 71m (active 50m) / 9k\n")  # same as lessons: once
        from unittest import mock
        with mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home}):
            self.assertEqual(estimate.history(self.p), [(100, 50), (40, 20), (200, 40)])
            self.assertEqual(estimate.ratio(self.p), (0.5, 3))
        self.assertIn("likely ~50m, ~50m left (past goals took ×0.50 of the critical path, last 3)", self.ps("S1", "notes=m"))


class Tokens(PlanBase):
    def test_tokens_likely_from_past_goals(self):
        with open(os.path.join(self.store, "lessons.md"), "w", encoding="utf-8") as f:
            f.write("- d a fix | steps 4 | time est 10m critical path / actual 5m | tokens est M / ~400k | x\n"
                    "- d b fix | steps 10 | time est 10m critical path / actual 5m | tokens est L 3M -> L 6M / ~2M | x\n")
        pat = os.path.join(self.home, ".claude", "mama", "patterns.md")
        with open(pat, "w", encoding="utf-8") as f:
            f.write("## Goals and estimates\n\n- c (fix, 2 steps): est 9m critical path / M, actual 5m / 300k measured\n")
        self.ps("--header", "budget=S")
        out = self.ps("S1", "est=10m")
        self.assertIn("tokens likely ~150k (1 steps × ~150k per step, last 3 goals)", out)  # 100k, 200k, 150k
        self.ps("S+", "title=b", "verify=v", "est=5m")
        self.ps("S+", "title=c", "verify=v", "est=5m")
        self.assertIn("tokens likely ~450k (3 steps", self.ps("S3", "notes=n"))
        self.assertIn("over the budget size S", self.ps("S3", "notes=m"))


class Unverified(PlanBase):
    """`unverified`: the verify couldn't run here; the step is finished like done."""

    def test_counts_as_finished(self):
        self.ps("S1", "est=10m")
        self.ps("S+", "title=b", "verify=v", "deps=S1", "est=5m")
        self.ps("S1", "status=running")
        out = self.ps("S1", "status=unverified")
        self.assertRegex(self.row(), r"\| unverified \| .* \| \d\d:\d\d \| \d\d:\d\d \|")  # end stamped
        self.assertIn("progress: 1/2 (50%)", out)
        self.assertIn("left 5m", out)
        out = self.ps("S2", "status=running")
        self.assertNotIn("WARNING", out)

    def test_never_running_for_resources(self):
        other = self.new_goal("other")
        po = self.plan(other)
        self.run_s("plan-set.py", po, "S+", "title=a", "verify=v")
        self.run_s("plan-set.py", po, "S+", "title=b", "verify=v")
        text = self.read(po)
        text = re.sub(r"status: \w+", "status: running", text, count=1)
        text = re.sub(r"^\| S1 (.*)\| todo \|", r"| S1 \1| unverified |", text, flags=re.M)
        text = re.sub(r"^\| S2 (.*)\| todo \|", r"| S2 \1| running |", text, flags=re.M)
        open(po, "w", encoding="utf-8").write(text)
        out = self.run_s("resources.py", "4", self.store, "demo")
        self.assertIn("other_goals_running_steps=1", out)


def usage_line(tokens):
    t = datetime.datetime.now()
    return json.dumps({"message": {"id": "m%d" % tokens, "type": "message", "role": "assistant", "content": [],
                                   "usage": {"input_tokens": tokens, "cache_creation_input_tokens": 0,
                                             "output_tokens": 0}},
                       "type": "assistant", "uuid": "u%d" % tokens, "timestamp": utc(t)},
                      separators=(",", ":")) + "\n"


class SpendLine(PlanBase):
    """After a step-row change plan-set prints the measured spend against the ceiling."""

    def spent(self, tokens, mode="w"):
        d = os.path.join(self.home, ".claude", "projects", "p")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "sess-a.jsonl"), mode, encoding="utf-8") as f:
            f.write(usage_line(tokens))

    def test_under_70_no_warning(self):
        self.ps("--header", "budget=S")
        self.spent(150_000)
        out = self.ps("S1", "notes=x")
        self.assertRegex(out, r"(?m)^budget: 50% of ")
        self.assertNotIn("WARNING", out)
        self.assertIn("budget: ~0k / S", self.read(self.p))  # the Stop hook writes the header, not plan-set

    def test_at_70_warns_past_100_still_only_warns(self):
        self.ps("--header", "budget=S")
        self.spent(240_000)
        out = self.ps("S1", "notes=x")
        self.assertRegex(out, r"(?m)^budget: 80% of .* — WARNING: .*rules/loop\.md → Budget")
        self.spent(210_000, mode="a")  # 450k in all
        out = self.ps("S+", "title=b", "verify=v")  # an added step row counts too
        self.assertRegex(out, r"(?m)^budget: 150% of .* — WARNING")
        self.assertIn("ADDED", out)

    def test_nothing_without_data(self):
        self.assertNotRegex(self.ps("S1", "notes=x"), r"(?m)^budget:")  # no ceiling, no transcript
        self.ps("--header", "budget=S")
        self.assertNotRegex(self.ps("S1", "notes=y"), r"(?m)^budget:")  # no transcript
        self.spent(150_000)
        self.assertNotRegex(self.ps("C1", "evidence=e"), r"(?m)^budget:")  # not a step row

    def test_broken_spend_data_is_silent(self):
        self.ps("--header", "budget=S")
        self.spent(150_000)
        with open(os.path.join(self.g, ".spend-cache.json"), "w", encoding="utf-8") as f:
            f.write("{broken")
        with open(os.path.join(self.home, ".claude", "projects", "p", "sess-a.jsonl"), "a", encoding="utf-8") as f:
            f.write("{not json\n")
        self.ps("S1", "notes=x")  # exit 0 whatever spend makes of it

    def test_partial_measure_prints_nothing(self):
        """A measure its deadline cut is not the spend: printing it would under-report and miss the WARNING."""
        import contextlib
        import importlib.util
        import io
        spec = importlib.util.spec_from_file_location("plan_set", os.path.join(S, "plan-set.py"))
        ps = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ps)
        lines = self.read(self.p).splitlines()
        lines = [re.sub(r"budget: [^|]*", "budget: ~0k / S ", l) if l.startswith("budget:") or "| budget:" in l
                 else l for l in lines]
        self.assertIn("S", ps.header_value(lines, "budget"))

        def fake(plan, transcript=None, deadline=None):
            fake.partial = cut
            return 100_000
        real = ps.spend.measure
        ps.spend.measure = fake
        try:
            for cut, want in ((False, True), (True, False)):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    ps.budget_line(self.p, lines)
                self.assertEqual(bool(re.search(r"(?m)^budget:", buf.getvalue())), want, (cut, buf.getvalue()))
        finally:
            ps.spend.measure = real


class EvidenceDue(PlanBase):
    def test_done_with_open_criterion_warns(self):
        self.ps("C+", "criterion=it works", "proven by=S1")
        out = self.ps("S1", "status=done")
        self.assertIn("WARNING", out)
        self.assertIn("C1", out)
        self.assertIn('plan-set.py %s C1 "evidence=' % self.p, out)
        self.assertIn("| done |", self.row())  # a warning, not a refusal

    def test_no_warning_once_evidence_is_in(self):
        self.ps("C+", "criterion=it works", "proven by=S1")
        self.ps("C1", "evidence=go test ok @11:40")
        self.assertNotIn("WARNING", self.ps("S1", "status=done"))

    def test_other_steps_criterion_not_named(self):
        self.ps("S+", "title=b", "verify=v")
        self.ps("C+", "criterion=it works", "proven by=S2")
        self.assertNotIn("C1", self.ps("S1", "status=done"))


def history_files(test, lessons=(), patterns=()):
    """Metrics lines: lessons as (steps, tokens k), patterns as (steps, tokens k)."""
    with open(os.path.join(test.store, "lessons.md"), "w", encoding="utf-8") as f:
        for i, (n, k) in enumerate(lessons):
            f.write(f"- 2026-01-0{i % 9 + 1} g{i} fix | steps {n} | time est 10m critical path / actual 5m"
                    f" | tokens est M / ~{k}k | x\n")
    with open(os.path.join(test.home, ".claude", "mama", "patterns.md"), "w", encoding="utf-8") as f:
        f.write("## Goals and estimates\n\n")
        for i, (n, k) in enumerate(patterns):
            f.write(f"- p{i} (fix, {n} steps): est 9m critical path / M, actual 5m / {k}k measured\n")


class Tiers(Base):
    def test_new_goal_writes_the_tier(self):
        g = self.new_goal()
        head = self.read(self.plan(g)).split("\n## ")[0]
        self.assertIn("| tier: —", head.splitlines()[0])  # line 1, after mode
        self.assertIn("auto-raise: —", head)
        g = self.run_s("new-goal.py", self.store, "s", "fix", "t", "--tier", "standard").splitlines()[0]
        self.assertRegex(self.read(self.plan(g)), r"mode: — \| tier: standard")
        for args in (("--quick",), ("--tier", "quick"), ("--tier=quick",)):
            g = self.run_s("new-goal.py", self.store, "q", "fix", "t", *args).splitlines()[0]
            self.assertRegex(self.read(self.plan(g)), r"mode: quick \| tier: quick", args)
            self.assertNotIn("## Timeline", self.read(os.path.join(g, "overview.md")))  # the 3-line overview
        self.run_s("new-goal.py", self.store, "x", "fix", "t", "--tier", "huge", ok=False)
        self.run_s("new-goal.py", self.store, "x", "fix", "t", "--tier", ok=False)

    def test_standard_has_the_full_approval_guards(self):
        g = self.run_s("new-goal.py", self.store, "s", "build", "t", "--tier", "standard").splitlines()[0]
        p, log = self.plan(g), os.path.join(g, "log.md")
        self.run_s("plan-set.py", p, "S+", "title=a", "verify=v")
        go = ("plan-set.py", p, "--header", "status=approved", "mode=checkpointed")
        self.assertIn("no research", self.run_s(*go, ok=False))
        for line, want in (("research: 1 findings, 0 cases, 0 open", "expectations not covered"),
                           ("expectations: 5 settled, 1 asked", "no database decision"),
                           ("db: none — t", "no playback"), ("playback: confirmed", "no budget ceiling")):
            self.run_s("log.py", log, "E", line)
            self.assertIn(want, self.run_s(*go, ok=False))
        self.run_s(*go, "budget=S")

    def test_plan_set_tier_and_auto_raise(self):
        g = self.new_goal()
        p = self.plan(g)
        self.assertIn("REFUSED", self.run_s("plan-set.py", p, "--header", "tier=huge", ok=False))
        self.run_s("plan-set.py", p, "--header", "tier=standard")
        self.assertIn("tier: standard", self.read(p))
        for typed, want in (("1.5", "1.5x"), ("2x", "2x"), ("1", "1x"), ("1.25x", "1.25x")):
            self.run_s("plan-set.py", p, "--header", f"auto-raise={typed}")
            self.assertIn(f"auto-raise: {want}", self.read(p), typed)
        for typed in ("2.5", "0.5x", "big", ""):
            self.assertIn("REFUSED", self.run_s("plan-set.py", p, "--header", f"auto-raise={typed}", ok=False), typed)

    def test_old_plan_without_the_fields_gets_them(self):
        g = self.new_goal()
        p = self.plan(g)
        s = re.sub(r" \| (tier|auto-raise): [^|\n]*", "", self.read(p))
        open(p, "w", encoding="utf-8").write(s)
        self.assertNotIn("tier:", self.read(p))
        self.run_s("plan-set.py", p, "--header", "tier=full", "auto-raise=1.5")
        lines = self.read(p).splitlines()
        self.assertTrue(lines[0].endswith("| tier: full"), lines[0])
        self.assertIn("| auto-raise: 1.5x", next(l for l in lines if "budget:" in l))


class TokenSource(Base):
    def test_lessons_first_patterns_only_as_fallback(self):
        import estimate
        from unittest import mock
        g = self.new_goal()
        history_files(self, lessons=[(2, 200), (2, 200), (2, 200)], patterns=[(1, 900)] * 5 + [(1, 800)])
        with mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home}):
            self.assertEqual(estimate.token_rate(self.plan(g)), (100_000, 3))  # patterns not mixed in
            history_files(self, lessons=[(1, 10)] * 12 + [(1, 20)] * 3)  # equal lines are separate goals
            self.assertEqual(estimate.token_rate(self.plan(g)), (10_000, 10))  # the last 10 lines
            history_files(self, lessons=[], patterns=[(2, 600), (2, 600), (2, 800)])
            self.assertEqual(estimate.token_rate(self.plan(g)), (300_000, 3))
            history_files(self)
            self.assertEqual(estimate.token_rate(self.plan(g)), (None, 0))


class BudgetFloor(PlanBase):
    def test_first_approval_refuses_a_size_below_tokens_likely(self):
        history_files(self, lessons=[(1, 500), (1, 500), (1, 500)])
        out = self.ps("--header", "status=approved", "mode=checkpointed", "budget=S", ok=False)
        self.assertIn("tokens likely ~500k", out)
        self.assertIn("budget=M", out)  # the size that covers it
        self.assertIn("status: planning", self.read(self.p))
        self.ps("--header", "status=approved", "mode=checkpointed", "budget=M")

    def test_user_decision_accepts_a_smaller_size(self):
        history_files(self, lessons=[(1, 2000), (1, 2000), (1, 2000)])
        out = self.ps("--header", "status=approved", "mode=checkpointed", "budget=M", ok=False)
        self.assertIn("budget='L 2M'", out)
        self.run_s("log.py", os.path.join(self.g, "log.md"), "D", "budget M is enough, scope is small (tag: user)")
        self.ps("--header", "status=approved", "mode=checkpointed", "budget=M")

    def test_no_history_no_refusal(self):
        self.ps("--header", "status=approved", "mode=checkpointed", "budget=S")


class AutoRaiseDefault(PlanBase):
    def raise_of(self):
        return re.search(r"auto-raise: ([^|\n]*)", self.read(self.p)).group(1).strip()

    def test_set_at_first_approval(self):
        self.ps("--header", "budget=S")
        self.assertEqual(self.raise_of(), "—")  # not before approval
        self.ps("--header", "status=approved", "mode=checkpointed")
        self.assertEqual(self.raise_of(), "1.5x")

    def test_given_value_kept(self):
        self.ps("--header", "status=approved", "mode=checkpointed", "budget=S", "auto-raise=1x")
        self.assertEqual(self.raise_of(), "1x")


class Heartbeat(PlanBase):
    """The Stop hook runs when a turn ends, right after a `wait …`/`waiting` line: a turn of any
    length that logs no wait is no sign the hook is down."""
    def setUp(self):
        super().setUp()
        self.ps("--header", "status=running", "mode=autonomous", "budget=M")
        self.hb = os.path.join(self.g, ".heartbeat")
        self.logp = os.path.join(self.g, "log.md")

    def beat(self, age_min):
        with open(self.hb, "w", encoding="utf-8") as f:
            f.write("2026-01-01T00:00:00 120k\n")
        t = time.time() - age_min * 60
        os.utime(self.hb, (t, t))

    def logged(self, ago_min, text):
        """Append an E line stamped ago_min minutes back, with its day's marker."""
        at = datetime.datetime.now() - datetime.timedelta(minutes=ago_min)
        with open(self.logp, "a", encoding="utf-8") as f:
            f.write(f"-- {at:%Y-%m-%d}\nE90 {at:%H:%M} {text}\n")
        return at

    def test_stale_heartbeat_after_a_wait_line_warns(self):
        # failing-first: test_stale_heartbeat_after_a_wait_line_warns
        at = self.logged(15, "wait S1 S2")
        self.beat(45)
        out = self.ps("S1", "notes=x")
        self.assertIn(f"WARNING: the Stop hook hasn't run since the wait at {at:%H:%M} (15 min ago) — "
                      "check ~/.claude/mama/hook-errors.log", out)
        self.beat(45)
        self.assertIn("hasn't run since the wait", self.ps("--header", "pr=none"))  # any write

    def test_waiting_line_counts_as_a_wait(self):
        self.logged(20, "S3 dispatched, waiting")
        self.beat(45)
        self.assertIn("hasn't run since the wait", self.ps("S1", "notes=x"))

    def test_long_turn_without_a_wait_is_quiet(self):
        # failing-first: test_long_turn_without_a_wait_is_quiet
        self.logged(40, "dispatch S1")
        self.beat(45)  # a 45-minute turn: every plan-set/log call moved log.md past the heartbeat
        self.assertNotIn("Stop hook", self.ps("S1", "notes=a"))

    def test_quiet_otherwise(self):
        # failing-first: test_quiet_otherwise
        self.logged(5, "wait S1")  # the wait is under 10 min old
        self.beat(45)
        self.assertNotIn("Stop hook", self.ps("S1", "notes=a"))
        self.logged(30, "wait S1")
        self.logged(20, "dispatch S2")  # the last wait is still the one that counts
        self.beat(25)  # the hook ran after that wait
        self.assertNotIn("Stop hook", self.ps("S1", "notes=b"))
        os.remove(self.hb)  # an old goal: no heartbeat at all
        self.assertNotIn("Stop hook", self.ps("S1", "notes=c"))
        self.beat(45)
        self.ps("--header", "status=waiting")  # not running
        self.logged(30, "wait S1")
        self.beat(45)
        self.assertNotIn("Stop hook", self.ps("S1", "notes=d"))


class ApprovedLine(PlanBase):
    """The first approval logs `E approved: …`, the overview's "Plan approved" Timeline row."""
    def approvals(self):
        return re.findall(r"^E\d+ \d\d:\d\d approved: .*$", self.read(os.path.join(self.g, "log.md")), re.M)

    def test_first_approval_logs_once(self):
        # failing-first: test_first_approval_logs_once
        self.ps("--header", "status=approved", "mode=checkpointed", "budget=L 2M")
        self.assertEqual(self.approvals(), [self.approvals()[0]])
        self.assertTrue(self.approvals()[0].endswith("approved: mode=checkpointed budget=L 2M auto-raise=1.5x"))
        self.ps("--header", "status=running")
        self.ps("--header", "status=waiting")
        self.ps("--header", "status=running")  # waiting → running before any resume line: still not a new approval
        self.assertEqual(len(self.approvals()), 1)

    def test_quick_goal_logs_it_too(self):
        q = self.new_goal("tiny")
        self.run_s("plan-set.py", self.plan(q), "S+", "title=a", "verify=v")
        self.run_s("log.py", os.path.join(q, "log.md"), "E", "playback: confirmed")
        self.run_s("plan-set.py", self.plan(q), "--header", "status=running", "mode=quick")
        self.assertRegex(self.read(os.path.join(q, "log.md")), r"(?m)^E\d+ \d\d:\d\d approved: mode=quick budget=")

    def test_refused_approval_logs_nothing(self):
        self.ps("--header", "status=approved", "mode=checkpointed", ok=False)  # no ceiling
        self.assertEqual(self.approvals(), [])


if __name__ == "__main__":
    unittest.main()
