#!/usr/bin/env python3
"""doc-save.py, in a throwaway HOME. Run: python3 tests/test_doc.py"""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Base  # noqa: E402

PAGE = "<!doctype html><html><body><svg><text>flow</text></svg>hi</body></html>"


class DocSave(Base):
    def page(self, body):
        p = os.path.join(self.tmp, "page.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        return p

    def test_saves_the_page_and_keeps_the_link(self):
        goal = self.new_goal()
        out = self.run_s("doc-save.py", goal, self.page(PAGE))
        self.assertIn("doc.url: none yet", out)
        self.assertIn("hi", self.read(os.path.join(goal, "doc.html")))
        self.run_s("doc-save.py", goal, "--url", "https://claude.ai/code/artifact/abc")
        self.assertIn("doc.url: https://claude.ai/code/artifact/abc", self.run_s("doc-save.py", goal))

    def test_diagrams_are_inline_svg(self):
        goal = self.new_goal()
        cases = [  # (name, page, refusal or None)
            ("an inline script is fine", PAGE.replace("</body>", "<script>document.body.dataset.t='d'</script></body>"), None),
            ("no diagram", "<html><body>hi</body></html>", "no diagram"),
            ("Mermaid markup", '<html><svg></svg><pre class="Diagram mermaid">graph TD; A-->B</pre></html>', "Mermaid"),
            ("a script from elsewhere", PAGE.replace("<body>", '<body><script src="https://cdn.example/x.js"></script>'),
             "loads scripts from elsewhere"),
        ]
        for name, page, refusal in cases:
            with self.subTest(name):
                out = self.run_s("doc-save.py", goal, self.page(page), ok=refusal is None)
                if refusal:
                    self.assertIn(refusal, out)
        self.assertIn("document.body", self.read(os.path.join(goal, "doc.html")))

    def test_cited_code_must_be_on_the_goals_branch(self):
        goal = self.new_goal()
        git = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t"]
        for path in ("apps/api/course/service.go", "apps/web/a/x/service.go", "apps/web/b/x/service.go"):
            os.makedirs(os.path.join(self.repo, os.path.dirname(path)), exist_ok=True)
            with open(os.path.join(self.repo, path), "w") as f:
                f.write("package x\n\nfunc A() {}\n")
        subprocess.run(git + ["checkout", "-q", "-b", "feat/x"], check=True)
        subprocess.run(git + ["add", "apps"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "x"], check=True)
        self.run_s("plan-set.py", self.plan(goal), "--header", "branch=feat/x")

        def cite(refs):
            return PAGE.replace("hi", " ".join(f'<span class="loc">{r}</span>' for r in refs))
        ok = ["apps/api/course/service.go:3", "api/course/service.go:1", "a/x/service.go:2",
              "x/service.go:99"]  # full, shortened, and ambiguous (not checked)
        self.assertIn("saved", self.run_s("doc-save.py", goal, self.page(cite(ok))))
        for ref, why in (("apps/api/course/service.go:4", "the file has 3 lines"),
                         ("apps/api/course/gone.go:1", "no such file on feat/x"),
                         ("course/service.go:0", "the file has 3 lines")):
            with self.subTest(ref):
                out = self.run_s("doc-save.py", goal, self.page(cite(ok + [ref])), ok=False)
                self.assertIn("cites code that isn't there", out)
                self.assertIn(why, out)
        self.run_s("plan-set.py", self.plan(goal), "--header", "branch=feat/gone")
        out = self.run_s("doc-save.py", goal, self.page(cite(["apps/api/course/gone.go:1"])))
        self.assertIn("weren't checked", out)

    def test_a_blank_link_is_refused(self):
        goal = self.new_goal()
        out = self.run_s("doc-save.py", goal, self.page(PAGE), "--url", "  ", ok=False)
        self.assertIn("'  ' is not a link", out)
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.html")))
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.url")))

    def test_a_page_that_isnt_utf8_is_refused(self):
        goal = self.new_goal()
        p = os.path.join(self.tmp, "latin1.html")
        with open(p, "wb") as f:
            f.write(PAGE.replace("hi", "caf\u00e9").encode("latin-1"))
        out = self.run_s("doc-save.py", goal, p, ok=False)
        self.assertIn("isn't UTF-8 text", out)
        self.assertNotIn("Traceback", out)
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.html")))

    def test_a_bad_link_with_a_page_writes_nothing(self):
        goal = self.new_goal()
        out = self.run_s("doc-save.py", goal, self.page(PAGE), "--url", "later", ok=False)
        self.assertIn("REFUSED", out)
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.html")))

    def test_a_missing_or_directory_page_is_refused(self):
        goal = self.new_goal()
        for path in (os.path.join(self.tmp, "nope.html"), self.tmp):
            out = self.run_s("doc-save.py", goal, path, ok=False)
            self.assertIn("not found or unreadable", out)
            self.assertNotIn("Traceback", out)

    def test_refuses_a_partial_page_a_bad_link_and_a_non_goal(self):
        goal = self.new_goal()
        self.assertIn("whole HTML page", self.run_s("doc-save.py", goal, self.page("<div><svg></svg></div>"), ok=False))
        self.assertIn("not a link", self.run_s("doc-save.py", goal, "--url", "later", ok=False))
        self.assertIn("not a goal folder", self.run_s("doc-save.py", self.tmp, ok=False))
        self.run_s("doc-save.py", ok=False)


if __name__ == "__main__":
    unittest.main()
