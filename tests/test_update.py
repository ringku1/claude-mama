#!/usr/bin/env python3
"""Self-update of a git install: scripts/self-update.py and the hook's once-a-day start. Run: python3 tests/test_update.py"""
import json
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import HOOK, S, Base  # noqa: E402

UPDATE = os.path.join(S, "self-update.py")


def git(cwd, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main",
                        "-C", cwd, *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class SelfUpdate(Base):
    def setUp(self):
        super().setUp()
        self.origin = os.path.join(self.home, "origin")
        self.install = os.path.join(self.home, "install")
        os.makedirs(self.origin)
        git(self.origin, "init", "-q", "-b", "main")
        open(os.path.join(self.origin, "SKILL.md"), "w").write("v1\n")
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-q", "-m", "v1")
        git(self.home, "clone", "-q", self.origin, self.install)
        open(os.path.join(self.origin, "SKILL.md"), "w").write("v2\n")
        git(self.origin, "commit", "-q", "-am", "v2")

    def update(self, **env):
        e = {**self.env(), "MAMA_AUTO_UPDATE": "1", **env}
        subprocess.run([sys.executable, UPDATE, self.install], env=e, check=True, capture_output=True)
        return open(os.path.join(self.install, "SKILL.md")).read()

    def test_clean_main_is_fast_forwarded(self):
        self.assertEqual(self.update(), "v2\n")

    def test_off_switch(self):
        self.assertEqual(self.update(MAMA_AUTO_UPDATE="0"), "v1\n")

    def test_local_changes_are_left_alone(self):
        open(os.path.join(self.install, "notes.txt"), "w").write("mine\n")
        self.assertEqual(self.update(), "v1\n")

    def test_other_branch_is_left_alone(self):
        git(self.install, "checkout", "-q", "-b", "feat/x")
        self.assertEqual(self.update(), "v1\n")


class HookStartsIt(Base):
    def hook(self, **env):
        # the started updater must not touch the checkout these tests run from: no git repo for it
        e = {**self.env(), "GIT_DIR": os.path.join(self.home, "no-repo")}
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        inp = json.dumps({"cwd": self.repo, "session_id": "sess-a"})
        r = subprocess.run([sys.executable, HOOK, "stop"], input=inp, env=e, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def stamp(self):
        return os.path.join(self.home, ".claude", "mama", ".update-check")

    def test_once_a_day(self):
        self.hook(MAMA_AUTO_UPDATE=None)
        self.assertTrue(os.path.exists(self.stamp()))
        day_ago = time.time() - 3600
        os.utime(self.stamp(), (day_ago, day_ago))
        self.hook(MAMA_AUTO_UPDATE=None)
        self.assertAlmostEqual(os.path.getmtime(self.stamp()), day_ago, delta=1)  # checked an hour ago: skipped
        old = time.time() - 25 * 3600
        os.utime(self.stamp(), (old, old))
        self.hook(MAMA_AUTO_UPDATE=None)
        self.assertGreater(os.path.getmtime(self.stamp()), old + 3600)

    def test_off_switch_and_plugin_installs(self):
        self.hook(MAMA_AUTO_UPDATE="0")
        self.hook(MAMA_AUTO_UPDATE=None, CLAUDE_PLUGIN_ROOT=self.home)
        self.assertFalse(os.path.exists(self.stamp()))


if __name__ == "__main__":
    unittest.main()
