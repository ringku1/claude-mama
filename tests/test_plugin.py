#!/usr/bin/env python3
"""mama as a Claude Code plugin: manifests, hooks.json, and install.py refusing to double up. Run: python3 tests/test_plugin.py

Never touches the real ~/.claude: HOME, USERPROFILE and CLAUDE_CONFIG_DIR point into a temp dir.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_mama import SKILL  # noqa: E402

PLUGIN = os.path.join(SKILL, ".claude-plugin", "plugin.json")
MARKET = os.path.join(SKILL, ".claude-plugin", "marketplace.json")
HOOKS = os.path.join(SKILL, "hooks", "hooks.json")
INSTALL = os.path.join(SKILL, "install.py")
BASH = shutil.which("bash")
CLAUDE = shutil.which("claude")
# install.py's EVENTS: event -> (mama-hook.py mode, matcher)
EVENTS = {"PreCompact": ("precompact", None), "SessionStart": ("sessionstart", "compact"), "Stop": ("stop", None)}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Manifests(unittest.TestCase):
    def test_plugin_and_marketplace_agree(self):
        plugin, market = load(PLUGIN), load(MARKET)
        self.assertEqual(plugin["name"], "mama")
        self.assertTrue(plugin.get("version") and plugin.get("description"))
        self.assertTrue(market["name"] and market["owner"]["name"])
        self.assertNotIn(market["name"], ("claude-plugins-official", "anthropic-marketplace"))
        [entry] = market["plugins"]
        self.assertEqual(entry["name"], plugin["name"])  # install id mama@<marketplace> = skill prefix
        self.assertEqual(entry["source"], "./")  # the repo root is the plugin, so SKILL.md stays put

    def test_skill_is_the_root_skill_md(self):
        # a root SKILL.md loads only with no skills/ dir and no "skills" key; its name gives /mama:mama, which /mama also reaches
        self.assertFalse(os.path.exists(os.path.join(SKILL, "skills")))
        self.assertNotIn("skills", load(PLUGIN))
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            self.assertRegex(f.read(), r"(?m)\A---\n(?:.*\n)*?name: mama\n")

    def test_hooks_match_install_py(self):
        hooks = load(HOOKS)["hooks"]
        self.assertEqual(set(hooks), set(EVENTS))
        for event, (mode, matcher) in EVENTS.items():
            [entry] = hooks[event]
            self.assertEqual(entry.get("matcher"), matcher, event)
            [h] = entry["hooks"]
            self.assertEqual(h["type"], "command")
            self.assertNotIn("args", h)  # shell form: Git Bash on Windows, so scripts/py can find Python
            self.assertEqual(h["command"], 'bash "${CLAUDE_PLUGIN_ROOT}/scripts/py" '
                                           f'"${{CLAUDE_PLUGIN_ROOT}}/hooks/mama-hook.py" {mode}')
            for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"]+)", h["command"]):
                self.assertTrue(os.path.isfile(os.path.join(SKILL, rel)), rel)

    @unittest.skipUnless(BASH, "needs bash")
    def test_hook_commands_run(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        for event, (mode, _) in EVENTS.items():
            cmd = load(HOOKS)["hooks"][event][0]["hooks"][0]["command"]
            cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", SKILL.replace(os.sep, "/"))
            r = subprocess.run([BASH, "-c", cmd], input=json.dumps({"session_id": "t", "cwd": tmp}),
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, f"{mode}: {r.stderr}")
            self.assertEqual(r.stderr, "", mode)

    @unittest.skipUnless(CLAUDE, "needs the claude CLI")
    def test_claude_plugin_validate(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        r = subprocess.run([CLAUDE, "plugin", "validate", SKILL], capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, CLAUDE_CONFIG_DIR=tmp))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Validation passed", r.stdout + r.stderr)


class InstallWithPlugin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        self.claude = os.path.join(self.home, ".claude")
        os.makedirs(self.claude)
        self.path = os.path.join(self.claude, "settings.json")

    def write(self, settings):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(settings, f)

    def install(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        env.update(HOME=self.home, USERPROFILE=self.home)
        r = subprocess.run([sys.executable, INSTALL, *args], capture_output=True, text=True, env=env)
        self.assertNotIn("Traceback", r.stderr)
        return r

    def linked(self):
        return os.path.lexists(os.path.join(self.claude, "skills", "mama"))

    def test_enabled_plugin_blocks_the_one_liner(self):
        self.write({"theme": "dark", "enabledPlugins": {"mama@claude-mama": True}})
        r = self.install()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("mama@claude-mama plugin is enabled", r.stderr)
        self.assertIn("claude plugin uninstall mama@claude-mama", r.stderr.strip().splitlines()[-1])
        self.assertEqual(load(self.path), {"theme": "dark", "enabledPlugins": {"mama@claude-mama": True}})
        self.assertFalse(self.linked())
        self.assertFalse(os.path.exists(self.path + ".bak"))

    def test_earlier_one_liner_hooks_are_removed(self):
        other = {"hooks": [{"type": "command", "command": "x"}]}
        self.write({"hooks": {"Stop": [other]}})
        self.assertEqual(self.install().returncode, 0)  # one-liner first
        self.assertEqual(len(load(self.path)["hooks"]["Stop"]), 2)
        s = load(self.path)
        s["enabledPlugins"] = {"mama@some-fork": True}  # then the plugin, from any marketplace
        self.write(s)
        r = self.install()
        self.assertEqual(r.returncode, 1)
        self.assertIn("removed", r.stderr)
        self.assertEqual(load(self.path)["hooks"], {"Stop": [other]})

    def test_disabled_or_other_plugins_dont_block(self):
        self.write({"enabledPlugins": {"mama@claude-mama": False, "mamba@x": True}})
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(set(load(self.path)["hooks"]), set(EVENTS))
        self.assertTrue(self.linked())

    def test_remove_still_works_with_the_plugin_enabled(self):
        self.write({})
        self.install()
        s = load(self.path)
        s["enabledPlugins"] = {"mama@claude-mama": True}
        self.write(s)
        r = self.install("--remove")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("hooks", load(self.path))


if __name__ == "__main__":
    unittest.main()
