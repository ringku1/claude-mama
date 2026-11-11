#!/usr/bin/env python3
"""Full datetimes for log.md lines, which carry only HH:MM.

log.py writes a marker line `-- YYYY-MM-DD` before the first line of each new day (the plan's
`started:` date counts as the first day). A log line's date is the latest marker above it, or
the start date; logs from before markers existed fall back to a rollover rule: a time earlier
than the line before it means the next day. Markers carry no ID, so `^[EDFQ]\\d+` parsers skip them.

timeline(log_text, start)            -> [(datetime, kind, id, text)] for every E/D/F/Q line
stamp_dt(start_dt, hhmm, not_before) -> the first datetime at HH:MM not before not_before
start_of(plan_text)                  -> the plan's `started:` datetime, or None
"""
import datetime
import re

LINE = re.compile(r"^([EDFQ])(\d+) (\d\d):(\d\d) ?(.*)$")
MARKER = re.compile(r"^-- (\d{4}-\d\d-\d\d)\s*$")
STARTED = re.compile(r"^started: (\d{4}-\d\d-\d\d \d\d:\d\d)", re.M)
DAY = datetime.timedelta(days=1)


def marker(date):
    """The marker line for date (a date or datetime)."""
    return f"-- {date:%Y-%m-%d}"


def start_of(plan_text):
    m = STARTED.search(plan_text or "")
    return datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M") if m else None


def stamp_dt(start_dt, hhmm, not_before=None):
    """The first datetime at hhmm ("HH:MM" or a time) on or after not_before (default start_dt),
    counting from start_dt's day."""
    t = datetime.datetime.strptime(hhmm, "%H:%M").time() if isinstance(hhmm, str) else hhmm
    bound = max(start_dt, not_before) if not_before else start_dt
    dt = datetime.datetime.combine(bound.date(), t)
    return dt if dt >= bound else dt + DAY


def timeline(log_text, start=None):
    """[(datetime, kind, id, text)] in file order. start (the plan's `started:`, a datetime or
    None) dates the lines before the first marker; with neither, those lines are left out.
    After a marker its date holds; within a day a time going backwards rolls to the next day."""
    out, day, prev = [], (start.date() if start else None), start
    for raw in (log_text or "").splitlines():
        m = MARKER.match(raw.strip())
        if m:
            day = datetime.datetime.strptime(m.group(1), "%Y-%m-%d").date()
            prev = None
            continue
        m = LINE.match(raw.strip())
        if not m or day is None:
            continue
        kind, n, hh, mm, text = m.groups()
        try:
            t = datetime.time(int(hh), int(mm))
        except ValueError:
            continue
        base = datetime.datetime.combine(day, datetime.time())
        dt = stamp_dt(base, t, prev)
        out.append((dt, kind, int(n), text))
        day, prev = dt.date(), dt
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("Usage: clock.py <goal dir>   # print log.md with full datetimes")
    import os
    g = sys.argv[1]
    plan = os.path.join(g, "plan.md")
    start = start_of(open(plan, encoding="utf-8").read()) if os.path.exists(plan) else None
    for dt, kind, n, text in timeline(open(os.path.join(g, "log.md"), encoding="utf-8").read(), start):
        print(f"{dt:%Y-%m-%d %H:%M} {kind}{n} {text}")
