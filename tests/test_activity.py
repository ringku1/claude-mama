"""activity.record never fails a write: an unwritable ~/.claude/mama only costs the ownership line."""
import os
import stat
import unittest

from helpers import Base


@unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                 "needs POSIX permissions and a non-root user")
class UnwritableHome(Base):
    def setUp(self):
        super().setUp()
        self.goal = self.new_goal()
        self.mama = os.path.join(self.home, ".claude", "mama")
        log = os.path.join(self.mama, "activity.log")
        if os.path.exists(log):
            os.remove(log)
        os.chmod(self.mama, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, self.mama, 0o755)

    def test_log_still_writes_and_exits_0(self):
        out = self.run_s("log.py", os.path.join(self.goal, "log.md"), "E", "note: still here", sid="sess-b")
        self.assertIn("note: still here", self.read(os.path.join(self.goal, "log.md")))
        self.assertIn("mama: can't write", out)
        self.assertIn("this session's ownership isn't recorded", out)
        self.assertEqual(out.count("mama: can't write"), 1, out)

    def test_plan_set_still_writes_and_exits_0(self):
        out = self.run_s("plan-set.py", self.plan(self.goal), "--header", "branch=feat/ro", sid="sess-b")
        self.assertIn("branch: feat/ro", self.read(self.plan(self.goal)))
        self.assertIn("mama: can't write", out)


if __name__ == "__main__":
    unittest.main()
