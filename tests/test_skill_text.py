"""SKILL.md loads on every /mama and is re-attached (and cut short) after a compaction, so it stays
small: the flow and the invariants, with details in rules/ files it points to."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_MAX_CHARS = 16_000


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class SkillText(unittest.TestCase):
    def test_skill_md_stays_small(self):
        self.assertLessEqual(len(read("SKILL.md")), SKILL_MAX_CHARS,
                             "SKILL.md grew: move detail into a rules/ file it points to")

    def test_every_rules_file_named_exists(self):
        texts = [read("SKILL.md")] + [read(os.path.join("rules", f)) for f in os.listdir(os.path.join(ROOT, "rules"))]
        named = {m for t in texts for m in re.findall(r"rules/([\w-]+\.md)", t)}
        self.assertTrue(named)
        for name in named:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "rules", name)), name)

    def test_every_rules_file_is_reachable_from_skill_md(self):
        skill = read("SKILL.md")
        for name in os.listdir(os.path.join(ROOT, "rules")):
            self.assertIn(f"rules/{name}", skill, f"rules/{name} is never pointed to, so it is never read")

    def test_every_log_line_the_guards_check_is_still_taught(self):
        # plan-set.py, close-check.py and the Stop hook look for these lines; a trim that drops one
        # from the instructions leaves the model unable to satisfy its guard.
        text = "\n".join([read("SKILL.md")] + [read(os.path.join("rules", f)) for f in os.listdir(os.path.join(ROOT, "rules"))]
                         + [read(os.path.join("templates", "log.md"))])
        for token in ("E research", "E research none", "E expectations", "E playback", "E db", "E dispatch",
                      "E wait", "E waiting", "E resume", "E hunt", "E hunt none", "E learn none", "E profile none",
                      "E pushed", "E compaction", "known issues", "tag: user", "/code-review", "D budget"):
            self.assertIn(token, text, f"{token!r} is checked by a guard but no longer taught")
        for script in os.listdir(os.path.join(ROOT, "scripts")):
            if script.endswith(".py") and script not in ("fileio.py", "clock.py", "activity.py", "overview.py", "self-update.py"):
                self.assertIn(script, text, f"scripts/{script} is never mentioned, so it is never run")

    def test_every_section_pointed_to_exists(self):
        texts = [read("SKILL.md")] + [read(os.path.join("rules", f)) for f in os.listdir(os.path.join(ROOT, "rules"))]
        pointers = {m for t in texts for m in re.findall(r"rules/([\w-]+\.md)`? (?:→|§) \"?([A-Z][\w ]*?)\"?(?=[.;,)\s]|$)", t)}
        self.assertTrue(pointers)
        for name, section in pointers:
            target = read(os.path.join("rules", name))
            anchors = re.findall(r"^#+ (.*)$", target, re.M) + re.findall(r"\*\*([^*]+)\*\*", target)
            self.assertTrue(any(a.startswith(section.strip()) for a in anchors), f"rules/{name} has no section {section!r}")


if __name__ == "__main__":
    unittest.main()
