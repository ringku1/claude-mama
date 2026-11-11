#!/usr/bin/env python3
"""Append one line to a mama log.md with the next ID and the real clock time.

Usage: log.py <log.md> <E|D|F|Q> "<text>"
  log.py log.md E "dispatch S1"
  log.py log.md D "decision | Q1 output | react-markdown | why: ... | tag: user"
  log.py log.md F "finding | <claim> | <file:line> | verified"
Prints the line written; a `wait` line identical to the last line is not written again. IDs and times are never typed by hand, so they can't drift.
"""
import datetime
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import activity  # noqa: E402
import fileio  # noqa: E402


def main():
    if len(sys.argv) != 4 or sys.argv[2] not in {"E", "D", "F", "Q"}:
        sys.exit(__doc__)
    path, kind, text = sys.argv[1], sys.argv[2], " ".join(sys.argv[3].split())
    with open(path, "a+", encoding="utf-8") as f, fileio.locked(f):
        f.seek(0)
        content = f.read()
        last = [l for l in content.splitlines() if l.strip()][-1:]
        if kind == "E" and text.startswith("wait") and last and re.sub(r"^E\d+ \d\d:\d\d ", "", last[0]) == text:
            print(last[0])  # still waiting on the same thing: one line is enough
            return
        ids = [int(n) for n in re.findall(rf"^{kind}(\d+) ", content, re.M)]
        line = f"{kind}{max(ids, default=0) + 1} {datetime.datetime.now():%H:%M} {text}"
        if content and not content.endswith("\n"):
            f.write("\n")
        f.write(line + "\n")
    activity.record(os.path.dirname(os.path.abspath(path)))
    print(line)


if __name__ == "__main__":
    main()
