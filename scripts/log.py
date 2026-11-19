#!/usr/bin/env python3
"""Append one line to a mama log.md with the next ID and the real clock time.

Usage: log.py [--no-record] <log.md> <E|D|F|Q|U> "<text>"
  log.py log.md E "dispatch S1"
  log.py log.md D "decision | Q1 output | react-markdown | why: ... | tag: user"
  log.py log.md F "finding | <claim> | <file:line> | verified"
  log.py log.md U "Filter API done and tested"    # a user-facing Timeline row in overview.md
Prints the line written; a `wait` line identical to the last line is not written again. IDs and times are never typed by hand, so they can't drift.
Lines carry only HH:MM: when the date differs from the log's last date (or the plan's `started:`
date, for the first line), a marker `-- YYYY-MM-DD` is written first (see clock.py).
--no-record: don't record this write in activity.log (hooks logging an event, e.g. a compaction,
must not make the goal this session's).
"""
import datetime
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import activity  # noqa: E402
import clock  # noqa: E402
import fileio  # noqa: E402

KINDS = {"E", "D", "F", "Q", "U"}
ANY = r"^[EDFQU]\d+ "  # any ID'd line


def write(path, kind, text, record=True, now=None):
    """Append a `<kind><n> HH:MM text` line (plus a date marker when the day changed) and return
    it. record=False leaves activity.log alone, so the write never claims the goal for a session."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    text = " ".join(text.split())
    now = now or datetime.datetime.now()
    with open(path, "a+", encoding="utf-8") as f, fileio.locked(f):
        f.seek(0)
        content = f.read()
        last = [l for l in content.splitlines() if re.match(ANY, l)][-1:]
        if kind == "E" and text.startswith("wait") and last and re.sub(r"^E\d+ \d\d:\d\d ", "", last[0]) == text:
            return last[0]  # still waiting on the same thing: one line is enough
        ids = [int(n) for n in re.findall(rf"^{kind}(\d+) ", content, re.M)]
        line = f"{kind}{max(ids, default=0) + 1} {now:%H:%M} {text}"
        out = []
        if content and not content.endswith("\n"):
            out.append("")
        if last_date(path, content) != now.date():
            out.append(clock.marker(now))
        out.append(line)
        f.write("\n".join(out) + "\n")
    if record:
        activity.record(os.path.dirname(os.path.abspath(path)))
    return line


def last_date(path, content):
    """The date of the log's last line (markers, then rollover), or the plan's start date for an
    empty log; None when neither is known."""
    plan = os.path.join(os.path.dirname(os.path.abspath(path)), "plan.md")
    try:
        with open(plan, encoding="utf-8") as f:
            start = clock.start_of(f.read())
    except OSError:
        start = None
    tl = timeline(content, start)
    if tl:
        return tl[-1][0].date()
    if re.search(ANY, content, re.M):
        return None  # lines with no date to anchor them: mark today
    dates = re.findall(r"^-- (\d{4}-\d\d-\d\d)", content, re.M)
    if dates:
        return datetime.datetime.strptime(dates[-1], "%Y-%m-%d").date()
    return start.date() if start else None


def timeline(content, start=None):
    """clock.timeline with U lines too: [(datetime, kind, id, text)] in file order. clock knows
    E/D/F/Q only, so each U line passes through it as an E line tagged in its text."""
    tag = "\x00U "
    tl = clock.timeline(re.sub(r"^U(\d+) (\d\d:\d\d) ?", lambda m: f"E{m.group(1)} {m.group(2)} {tag}",
                               content or "", flags=re.M), start)
    return [(dt, "U", n, text[len(tag):]) if text.startswith(tag) else (dt, kind, n, text)
            for dt, kind, n, text in tl]


def main():
    args = sys.argv[1:]
    record = "--no-record" not in args
    args = [a for a in args if a != "--no-record"]
    if len(args) != 3 or args[1] not in KINDS:
        sys.exit(__doc__)
    print(write(args[0], args[1], args[2], record=record))


if __name__ == "__main__":
    main()
