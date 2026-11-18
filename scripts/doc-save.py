#!/usr/bin/env python3
"""Save the page /mama doc built into the goal's folder, and keep its link.

Usage:
  doc-save.py <goal dir> [<page.html>] [--url <link>]

<goal dir> is <store>/<slug> (it must hold plan.md). Alone, it prints the link on record. With
<page.html>, the page is copied to <goal dir>/doc.html; it is refused when it isn't a whole HTML
page, or has Mermaid diagrams but doesn't load Mermaid itself (opened from disk they wouldn't
draw). With --url, the published link goes to <goal dir>/doc.url. It always prints the link on
record, so a re-run updates the same page. File tools treat .claude/ as sensitive; this script is
how the page gets there.
"""
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402


# An import whose module specifier names Mermaid. Static `import … from "…mermaid…"` works only in
# a module script; dynamic `import("…mermaid…")` works in any script. The import clause is
# whitespace-separated tokens, so a long run of words after `import` can't backtrack badly.
STATIC = re.compile(r"(?<![.\w$])import\s*(?:[\w$*{},]+(?:\s+[\w$*{},]+)*\s*from\s*)?['\"][^'\"]*(?i:mermaid)")
DYNAMIC = re.compile(r"(?<![.\w$])import\s*\(\s*['\"`][^'\"`]*(?i:mermaid)")
# Script types a browser runs (the HTML spec's JavaScript MIME types, plus module).
JS_TYPES = {"", "module", "text/javascript", "application/javascript", "text/ecmascript", "application/ecmascript",
            "application/x-javascript", "application/x-ecmascript", "text/x-javascript", "text/x-ecmascript",
            "text/jscript", "text/livescript"}


class MermaidScan(HTMLParser):
    """Notes whether any element has the class token "mermaid", and whether any <script> loads it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.diagrams = False
        self.loader = False
        self.script = None  # (is a module, text) of the JS <script> being read, else None

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "class" and value and "mermaid" in value.split():
                self.diagrams = True
        if tag == "script":
            a = dict(attrs)
            kind = (a.get("type") or "").split(";")[0].strip().lower()
            if kind not in JS_TYPES or "nomodule" in a:  # scripts a modern browser doesn't run
                return
            if "src" in a:  # the browser ignores a src script's own text
                self.loader = self.loader or "mermaid" in (a["src"] or "").lower()
            else:
                self.script = (kind == "module", [])

    def handle_data(self, data):
        if self.script is not None:
            self.script[1].append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            module, text = self.script
            text = "".join(text)
            if DYNAMIC.search(text) or (module and STATIC.search(text)):
                self.loader = True
            self.script = None


def problems(html):
    out = []
    if not re.search(r"<html\b", html, re.I) or not re.search(r"</html>", html, re.I):
        out.append("it isn't a whole HTML page (no <html> … </html>)")
    scan = MermaidScan()
    scan.feed(html)
    scan.close()
    if scan.diagrams and not scan.loader:
        out.append("it has Mermaid diagrams but nothing loads Mermaid (a <script src=…mermaid…>, or an import of it;"
                   " a static import needs <script type=\"module\">)")
    return out


def main():
    args = sys.argv[1:]
    url = None
    if "--url" in args:
        i = args.index("--url")
        if i + 1 >= len(args):
            sys.exit(__doc__)
        raw = args[i + 1]
        url = raw.strip()
        del args[i:i + 2]
    if not args or len(args) > 2:
        sys.exit(__doc__)
    goal = args[0]
    if not os.path.isfile(os.path.join(goal, "plan.md")):
        sys.exit(f"REFUSED: {goal} is not a goal folder (no plan.md)")
    if url is not None and not re.match(r"https?://\S+$", url):
        sys.exit(f"REFUSED: {raw!r} is not a link")
    if len(args) == 2:
        try:
            with open(args[1], encoding="utf-8") as f:
                html = f.read()
        except UnicodeDecodeError:
            sys.exit(f"REFUSED: {args[1]} isn't UTF-8 text")
        except OSError:
            sys.exit(f"REFUSED: {args[1]} not found or unreadable")
        bad = problems(html)
        if bad:
            sys.exit("REFUSED: the page " + "; ".join(bad) + ".")
        fileio.write_atomic(os.path.join(goal, "doc.html"), html)
        print(f"saved {os.path.join(goal, 'doc.html')}")
    url_file = os.path.join(goal, "doc.url")
    if url:
        fileio.write_atomic(url_file, url + "\n")
    if os.path.isfile(url_file):
        with open(url_file, encoding="utf-8") as f:
            print(f"doc.url: {f.read().strip()}")
    else:
        print("doc.url: none yet")


if __name__ == "__main__":
    main()
