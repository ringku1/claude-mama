#!/usr/bin/env python3
"""Keep overview.md in step with plan.md and log.md, and mark milestones.

An overview with the markers `<!-- mama:auto:start -->` … `<!-- mama:auto:end -->` has a
generated block: regenerate() rewrites only what is between them, from state:
  **Status:** <Word> · <n> of <m> parts done[ · detail]   (detail kept while the word stays)
  ## Done means       criteria, [x] with their evidence once it is recorded
  ## Timeline         the goal's start, the plan approval, and every `U` log line (last 12 rows)
  ## Where we are     n of m parts, what is being worked on, what is ready next
  ## Needs your input only while waiting: the last open question
Step titles stand in for step IDs; IDs and file:line refs are dropped from any text shown.
Everything outside the markers (title, Goal, Key decisions, Final report …) is hand-written.
An overview without the markers (goals from before them) gets only its Status line synced.
The overview's mtime is kept either way, so the hand-written prose still counts as unrefreshed.

A milestone (a step done/blocked/dropped, the goal's status or PR changed, scope added)
touches `<goal>/.milestone`; the Stop hook asks for the prose to be refreshed only when the
overview is older than the last milestone — not after every plan write.

Usage: overview.py <goal dir>   # regenerate the block (or sync the Status line) now
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clock  # noqa: E402
import fileio  # noqa: E402
import log  # noqa: E402
from estimate import FINISHED, expand, table  # noqa: E402

WORDS = {"planning": "Planning", "approved": "Approved", "running": "Working", "waiting": "Waiting for you",
         "paused": "Paused", "blocked": "Blocked", "done": "Done", "aborted": "Stopped"}
STATUS_RE = re.compile(r"^\*\*Status:\*\*.*$", re.M)
START, END = "<!-- mama:auto:start -->", "<!-- mama:auto:end -->"
MARK = ".milestone"
TIMELINE_ROWS = 12
WORKING = {"running", "testing", "fixing"}
SKIP = {"obsolete", "parked"}
ID = re.compile(r"(?<![\w./:#-])[SDCQFEUP]\d+[a-z]?(?![\w/:-]|\.\w)")
FILE_LINE = re.compile(r"\b[\w./-]*\.[A-Za-z]\w{0,3}:\d+\b")


def status_line(plan_text):
    head = plan_text.split("\n## ")[0]
    st = re.search(r"status: (\w+)", head)
    pr = re.search(r"progress: (\d+)/(\d+)", head)
    word = WORDS.get(st.group(1), st.group(1).capitalize()) if st else "Planning"
    if pr and int(pr.group(2)):
        return f"**Status:** {word} · {pr.group(1)} of {pr.group(2)} parts done"
    return f"**Status:** {word}"


def merged(old, new):
    """Keep the hand-written detail after the progress while the status word is unchanged."""
    m = re.match(r"\*\*Status:\*\* ([^·]+?) · [^·]+? · (.+)$", old)
    if m and new.startswith(f"**Status:** {m.group(1)} ·"):
        return f"{new} · {m.group(2)}"
    return new


def plain(text):
    """Text fit for the user: no step/log IDs, no file:line refs, no `@HH:MM` stamps."""
    text = FILE_LINE.sub("", text.replace("\\|", "|"))
    text = ID.sub("", re.sub(r"\s*@\s?\d\d:\d\d\b", "", text))
    text = re.sub(r"\(\s*[,;]?\s*\)", "", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", " ".join(text.split()))
    return text.strip(" ,;·-—")


def _rows(plan, section):
    hdr, rows = table(plan, section)
    return [dict(zip(hdr, r)) for r in rows]


def done_means(plan):
    out = []
    for c in _rows(plan, "Criteria"):
        crit = plain(c.get("criterion", ""))
        if not crit:
            continue
        ev = c.get("evidence", "").strip()
        ev = "" if ev in ("", "—", "-") else plain(ev)
        out.append(f"- [x] {crit} — {ev}" if ev else f"- [ ] {crit}")
    return out or ["- [ ] Set when the plan is ready"]


def timeline(plan, logtext):
    start = clock.start_of(plan)
    lines = log.timeline(logtext, start)
    rows = []
    first = next((e for e in lines if e[1] == "E" and e[3].startswith("start")), None)
    if first:
        rows.append((first[0], "Started"))
    elif start:
        rows.append((start, "Started"))
    approved = next((e for e in lines if e[1] == "E" and re.match(r"approved?\b", e[3])), None)
    if approved:
        rows.append((approved[0], "Plan approved"))
    rows += [(e[0], plain(e[3])) for e in lines if e[1] == "U" and plain(e[3])]
    rows.sort(key=lambda r: r[0])
    if len(rows) > TIMELINE_ROWS:
        rows = rows[:1] + rows[-(TIMELINE_ROWS - 1):]  # the start, then the latest
    days = {dt.date() for dt, _ in rows}
    fmt = "%H:%M" if len(days) <= 1 else "%b %d %H:%M"
    out = ["| When | What |", "| ---- | ---- |"]
    out += [f"| {dt.strftime(fmt)} | {what.replace('|', '/')} |" for dt, what in rows]
    return out


def where(plan):
    allrows = _rows(plan, "Steps")
    steps = [s for s in allrows if s.get("status") not in SKIP and s.get("title")]
    done = {s["id"] for s in steps if s.get("status") in FINISHED}
    dropped = {s["id"] for s in allrows if s.get("status") == "obsolete"}
    title = lambda s: plain(s["title"]) or "a step"
    out = []
    if steps:
        out.append(f"{len(done)} of {len(steps)} parts done.")
    working = [title(s) for s in steps if s.get("status") in WORKING]
    if working:
        out.append("Working on: " + ", ".join(working[:5]) + ".")
    blocked = [title(s) for s in steps if s.get("status") == "blocked"]
    if blocked:
        out.append("Blocked: " + ", ".join(blocked[:5]) + ".")
    ready = [title(s) for s in steps if s.get("status") == "todo"
             and all(d in done | dropped for d in expand(s.get("deps", "")))]
    if ready:
        out.append("Next: " + ", ".join(ready[:5]) + ".")
    return [" ".join(out) or "Planning: research and questions come first."]


def open_question(logtext):
    """The text of the last question no decision refers to, or None."""
    qs = list(re.finditer(r"^Q(\d+) \d\d:\d\d (.*)$", logtext, re.M))
    for m in reversed(qs):
        n, text = m.groups()
        if re.search(rf"^D\d+ .*\bQ{n}\b", logtext[m.end():], re.M):
            continue  # a later decision answers it
        parts = [p.strip() for p in re.split(r"(?<!\\)\|", text)]
        q = parts[1] if len(parts) > 1 and parts[0].lower() == "question" else parts[0]
        return plain(q) or None
    return None


def block(plan, logtext, old_status):
    out = [merged(old_status, status_line(plan)) if old_status else status_line(plan), "",
           "## Done means", "", *done_means(plan), "",
           "## Timeline", "", *timeline(plan, logtext), "",
           "## Where we are", "", *where(plan)]
    st = re.search(r"status: (\w+)", plan.split("\n## ")[0])
    q = open_question(logtext) if st and st.group(1) == "waiting" else None
    if q:
        out += ["", "## Needs your input", "", f"- {q}"]
    return "\n".join(out)


def _write_keep_mtime(path, text):
    st = os.stat(path)
    fileio.write_atomic(path, text)
    os.utime(path, (st.st_atime, st.st_mtime))


def regenerate(goal):
    """Rewrite the generated block between the markers; without markers, sync the Status line."""
    ov = os.path.join(goal, "overview.md")
    try:
        text = open(ov, encoding="utf-8").read()
        plan = open(os.path.join(goal, "plan.md"), encoding="utf-8").read()
    except OSError:
        return
    a, b = text.find(START), text.find(END)
    if a < 0 or b < a:
        return _sync_status(ov, text, plan)
    try:
        logtext = open(os.path.join(goal, "log.md"), encoding="utf-8").read()
    except OSError:
        logtext = ""
    m = STATUS_RE.search(text[a + len(START):b])
    new = text[:a] + START + "\n" + block(plan, logtext, m.group(0) if m else "") + "\n" + text[b:]
    if new != text:
        _write_keep_mtime(ov, new)


def _sync_status(ov, text, plan):
    m = STATUS_RE.search(text)
    if not m:
        return  # close-check reports a missing Status line
    line = merged(m.group(0), status_line(plan))
    if line != m.group(0):
        _write_keep_mtime(ov, text[:m.start()] + line + text[m.end():])


def sync(goal):
    """After a plan write: regenerate the block when the overview has one, else sync the Status line."""
    regenerate(goal)


def milestone(goal):
    p = os.path.join(goal, MARK)
    with open(p, "a"):
        pass
    os.utime(p)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    regenerate(os.path.abspath(sys.argv[1]))
