#!/usr/bin/env python3
"""doc-save.py, in a throwaway HOME. Run: python3 tests/test_doc.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Base  # noqa: E402

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
        self.assertIn("nothing loads Mermaid", self.run_s("doc-save.py", goal, self.page(bare), ok=False))
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.html")))
        self.run_s("doc-save.py", goal, self.page(bare.replace("<html>", "<html>" + MERMAID)))

    def test_hyphenated_mermaid_classes_need_no_script(self):
        goal = self.new_goal()
        page = '<html><code class="language-mermaid">x</code><div class="mermaid-legend">y</div></html>'
        self.run_s("doc-save.py", goal, self.page(page))
        self.assertTrue(os.path.exists(os.path.join(goal, "doc.html")))

    def test_an_esm_import_loads_mermaid(self):
        goal = self.new_goal()
        esm = ('<script type="module">\nimport mermaid from '
               "'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs';\n"
               "mermaid.initialize({});\n</script>")
        self.run_s("doc-save.py", goal, self.page('<html><pre class="diagram mermaid">graph TD; A-->B</pre>' + esm + "</html>"))
        self.assertTrue(os.path.exists(os.path.join(goal, "doc.html")))

    def test_mermaid_loader_cases(self):
        esm = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"
        pre = '<pre class="mermaid">graph TD; A-->B</pre>'
        cases = [  # (name, page, saved?)
            ("an import before Mermaid's", '<html>' + pre + '<script type="module">import a from "./a.js";\n'
             'import mermaid from "' + esm + '";</script></html>', True),
            ("a comment after an import is no loader", '<html>' + pre + '<script type="module">'
             'import {a} from "./a.js"\n// mermaid todo</script></html>', False),
            ("a dynamic import in a classic script", '<html>' + pre + '<script>import("' + esm + '")'
             '.then(m => m.default.run());</script></html>', True),
            ("class=\"mermaid\" as text is no diagram", '<html><p>use class="mermaid" on a pre</p></html>', True),
            ("an unquoted class", '<html><pre class=mermaid>graph TD; A-->B</pre></html>', False),
            ("an uppercase CLASS", '<html><pre CLASS="x mermaid">graph TD; A-->B</pre></html>', False),
        ]
        for name, page, saved in cases:
            with self.subTest(name):
                goal = self.new_goal(slug="m" + str(cases.index((name, page, saved))))
                out = self.run_s("doc-save.py", goal, self.page(page), ok=saved)
                self.assertEqual(os.path.exists(os.path.join(goal, "doc.html")), saved, out)
                if not saved:
                    self.assertIn("nothing loads Mermaid", out)

    def test_a_blank_link_is_refused(self):
        goal = self.new_goal()
        out = self.run_s("doc-save.py", goal, self.page("<html>hi</html>"), "--url", "  ", ok=False)
        self.assertIn("'' is not a link", out)
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.html")))
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.url")))

    def test_a_page_that_isnt_utf8_is_refused(self):
        goal = self.new_goal()
        p = os.path.join(self.tmp, "latin1.html")
        with open(p, "wb") as f:
            f.write("<html>caf\u00e9</html>".encode("latin-1"))
        out = self.run_s("doc-save.py", goal, p, ok=False)
        self.assertIn("isn't UTF-8 text", out)
        self.assertNotIn("Traceback", out)
        self.assertFalse(os.path.exists(os.path.join(goal, "doc.html")))

    def test_a_bad_link_with_a_page_writes_nothing(self):
        goal = self.new_goal()
        out = self.run_s("doc-save.py", goal, self.page("<html>hi</html>"), "--url", "later", ok=False)
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
        self.assertIn("whole HTML page", self.run_s("doc-save.py", goal, self.page("<div>hi</div>"), ok=False))
        self.assertIn("not a link", self.run_s("doc-save.py", goal, "--url", "later", ok=False))
        self.assertIn("not a goal folder", self.run_s("doc-save.py", self.tmp, ok=False))
        self.run_s("doc-save.py", ok=False)


if __name__ == "__main__":
    unittest.main()
