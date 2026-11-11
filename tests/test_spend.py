#!/usr/bin/env python3
"""spend.py: which sessions and times count toward a goal, multi-day windows, the per-goal
cache, and the transcripts folder. Run: python3 tests/test_spend.py
"""
import datetime
import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import NOW, S, Base, utc  # noqa: E402

DAY = datetime.timedelta(days=1)


def line(t, mid, tokens, content=None):
    """An assistant line laid out as Claude Code writes it (compact, message first)."""
    return json.dumps({"parentUuid": None, "isSidechain": False, "message": {
        "model": "m", "id": mid, "type": "message", "role": "assistant", "content": content or [],
        "usage": {"input_tokens": tokens, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 999999,
                  "output_tokens": 0, "iterations": [{"input_tokens": 5}]}},
        "type": "assistant", "uuid": mid + "-u", "timestamp": utc(t)}, separators=(",", ":")) + "\n"


def bash(cmd):
    return [{"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": cmd}}]


class Spend(Base):
    def setUp(self):
        super().setUp()
        self.start = NOW.replace(second=0, microsecond=0) - datetime.timedelta(hours=1)
        self.cfg = None

    def env(self, sid=None):
        e = super().env(sid)
        e.pop("CLAUDE_CONFIG_DIR", None)
        if self.cfg:
            e["CLAUDE_CONFIG_DIR"] = self.cfg
        return e

    def m(self, k):
        return self.start + datetime.timedelta(minutes=k)

    def goal(self, slug, start=None, status=None):
        g = self.new_goal(slug, sid=None)
        p = self.plan(g)
        text = re.sub(r"started: .*", f"started: {(start or self.start):%Y-%m-%d %H:%M}", self.read(p))
        if status:
            text = re.sub(r"status: \w+", f"status: {status}", text, count=1)
        open(p, "w", encoding="utf-8").write(text)
        return g

    def projects(self):
        return os.path.join(self.cfg or os.path.join(self.home, ".claude"), "projects", "p")

    def transcript(self, sid, lines, mode="w", sub=None):
        d = self.projects()
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{sid}.jsonl")
        with open(path, mode, encoding="utf-8") as f:
            f.writelines(lines)
        if sub:
            sd = os.path.join(d, sid, "subagents")
            os.makedirs(sd, exist_ok=True)
            with open(os.path.join(sd, "agent-1.jsonl"), "w", encoding="utf-8") as f:
                f.writelines(sub)
        return path

    def activity(self, rows):
        with open(os.path.join(self.home, ".claude", "mama", "activity.log"), "w", encoding="utf-8") as f:
            for t, sid, goal in rows:
                f.write(f"{t.isoformat(timespec='seconds')} {sid} {goal}\n")

    def measure(self, goal):
        code = f"import sys; sys.path.insert(0, {S!r}); import spend; print(spend.measure({self.plan(goal)!r}))"
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_session_that_never_recorded_the_goal_adds_nothing(self):
        a, b = self.goal("one"), self.goal("two")
        self.activity([(self.m(1), "sess-a", a), (self.m(1), "sess-b", b)])
        self.transcript("sess-a", [line(self.m(2), "a1", 100)])
        # sess-b's own shell wrote into goal one's folder (it looks like a write) but never recorded it
        self.transcript("sess-b", [line(self.m(3), "b1", 7000, bash(f"echo x >> {a}/notes.txt")),
                                   line(self.m(4), "b2", 50)])
        self.assertEqual(self.measure(a), "100")
        self.assertEqual(self.measure(b), "7050")
        self.assertEqual(self.measure(self.goal("three")), "None")

    def test_each_session_counts_only_its_own_time_on_the_goal(self):
        a, b = self.goal("one"), self.goal("two")
        self.activity([(self.m(1), "sess-a", a), (self.m(5), "sess-b", a), (self.m(10), "sess-a", b),
                       (self.m(20), "sess-a", a), (self.m(30), "sess-b", b)])
        self.transcript("sess-a", [line(self.m(k), f"a{k}", 1 << k) for k in (2, 12, 22)],
                        sub=[line(self.m(13), "s1", 3000)])  # started while sess-a was on two
        self.transcript("sess-b", [line(self.m(k), f"b{k}", 10 * k) for k in (6, 31)])
        self.assertEqual(self.measure(a), str((1 << 2) + (1 << 22) + 60))
        self.assertEqual(self.measure(b), str((1 << 12) + 3000 + 310))

    def test_multi_day_goal_ends_at_its_dated_last_log_line(self):
        start = self.start - 3 * DAY
        g = self.goal("long", start=start, status="done")
        end = start + 2 * DAY
        with open(os.path.join(g, "log.md"), "w", encoding="utf-8") as f:
            f.write(f"E1 {start:%H:%M} start\n-- {end:%Y-%m-%d}\nE2 {end:%H:%M} done\n")
        self.activity([(start, "sess-a", g)])
        self.transcript("sess-a", [line(start + datetime.timedelta(hours=k), f"m{k}", 1 << k) for k in (1, 30, 47, 49)])
        self.assertEqual(self.measure(g), str((1 << 1) + (1 << 30) + (1 << 47)))

    def test_cache_reads_only_new_bytes(self):
        g = self.goal("one")
        self.activity([(self.m(1), "sess-a", g)])
        path = self.transcript("sess-a", [line(self.m(2), "x", 100), line(self.m(3), "y", 10)])
        self.assertEqual(self.measure(g), "110")
        cache = json.load(open(os.path.join(g, ".spend-cache.json"), encoding="utf-8"))
        self.assertEqual(cache["files"][path]["off"], os.path.getsize(path))
        # grown: a repeat of an old message id (rewind/replay) once more, a new one, and a half-written line
        self.transcript("sess-a", [line(self.m(4), "x", 100), line(self.m(5), "z", 1000), '{"type":"assis'], mode="a")
        self.assertEqual(self.measure(g), "1110")
        # the cached bytes are trusted: a changed old line isn't re-read…
        text = open(path, encoding="utf-8").read().replace('"input_tokens":100', '"input_tokens":200', 1)
        open(path, "w", encoding="utf-8").write(text)
        self.assertEqual(self.measure(g), "1110")
        # …but a shorter (rewritten) transcript, or a broken cache, is read again in full
        self.transcript("sess-a", [line(self.m(2), "x", 300)])
        self.assertEqual(self.measure(g), "300")
        open(os.path.join(g, ".spend-cache.json"), "w").write("{broken")
        self.assertEqual(self.measure(g), "300")

    def test_other_lines_are_not_usage(self):
        g = self.goal("one")
        self.activity([(self.m(1), "sess-a", g)])
        user = json.dumps({"message": {"role": "user", "content": "usage"}, "type": "user", "timestamp": utc(self.m(2)),
                           "toolUseResult": {"usage": {"input_tokens": 5000}}}, separators=(",", ":")) + "\n"
        attach = json.dumps({"type": "attachment", "attachment": {"message": {"id": "q", "role": "assistant",
                             "usage": {"input_tokens": 9000}}, "type": "assistant"}, "timestamp": utc(self.m(2))},
                            separators=(",", ":")) + "\n"
        loose = json.dumps({"type": "assistant", "timestamp": utc(self.m(3)), "message": {"id": "w", "usage": {
            "input_tokens": 7, "output_tokens": 3}}}) + "\n"  # spaced JSON: parsed whole
        self.transcript("sess-a", [user, attach, loose, line(self.m(4), "k", 40)])
        self.assertEqual(self.measure(g), "50")

    def test_claude_config_dir_holds_the_transcripts(self):
        g = self.goal("one")
        self.activity([(self.m(1), "sess-a", g)])
        self.cfg = os.path.join(self.tmp, "cfg")
        self.transcript("sess-a", [line(self.m(2), "x", 100)])
        self.assertEqual(self.measure(g), "100")

    def test_cli_writes_the_budget(self):
        g = self.goal("one")
        self.activity([(self.m(1), "sess-a", g)])
        self.transcript("sess-a", [line(self.m(2), "x", 150_000)])
        r = subprocess.run([sys.executable, os.path.join(S, "spend.py"), self.plan(g), "--write"],
                           capture_output=True, text=True, env=self.env())
        self.assertIn("spend=150k pct=", r.stdout, r.stderr)
        self.assertIn("budget: ~150k /", self.read(self.plan(g)))


if __name__ == "__main__":
    unittest.main(verbosity=1, warnings="ignore")
