#!/usr/bin/env python3
"""Save the page /mama doc built into the goal's folder, and keep its link.

Usage:
  doc-save.py <goal dir> [<page.html>] [--url <link>]

<goal dir> is <store>/<slug> (it must hold plan.md). Alone, it prints the link on record. With
<page.html>, the page is copied to <goal dir>/doc.html. It is refused when it isn't a whole HTML
page, when its diagrams aren't inline <svg> or it loads scripts from elsewhere (it must draw the
same on claude.ai and opened from disk), and when a `path/file.ext:line` it cites is missing from
the goal's branch (plan.md header) or past that file's end. With --url, the published link goes to
<goal dir>/doc.url. It always prints the link on record, so a re-run updates the same page. File
tools treat .claude/ as sensitive; this script is how the page gets there.
"""
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402


REF = re.compile(r"(?<![\w./-])((?:[\w.@$\[\]-]+/)+[\w.@$\[\]-]+\.[A-Za-z]\w*):(\d+)")


class Scan(HTMLParser):
    """Notes inline <svg> diagrams, Mermaid diagram markup, <script src> loads, and the page's text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.svg = self.mermaid = False
        self.external = []
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.svg = self.svg or tag == "svg"
        self.mermaid = self.mermaid or "mermaid" in (a.get("class") or "").lower().split()
        if tag == "script" and a.get("src"):
            self.external.append(a["src"])


def branch_of(goal):
    with open(os.path.join(goal, "plan.md"), encoding="utf-8") as f:
        m = re.search(r"^base:.*?\| branch: ([^|\s]+)", f.read(), re.M)
    b = m.group(1) if m else ""
    return b if re.match(r"[\w][\w./-]*$", b) and b != "n/a" else None


def bad_refs(goal, text):
    """`path:line` refs the goal's branch doesn't have; [] when there is no branch to check against."""
    branch = branch_of(goal)
    if not branch:
        return []
    git = ["git", "-C", goal]
    rev = next((r for r in (branch, "origin/" + branch) if subprocess.run(
        git + ["rev-parse", "-q", "--verify", r + "^{commit}"], capture_output=True).returncode == 0), None)
    if not rev:
        print(f"note: branch {branch} not found, so file:line references weren't checked")
        return []
    tree = subprocess.run(git + ["ls-tree", "-r", "--name-only", "--full-tree", rev],
                          capture_output=True, text=True).stdout.splitlines()
    files = set(tree)
    sizes, out = {}, []
    for path, line in sorted(set(REF.findall(text))):
        if path not in files:  # a shortened path ("course/service.go") stands for the one file it ends
            hits = [f for f in tree if f.endswith("/" + path)]
            if len(hits) > 1:
                continue  # ambiguous: can't tell which file it means
            if not hits:
                out.append(f"{path}:{line} (no such file on {branch})")
                continue
            path = hits[0]
        if path not in sizes:
            blob = subprocess.run(git + ["show", f"{rev}:{path}"], capture_output=True).stdout
            sizes[path] = len(blob.splitlines())
        if not 1 <= int(line) <= sizes[path]:
            out.append(f"{path}:{line} (the file has {sizes[path]} lines)")
    return out


def problems(html, goal):
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
    refs = bad_refs(goal, "\n".join(scan.text))
    if refs:
        out.append("it cites code that isn't there: " + ", ".join(refs[:8]) + (" …" if len(refs) > 8 else ""))
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
        bad = problems(html, goal)
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
