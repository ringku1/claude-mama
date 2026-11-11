#!/usr/bin/env python3
"""mama's installers and launchers, tested in a throwaway HOME. Run: python3 tests/test_install.py

Never touches the real ~/.claude: HOME, USERPROFILE and CLAUDE_CONFIG_DIR point into a temp dir.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_mama import SKILL, S  # noqa: E402

INSTALL = os.path.join(SKILL, "install.py")
BASH = shutil.which("bash")


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.claude = os.path.join(self.home, ".claude")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, **extra):
        e = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        e.update(HOME=self.home, USERPROFILE=self.home, **extra)
        return e

    def install(self, *args, ok=True, **extra):
        r = subprocess.run([sys.executable, INSTALL, *args], capture_output=True, text=True, env=self.env(**extra))
        (self.assertEqual if ok else self.assertNotEqual)(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        return r

    def settings(self, base=None):
        with open(os.path.join(base or self.claude, "settings.json"), encoding="utf-8") as f:
            return json.load(f)

    def write_settings(self, text):
        os.makedirs(self.claude, exist_ok=True)
        with open(os.path.join(self.claude, "settings.json"), "w", encoding="utf-8") as f:
            f.write(text)

    def test_registers_and_removes_hooks_keeping_other_settings(self):
        self.write_settings('{"theme": "dark", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}')
        self.install()
        s = self.settings()
        self.assertEqual(s["theme"], "dark")
        self.assertEqual(set(s["hooks"]), {"PreCompact", "SessionStart", "Stop"})
        self.assertEqual(len(s["hooks"]["Stop"]), 2)
        self.install()  # re-run: still one mama entry per event
        self.assertEqual(len(self.settings()["hooks"]["Stop"]), 2)
        self.install("--remove")
        self.assertEqual(self.settings()["hooks"], {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]})

    def test_backup_keeps_the_original(self):
        self.write_settings('{"theme": "original"}')
        self.install()
        self.install()
        self.install("--remove")
        with open(os.path.join(self.claude, "settings.json.bak"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"theme": "original"})

    def test_invalid_settings_is_left_alone(self):
        for bad in ('{"theme": ', '[1, 2]', '{"hooks": []}'):
            self.write_settings(bad)
            r = self.install(ok=False)
            self.assertIn("settings.json", r.stderr)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
            with open(os.path.join(self.claude, "settings.json"), encoding="utf-8") as f:
                self.assertEqual(f.read(), bad)
            self.assertFalse(os.path.exists(os.path.join(self.claude, "settings.json.bak")))

    def test_honours_claude_config_dir(self):
        cfg = os.path.join(self.tmp, "cfg")
        self.install(CLAUDE_CONFIG_DIR=cfg)
        self.assertIn("Stop", self.settings(cfg)["hooks"])
        self.assertEqual(os.path.realpath(os.path.join(cfg, "skills", "mama")), os.path.realpath(SKILL))
        self.assertFalse(os.path.exists(os.path.join(self.claude, "settings.json")))


class Lock(unittest.TestCase):
    def test_runs_a_program_found_on_path(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        if os.name == "nt":  # the case that broke: pnpm is pnpm.cmd
            tool = os.path.join(tmp, "faketool.cmd")
            body = "@echo off\r\necho ran %1\r\nexit /b 3\r\n"
        else:
            tool = os.path.join(tmp, "faketool")
            body = '#!/bin/sh\necho "ran $1"\nexit 3\n'
        with open(tool, "w") as f:
            f.write(body)
        os.chmod(tool, 0o755)
        env = dict(os.environ, PATH=tmp + os.pathsep + os.environ.get("PATH", ""))
        lock = os.path.join(tmp, "x.lock")
        r = subprocess.run([sys.executable, os.path.join(S, "lock.py"), lock, "faketool", "hi"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("ran hi", r.stdout)
        r = subprocess.run([sys.executable, os.path.join(S, "lock.py"), lock, "no-such-tool-xyz"],
                           capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("command not found: no-such-tool-xyz", r.stderr)


@unittest.skipUnless(BASH, "needs bash")
class PyLauncher(unittest.TestCase):
    def test_passes_args_and_exit_code(self):
        r = subprocess.run([BASH, os.path.join(S, "py"), "-c",
                            "import sys; print(sys.version_info >= (3, 8), sys.argv[1:]); sys.exit(4)", "a b", "c"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn("True ['a b', 'c']", r.stdout)

    def test_no_python_is_a_clear_error(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty, True)
        r = subprocess.run([BASH, os.path.join(S, "py"), "-c", "pass"], capture_output=True, text=True,
                           env=dict(os.environ, PATH=empty))
        self.assertEqual(r.returncode, 127)
        self.assertIn("Python 3.8+", r.stderr)


@unittest.skipIf(os.name == "nt" or not BASH, "install.sh is for macOS and Linux")
class InstallSh(unittest.TestCase):
    """install.sh against a local repo, so no network is needed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.origin = os.path.join(self.tmp, "origin.git")
        subprocess.run(["git", "clone", "-q", "--bare", "--no-local", SKILL, self.origin], check=True)
        head = subprocess.run(["git", "-C", SKILL, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "--git-dir", self.origin, "branch", "-f", "mama-test", head], check=True)
        subprocess.run(["git", "--git-dir", self.origin, "symbolic-ref", "HEAD", "refs/heads/mama-test"], check=True)
        self.dest = os.path.join(self.home, ".claude", "skills", "mama")

    def sh(self, repo=None, ok=True):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        env.update(HOME=self.home, MAMA_REPO=repo or self.origin)
        r = subprocess.run([BASH, os.path.join(SKILL, "install.sh")], capture_output=True, text=True, env=env)
        (self.assertEqual if ok else self.assertNotEqual)(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn("fatal:", r.stderr)
        return r.stdout + r.stderr

    def test_install_update_and_failures(self):
        self.assertIn("ready", self.sh())
        self.assertIn("updating", self.sh())
        with open(os.path.join(self.dest, "SKILL.md"), "a") as f:
            f.write("\nmy edit\n")
        self.assertIn("changed locally", self.sh(ok=False))
        subprocess.run(["git", "-C", self.dest, "checkout", "-q", "--", "."], check=True)
        shutil.rmtree(self.origin)
        self.assertIn("internet connection", self.sh(ok=False))
        shutil.rmtree(self.dest)
        self.assertIn("couldn't download", self.sh(repo=os.path.join(self.tmp, "nowhere.git"), ok=False))
        self.assertFalse(os.path.exists(self.dest))


if __name__ == "__main__":
    unittest.main()
