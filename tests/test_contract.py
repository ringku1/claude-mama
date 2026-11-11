#!/usr/bin/env python3
"""The shared contract: dated log lines (clock.py, log.py markers) and goal ownership
(activity.goals_of, log.write(record=False))."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import S, Base  # noqa: E402

sys.path.insert(0, S)
import clock  # noqa: E402
import log  # noqa: E402

DT = datetime.datetime


class Clock(unittest.TestCase):
    def test_stamp_dt(self):
        start = DT(2026, 3, 1, 22, 0)
        self.assertEqual(clock.stamp_dt(start, "23:30"), DT(2026, 3, 1, 23, 30))
        self.assertEqual(clock.stamp_dt(start, "21:00"), DT(2026, 3, 2, 21, 0))
        self.assertEqual(clock.stamp_dt(start, "22:00"), DT(2026, 3, 1, 22, 0))
        self.assertEqual(clock.stamp_dt(start, "01:00", DT(2026, 3, 4, 0, 30)), DT(2026, 3, 4, 1, 0))
        self.assertEqual(clock.stamp_dt(start, "00:10", DT(2026, 3, 4, 0, 30)), DT(2026, 3, 5, 0, 10))

    def test_midnight_rollover_without_markers(self):
        tl = clock.timeline("E1 23:50 start\nE2 23:59 a\nD1 00:05 b | tag: x\nE3 00:05 c\n", DT(2026, 3, 1, 23, 50))
        self.assertEqual([(t, k, n) for t, k, n, _ in tl], [
            (DT(2026, 3, 1, 23, 50), "E", 1), (DT(2026, 3, 1, 23, 59), "E", 2),
            (DT(2026, 3, 2, 0, 5), "D", 1), (DT(2026, 3, 2, 0, 5), "E", 3)])
        self.assertEqual(tl[2][3], "b | tag: x")

    def test_first_line_after_midnight_of_start(self):
        tl = clock.timeline("E1 00:10 start\n", DT(2026, 3, 1, 23, 58))
        self.assertEqual(tl[0][0], DT(2026, 3, 2, 0, 10))

    def test_three_day_log_with_markers(self):
        # day 1 ends 18:00, day 2 has a later time than day 3's: only markers can tell
        text = ("E1 09:00 start\nE2 18:00 wait\n-- 2026-03-02\nE3 08:00 back\nF1 20:00 f | x | a:1 | verified\n"
                "-- 2026-03-03\nE4 07:00 more\n\nE5 07:30 done\n")
        tl = clock.timeline(text, DT(2026, 3, 1, 9, 0))
        self.assertEqual([t for t, *_ in tl], [DT(2026, 3, 1, 9), DT(2026, 3, 1, 18), DT(2026, 3, 2, 8),
                                                DT(2026, 3, 2, 20), DT(2026, 3, 3, 7), DT(2026, 3, 3, 7, 30)])

    def test_marker_skips_days_rollover_cannot(self):
        tl = clock.timeline("E1 09:00 a\n-- 2026-03-05\nE2 10:00 b\n", DT(2026, 3, 1, 9, 0))
        self.assertEqual(tl[1][0], DT(2026, 3, 5, 10))

    def test_no_start_no_marker_lines_left_out(self):
        self.assertEqual(clock.timeline("E1 09:00 a\n-- 2026-03-05\nE2 10:00 b\n"),
                         [(DT(2026, 3, 5, 10), "E", 2, "b")])

    def test_start_of(self):
        self.assertEqual(clock.start_of("# g\nstatus: running\nstarted: 2026-03-01 09:05\n"), DT(2026, 3, 1, 9, 5))
        self.assertIsNone(clock.start_of("started: <now>"))


class LogMarkers(Base):
    def goal(self, started="2026-03-01 23:50"):
        g = os.path.join(self.tmp, "g")
        os.makedirs(g)
        open(os.path.join(g, "plan.md"), "w", encoding="utf-8").write(f"# g\nstarted: {started}\n")
        return os.path.join(g, "log.md")

    def test_same_day_as_start_no_marker(self):
        p = self.goal()
        log.write(p, "E", "start", record=False, now=DT(2026, 3, 1, 23, 50))
        log.write(p, "E", "a", record=False, now=DT(2026, 3, 1, 23, 59))
        self.assertEqual(self.read(p), "E1 23:50 start\nE2 23:59 a\n")

    def test_midnight_writes_marker_once(self):
        p = self.goal()
        log.write(p, "E", "start", record=False, now=DT(2026, 3, 1, 23, 50))
        log.write(p, "E", "a", record=False, now=DT(2026, 3, 2, 0, 5))
        log.write(p, "D", "b", record=False, now=DT(2026, 3, 2, 0, 6))
        self.assertEqual(self.read(p), "E1 23:50 start\n-- 2026-03-02\nE2 00:05 a\nD1 00:06 b\n")

    def test_first_line_on_a_later_day_than_start(self):
        p = self.goal()
        log.write(p, "E", "start", record=False, now=DT(2026, 3, 3, 9, 0))
        self.assertEqual(self.read(p), "-- 2026-03-03\nE1 09:00 start\n")

    def test_old_log_without_markers_uses_rollover(self):
        p = self.goal()
        open(p, "w", encoding="utf-8").write("E1 23:50 start\nE2 00:30 a")  # already the 2nd, no newline
        log.write(p, "E", "b", record=False, now=DT(2026, 3, 2, 1, 0))
        log.write(p, "E", "c", record=False, now=DT(2026, 3, 4, 1, 0))
        self.assertEqual(self.read(p), "E1 23:50 start\nE2 00:30 a\nE3 01:00 b\n-- 2026-03-04\nE4 01:00 c\n")

    def test_three_days_round_trip(self):
        p = self.goal("2026-03-01 09:00")
        for now in (DT(2026, 3, 1, 9), DT(2026, 3, 1, 18), DT(2026, 3, 2, 8), DT(2026, 3, 2, 20), DT(2026, 3, 3, 7)):
            log.write(p, "E", "x", record=False, now=now)
        self.assertEqual(self.read(p).count("-- "), 2)
        tl = clock.timeline(self.read(p), DT(2026, 3, 1, 9))
        self.assertEqual([t for t, *_ in tl], [DT(2026, 3, 1, 9), DT(2026, 3, 1, 18), DT(2026, 3, 2, 8),
                                                DT(2026, 3, 2, 20), DT(2026, 3, 3, 7)])

    def test_wait_dedupe_sees_past_marker(self):
        p = self.goal()
        log.write(p, "E", "wait S1", record=False, now=DT(2026, 3, 1, 23, 55))
        self.assertEqual(log.write(p, "E", "wait S1", record=False, now=DT(2026, 3, 2, 0, 5)), "E1 23:55 wait S1")
        self.assertEqual(self.read(p), "E1 23:55 wait S1\n")

    def test_no_plan_marks_today(self):
        p = os.path.join(self.tmp, "log.md")
        log.write(p, "E", "a", record=False, now=DT(2026, 3, 1, 9))
        self.assertEqual(self.read(p), "-- 2026-03-01\nE1 09:00 a\n")

    def test_cli_today(self):
        g = self.new_goal()
        p = os.path.join(g, "log.md")
        self.run_s("log.py", p, "E", "x")
        self.assertNotIn("-- ", self.read(p))  # started today, same day


class Ownership(Base):
    def activity_log(self):
        return os.path.join(self.home, ".claude", "mama", "activity.log")

    def goals_of(self, sid):
        code = "import sys, activity; print('\\n'.join(activity.goals_of(sys.argv[1])))"
        import subprocess
        r = subprocess.run([sys.executable, "-c", code, sid], cwd=S, capture_output=True, text=True, env=self.env(None))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.split()

    def test_goals_of_oldest_first_any_store(self):
        a, b = self.new_goal("one"), self.new_goal("two")
        other = os.path.join(self.tmp, "repo2", ".claude", "mama")
        c = self.run_s("new-goal.py", other, "three", "build", "t").splitlines()[0]
        self.run_s("log.py", os.path.join(a, "log.md"), "E", "back to one")
        self.run_s("log.py", os.path.join(b, "log.md"), "E", "theirs", sid="sess-b")
        self.assertEqual(self.goals_of("sess-a"), [os.path.realpath(g) for g in (a, b, c)])
        self.assertEqual(self.goals_of("sess-b"), [os.path.realpath(b)])
        self.assertEqual(self.goals_of("sess-none"), [])

    def test_no_record_never_claims(self):
        a = self.new_goal("one", sid="sess-a")
        self.run_s("log.py", "--no-record", os.path.join(a, "log.md"), "E", "compacted", sid="sess-hook")
        self.assertEqual(self.goals_of("sess-hook"), [])
        self.assertIn("compacted", self.read(os.path.join(a, "log.md")))
        self.assertNotIn("sess-hook", self.read(self.activity_log()))


if __name__ == "__main__":
    unittest.main(verbosity=1)
