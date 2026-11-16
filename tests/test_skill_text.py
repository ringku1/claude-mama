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


if __name__ == "__main__":
    unittest.main()
