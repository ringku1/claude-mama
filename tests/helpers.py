"""Shared test scaffolding: a throwaway HOME and repo per test, scripts run as subprocesses.

Never touches the real ~/.claude: every script runs with HOME set to a temp dir and a fake
CLAUDE_CODE_SESSION_ID.
"""
import atexit
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

# Every temp dir the tests make (homes, repos, big transcripts) goes under one root that is
# removed when the run ends, so test runs leave nothing behind in the system temp folder.
_ROOT = tempfile.mkdtemp(prefix="mama-tests-")
tempfile.tempdir = _ROOT
atexit.register(shutil.rmtree, _ROOT, True)

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
        e["USERPROFILE"] = self.home  # Windows: expanduser reads USERPROFILE, not HOME
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
        """Replace the template step/criterion rows with real ones (research already logged)."""
        p = self.plan(goal)
        self.run_s("log.py", os.path.join(goal, "log.md"), "E", "research: 2 findings, 1 cases, 0 open")
        self.run_s("log.py", os.path.join(goal, "log.md"), "E", "expectations: 9 settled, 0 asked")
        self.run_s("log.py", os.path.join(goal, "log.md"), "E", "playback: confirmed")
        s = self.read(p)
        s = re.sub(r"^\| C1 .*$", "| C1  | it works | S1 | — |", s, flags=re.M)
        s = re.sub(r"^\| S1 .*$", "| S1  | build | thing | — | a.go | go test | todo | 0 | 10m |  |  |  |", s, flags=re.M)
        s = s.replace("budget: ~0k / —", "budget: ~0k / M")  # a full goal's approval needs a ceiling
        open(p, "w", encoding="utf-8").write(s)
