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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402


# "mermaid" as a whole class token, not part of language-mermaid or mermaid-legend.
CLASS = r"class=[\"'](?:[^\"']*\s)?mermaid[\"'\s]"
# A loader: <script src=…mermaid…>, or an inline <script type="module"> that imports Mermaid.
SRC = r"<script[^>]+src=[^>]*mermaid"
ESM = r"<script\b[^>]*type=[\"']?module\b[^>]*>(?:(?!</script)[^;])*?\bimport\b(?:(?!</script)[^;])*?mermaid"


def problems(html):
    out = []
    if not re.search(r"<html\b", html, re.I) or not re.search(r"</html>", html, re.I):
        out.append("it isn't a whole HTML page (no <html> … </html>)")
    if re.search(CLASS, html) and not (re.search(SRC, html, re.I) or re.search(ESM, html, re.I | re.S)):
        out.append("it has Mermaid diagrams but no <script src=…mermaid…> to draw them")
    return out


def main():
    args = sys.argv[1:]
    url = None
    if "--url" in args:
        i = args.index("--url")
        if i + 1 >= len(args):
            sys.exit(__doc__)
        url = args[i + 1].strip()
        del args[i:i + 2]
    if not args or len(args) > 2:
        sys.exit(__doc__)
    goal = args[0]
    if not os.path.isfile(os.path.join(goal, "plan.md")):
        sys.exit(f"REFUSED: {goal} is not a goal folder (no plan.md)")
    if url and not re.match(r"https?://\S+$", url):
        sys.exit(f"REFUSED: {url!r} is not a link")
    if len(args) == 2:
        try:
            with open(args[1], encoding="utf-8") as f:
                html = f.read()
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
