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

    def measure(self, goal, deadline=None):
        arg = "" if deadline is None else f", deadline={deadline!r}"
        code = f"import sys; sys.path.insert(0, {S!r}); import spend; print(spend.measure({self.plan(goal)!r}{arg}))"
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

    def cache(self, goal):
        return json.load(open(os.path.join(goal, ".spend-cache.json"), encoding="utf-8"))["files"]

    def test_cache_saved_before_deadline(self):
        g = self.goal("one")
        self.activity([(self.m(1), "sess-a", g)])
        path = self.transcript("sess-a", [line(self.m(k), f"x{k}", 1 << k) for k in (2, 3, 4)],
                               sub=[line(self.m(5), "s1", 1000)])
        # past its deadline a call still makes progress, saves it, and returns what it has so far
        first = self.measure(g, deadline=0)
        off = self.cache(g)[path]["off"]
        self.assertTrue(0 < off < os.path.getsize(path), off)
        self.assertNotEqual(first, str(4 + 8 + 16 + 1000))
        # each later call resumes from the saved offsets instead of starting over
        for _ in range(10):
            last = self.measure(g, deadline=0)
            self.assertGreaterEqual(self.cache(g)[path]["off"], off)
            off = self.cache(g)[path]["off"]
        self.assertEqual(last, str(4 + 8 + 16 + 1000))
        self.assertEqual(self.measure(g), str(4 + 8 + 16 + 1000))

    def old_goal(self):
        """Goal `old` started before activity.log; sess-a wrote to it (m1) before the record began (m10)."""
        a, b = self.goal("old", start=self.m(-30)), self.goal("new", start=self.m(-30))
        write = json.dumps({"type": "assistant", "timestamp": utc(self.m(1)), "message": {"id": "w", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": f"python3 x/log.py {a}/log.md E go"}}]}}) + "\n"
        self.activity([(self.m(10), "sess-a", b)])
        return a, b, write

    def test_unmatched_candidates_pruned(self):
        a, b, write = self.old_goal()
        pa = self.transcript("sess-a", [write, line(self.m(2), "m1", 100), line(self.m(12), "m2", 5000)])
        pc = self.transcript("sess-c", [line(self.m(k), f"c{k}", 7) for k in range(2, 9)])  # never wrote to `old`
        self.assertEqual(self.measure(a), "100")
        files = self.cache(a)
        self.assertIn("use", files[pa])
        self.assertNotIn("use", files[pc])
        self.assertNotIn("ids", files[pc])
        self.assertEqual(files[pc]["off"], os.path.getsize(pc))
        self.assertEqual(self.measure(a), "100")  # the slim entry still counts as read
        # an unmatched transcript that later becomes a recorded session is read again in full
        self.activity([(self.m(3), "sess-c", a), (self.m(10), "sess-a", b)])
        self.assertEqual(self.measure(a), str(100 + 7 * 6))

    def test_session_owner_first_line_still_found(self):
        a, b, write = self.old_goal()
        owner = json.dumps({"type": "session-owner", "sessionId": "sess-a"}) + "\n"
        self.transcript("sess-a", [owner, write, line(self.m(2), "m1", 100), line(self.m(12), "m2", 5000)])
        self.assertEqual(self.measure(a), "100")
        self.assertEqual(self.measure(b), "5000")

    def run_py(self, body):
        """Run body (python, after `import spend`) in a subprocess with the test env; its stdout lines."""
        code = f"import sys, glob; sys.path.insert(0, {S!r}); import spend\n" + body
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.split()

    def test_scan_cut_returns_on_any_line(self):
        sys.path.insert(0, S)
        import spend
        user = json.dumps({"message": {"role": "user", "content": "x" * 5000}, "type": "user",
                           "timestamp": utc(self.m(2))}, separators=(",", ":")) + "\n"
        path = self.transcript("sess-a", [user] * 50 + [line(self.m(3), "a", 100)])
        e = spend.scan(path, {}, 0, deadline=0)
        self.assertTrue(e["cut"])
        self.assertEqual(e["off"], len(user.encode()))  # one line of progress, not every tool result

    def test_candidates_dated_once_and_within_deadline(self):
        a, b, write = self.old_goal()
        self.transcript("sess-a", [write, line(self.m(2), "m1", 100)])
        for i in range(5):  # began after the record: their writes are recorded, so they never count
            self.transcript(f"later-{i}", [line(self.m(11 + i), f"l{i}", 9)])
        count = ("n = [0]; f0 = spend._first_ts\n"
                 "def f(x):\n    n[0] += 1\n    return f0(x)\n"
                 "spend._first_ts = f\n")
        # past the deadline the candidate search stops after one file and says so
        out = self.run_py(count + f"print(spend.measure({self.plan(a)!r}, deadline=0), spend.measure.partial, n[0])")
        self.assertEqual(out[1:], ["True", "1"])
        self.assertEqual(self.run_py(f"print(spend.measure({self.plan(a)!r}, deadline=float('inf')))"), ["100"])
        # a transcript already dated is not opened again
        out = self.run_py(count + f"print(spend.measure({self.plan(a)!r}), n[0])")
        self.assertEqual(out, ["100", "0"])

    def test_cut_candidate_search_keeps_found_sessions(self):
        a, b, write = self.old_goal()
        sort = "_g = glob.glob; glob.glob = lambda p: sorted(_g(p))\n"  # a-cand is searched before sess-a
        cand = [line(self.m(k), f"c{k}", 7) for k in range(2, 9)]  # pre-birth, never wrote to `old`
        pc = self.transcript("a-cand", cand)
        self.transcript("sess-a", [write, line(self.m(2), "m1", 100)], sub=[line(self.m(3), "s1", 1000)])
        go = sort + f"print(spend.measure({self.plan(a)!r}, deadline=%s))"
        self.assertEqual(self.run_py(go % "float('inf')"), ["1100"])
        self.transcript("a-cand", cand, mode="a")  # grown: the cut lands on it, before sess-a is reached
        self.run_py(go % "0")
        files = self.cache(a)
        self.assertTrue(all("use" in e for p, e in files.items() if "sess-a" in p), files)
        self.transcript("sess-a", [line(self.m(4), "m2", 20)], mode="a")
        self.assertEqual(self.run_py(go % "float('inf')"), ["1120"])
        self.assertNotIn("use", self.cache(a)[pc])

    def test_grown_slim_candidate_cut_then_session_is_read_in_full(self):
        a, b, write = self.old_goal()
        sort = "_g = glob.glob; glob.glob = lambda p: sorted(_g(p))\n"  # a-cand is searched before sess-a
        cand = [line(self.m(k), f"c{k}", 7) for k in range(2, 9)]  # pre-birth, never wrote to `old`
        pc = self.transcript("a-cand", cand)
        self.transcript("sess-a", [write, line(self.m(2), "m1", 100)])
        go = sort + f"print(spend.measure({self.plan(a)!r}, deadline=%s))"
        self.assertEqual(self.run_py(go % "float('inf')"), ["100"])
        self.assertNotIn("use", self.cache(a)[pc])
        # grown by one line: the search reads it from the slim entry's offset, then is cut before slimming
        self.transcript("a-cand", [line(self.m(9), "c9", 7)], mode="a")
        self.run_py(go % "0")
        # a-cand later turns out to be a session: every one of its tokens counts, not only the new line's
        self.activity([(self.m(3), "a-cand", a), (self.m(10), "sess-a", b)])
        self.assertEqual(self.run_py(go % "float('inf')"), [str(100 + 7 * 7)])

    def test_slim_subagent_entry_is_read_again(self):
        a, b, write = self.old_goal()
        pa = self.transcript("sess-a", [write, line(self.m(2), "m1", 100)], sub=[line(self.m(3), "s1", 1000)])
        go = f"print(spend.measure({self.plan(a)!r}, deadline=float('inf')))"
        self.assertEqual(self.run_py(go), ["1100"])
        # a cache left by an older version: the session's subagent slimmed
        cache = json.load(open(os.path.join(a, ".spend-cache.json"), encoding="utf-8"))
        sub = [p for p in cache["files"] if "subagents" in p][0]
        cache["files"][sub] = {k: cache["files"][sub].get(k) for k in ("size", "off", "first", "last", "writes")}
        open(os.path.join(a, ".spend-cache.json"), "w", encoding="utf-8").write(json.dumps(cache))
        self.assertEqual(self.run_py(go), ["1100"])
        self.assertIn(pa, self.cache(a))

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
