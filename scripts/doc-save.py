#!/usr/bin/env python3
"""Save the page /mama doc built into the goal's folder, and keep its link.

Usage:
  doc-save.py <goal dir> [<page.html>] [--url <link>]

<goal dir> is <store>/<slug> (it must hold plan.md). Alone, it prints the link on record. With
<page.html>, the page is copied to <goal dir>/doc.html; it is refused unless it is a whole HTML
page with its diagrams as inline <svg> and no scripts loaded from elsewhere, so it draws the same
on claude.ai and opened from disk. With --url, the published link goes to <goal dir>/doc.url. It always prints the link on
record, so a re-run updates the same page. File tools treat .claude/ as sensitive; this script is
how the page gets there.
"""
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402


class Scan(HTMLParser):
    """Notes inline <svg> diagrams, Mermaid diagram markup, and <script src> loads."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.svg = self.mermaid = False
        self.external = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.svg = self.svg or tag == "svg"
        self.mermaid = self.mermaid or "mermaid" in (a.get("class") or "").lower().split()
        if tag == "script" and a.get("src"):
            self.external.append(a["src"])


def problems(html):
    out = []
    if not re.search(r"<html\b", html, re.I) or not re.search(r"</html>", html, re.I):
        out.append("it isn't a whole HTML page (no <html> … </html>)")
    scan = Scan()
    scan.feed(html)
    scan.close()
    if scan.mermaid:
        out.append("it has Mermaid diagrams — draw them as inline <svg> instead")
    elif not scan.svg:
        out.append("it has no diagram — draw the flow as inline <svg>")
    if scan.external:
        out.append(f"it loads scripts from elsewhere ({', '.join(scan.external[:3])}) — keep it self-contained")
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
