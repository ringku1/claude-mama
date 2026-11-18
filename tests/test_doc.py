#!/usr/bin/env python3
"""doc-save.py, in a throwaway HOME. Run: python3 tests/test_doc.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_mama import Base  # noqa: E402

MERMAID = '<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>'


class DocSave(Base):
    def page(self, body):
        p = os.path.join(self.tmp, "page.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        return p

    def test_saves_the_page_and_keeps_the_link(self):
        goal = self.new_goal()
        out = self.run_s("doc-save.py", goal, self.page("<!doctype html><html><body>hi</body></html>"))
        self.assertIn("doc.url: none yet", out)
        self.assertIn("hi", self.read(os.path.join(goal, "doc.html")))
        self.run_s("doc-save.py", goal, "--url", "https://claude.ai/code/artifact/abc")
        self.assertIn("doc.url: https://claude.ai/code/artifact/abc", self.run_s("doc-save.py", goal))

    def test_mermaid_needs_its_script(self):
        goal = self.new_goal()
        bare = '<html><pre class="mermaid">graph TD; A-->B</pre></html>'
        self.assertIn("no <script", self.run_s("doc-save.py", goal, self.page(bare), ok=False))
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.html")))
        self.run_s("doc-save.py", goal, self.page(bare.replace("<html>", "<html>" + MERMAID)))

    def test_refuses_a_partial_page_a_bad_link_and_a_non_goal(self):
        goal = self.new_goal()
        self.assertIn("whole HTML page", self.run_s("doc-save.py", goal, self.page("<div>hi</div>"), ok=False))
        self.assertIn("not a link", self.run_s("doc-save.py", goal, "--url", "later", ok=False))
        self.assertIn("not a goal folder", self.run_s("doc-save.py", self.tmp, ok=False))
        self.run_s("doc-save.py", ok=False)


if __name__ == "__main__":
    unittest.main()
