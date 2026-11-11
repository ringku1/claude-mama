#!/usr/bin/env python3
"""Update a mama plan.md safely and recompute the progress line.

Usage:
  plan-set.py <plan.md> S3 status=done end=now "notes=★ D2"     # a Steps row (now = real HH:MM)
  plan-set.py <plan.md> C1 "evidence=go test ./... ok @11:40"     # a Criteria row
  plan-set.py <plan.md> --header status=waiting pr=none           # header fields
  plan-set.py <plan.md> --progress                                # only recompute
  plan-set.py <plan.md> S+ kind=build "title=…" deps=S2 "verify=…" est=15m   # add a step (next id)
  plan-set.py <plan.md> C+ "criterion=…" "proven by=S7"                       # add a criterion
  plan-set.py <plan.md> P+ "text=student side: no design yet"                 # park an out-of-scope idea

Row columns are matched by the table's header. Header fields are the `key: value`
pairs in the lines above the first section. Prints what changed and the progress line.

Guards (they enforce the skill's rules, so state can't drift):
- a step set to running/testing/fixing gets start=now if empty; done/obsolete gets end=now if empty
- a step set to running whose deps aren't done prints a WARNING
- header status approved/running needs mode checkpointed|autonomous|quick (ask the user); the first
  approval of a full goal also needs an `E research` log line (rules/research.md) and a budget ceiling
- budget is always `~<spent>k / <size>`, size S, M or `L <n>` (e.g. `L 1.5M`): the Stop hook measures
  the spend part and reads the ceiling from the size, so neither can be dropped
- pr is one of ask-at-end | auto | none | declined | <url>
- a hand-typed end earlier than start is refused (a step that crossed midnight: end=now)
- header status done runs close-check.py and is refused until it prints OK
- added rows get the next free id; a step needs title + verify, deps must exist; rows are never
  deleted (set status=obsolete with a reason in notes)
- first switch to running with a linked Trello card and no `trello` log line prints a REMINDER
- `now` stamps the real HH:MM in any row, added ones too; S+/C+ fill the template's blank row first
- the whole read → edit → write holds fileio.plan_lock (the Stop hook writes the budget under it too)

After every write it syncs overview.md's **Status:** line (scripts/overview.py) and, on a
milestone (step done/blocked/dropped, goal status or PR changed, scope added mid-run), marks
it so the Stop hook asks for the overview's prose to be refreshed. Prints the estimate
(critical path, sum, time left) after step changes.
"""
import datetime
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import activity  # noqa: E402
import fileio  # noqa: E402
import overview  # noqa: E402
from estimate import expand, summary  # noqa: E402

NOW = lambda: datetime.datetime.now().strftime("%H:%M")
MODES = {"checkpointed", "autonomous", "quick"}
PR_VALUES = ("ask-at-end", "auto", "none", "declined")
SIZE = re.compile(r"[SM]|L \d+(?:\.\d+)?[kM]")
SPENT = re.compile(r"~\d+(?:\.\d+)?k")

LIVE_EXCLUDED = {"obsolete", "parked"}


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(values):
    return "| " + " | ".join(values) + " |"


def parse_updates(args):
    out = {}
    for arg in args:
        if "=" not in arg:
            sys.exit(f"bad update {arg!r}, want key=value")
        k, v = arg.split("=", 1)
        out[k] = v.replace("|", "/")
    return out


def table(lines, section):
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == section)
    except StopIteration:
        sys.exit(f"no '{section}' section")
    header_i = next(i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("|"))
    rows, i = [], header_i + 2
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        rows.append(i)
        i += 1
    return cells(lines[header_i]), rows


def apply_updates(lines, rows, header, vals, row_id, updates):
    """Write updates into a row's values with the guards — the same for set and added rows."""
    col = {h: i for i, h in enumerate(header)}
    stamped = set()  # columns set to the real time in this call
    for k, v in updates.items():
        if k not in col:
            sys.exit(f"unknown column {k!r}; columns: {', '.join(header)}")
        vals[col[k]] = NOW() if v == "now" else v
        if v == "now":
            stamped.add(k)
    st = updates.get("status")
    if st and "status" in col:
        if st in ("running", "testing", "fixing") and "start" in col and not vals[col["start"]]:
            vals[col["start"]] = NOW()
            stamped.add("start")
        if st in ("done", "obsolete") and "end" in col and not vals[col["end"]]:
            vals[col["end"]] = NOW()
            stamped.add("end")
        if st == "running" and "deps" in col:
            done = {cells(lines[r])[0] for r in rows if cells(lines[r])[col["status"]] in ("done", "obsolete")}
            open_deps = [d for d in expand(vals[col["deps"]]) if d not in done]
            if open_deps:
                print(f"WARNING: {row_id} started before its deps are done: {', '.join(open_deps)}")
    if "start" in col and "end" in col and "end" not in stamped and ({"start", "end"} & (set(updates) | stamped)):
        # the real time (end=now) is always right — a step may run past midnight or over days;
        # only a hand-typed end can be earlier than its start by mistake
        a, b = vals[col["start"]], vals[col["end"]]
        if re.fullmatch(r"\d\d:\d\d", a or "") and re.fullmatch(r"\d\d:\d\d", b or "") and b < a:
            sys.exit(f"REFUSED: {row_id} end {b} is before start {a}. Never type times: set end=now "
                     "(a step that ran past midnight is fine with end=now).")


MILESTONE_STEP = {"done", "blocked", "obsolete", "parked"}


def set_row(lines, section, row_id, updates):
    """Returns True when the change is a milestone (a step finished, blocked or dropped)."""
    header, rows = table(lines, section)
    target = next((r for r in rows if cells(lines[r])[0] == row_id), None)
    if target is None:
        sys.exit(f"{row_id} not found in {section}")
    vals = (cells(lines[target]) + [""] * len(header))[: len(header)]
    before = vals[header.index("status")] if "status" in header else ""
    apply_updates(lines, rows, header, vals, row_id, updates)
    lines[target] = render(vals)
    print(lines[target])
    return "status" in header and updates.get("status") in MILESTONE_STEP and before != updates["status"]


def add_row(lines, section, prefix, updates):
    """Add a row with the next free id — or fill the template's empty row (the blank S1/C1 a
    new plan starts with) in place, so no placeholder is left behind."""
    header, rows = table(lines, section)
    need = ("title", "verify") if prefix == "S" else ("criterion", "proven by")
    key = need[0]
    blank = next((r for r in rows if key in header and not cells(lines[r])[header.index(key)]), None)
    if blank is not None:
        row_id = cells(lines[blank])[0]
    else:
        nums = [int(m.group(1)) for r in rows if (m := re.match(rf"{prefix}(\d+)", cells(lines[r])[0]))]
        row_id = f"{prefix}{max(nums, default=0) + 1}"
    vals = [""] * len(header)
    vals[0] = row_id
    for k, v in {"status": "todo", "att": "0", "deps": "—", "evidence": "—"}.items():
        if k in header:
            vals[header.index(k)] = v
    apply_updates(lines, rows, header, vals, row_id, updates)
    miss = [k for k in need if k in header and not vals[header.index(k)]]
    if miss:
        sys.exit(f"REFUSED: a new {prefix} row needs {', '.join(miss)}")
    if prefix == "S":
        ids = {cells(lines[r])[0] for r in rows if r != blank}
        bad = [d for d in expand(vals[header.index("deps")]) if d not in ids]
        if bad:
            sys.exit(f"REFUSED: unknown deps {', '.join(bad)}")
    if blank is not None:
        at = blank
        lines[at] = render(vals)
    else:
        at = rows[-1] + 1 if rows else next(i for i in range(len(lines)) if lines[i].lstrip().startswith("|---") or lines[i].lstrip().startswith("| ---")) + 1
        lines.insert(at, render(vals))
    print("ADDED", lines[at])


def park(lines, text):
    """Append a bullet to ## Parked (dropping the template's placeholder bullet)."""
    if not text.strip():
        sys.exit("REFUSED: P+ needs text=…")
    if not any(l.strip() == "## Parked" for l in lines):
        lines += ["", "## Parked", ""]
    start = next(i for i, l in enumerate(lines) if l.strip() == "## Parked")
    end = lambda: next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    for i in range(end() - 1, start, -1):
        if re.fullmatch(r"- <[^>]*>", lines[i].strip()):
            del lines[i]
    bullets = [i for i in range(start + 1, end()) if lines[i].startswith("- ")]
    at = bullets[-1] + 1 if bullets else start + 1
    if not bullets:
        lines.insert(at, "")
        at += 1
    lines.insert(at, f"- {text.strip()}")
    print("PARKED", lines[at])


def header_value(lines, key):
    for l in lines:
        if l.startswith("## "):
            break
        m = re.search(rf"(?:^|\| ){re.escape(key)}: ([^|]*)", l)
        if m:
            return m.group(1).strip()
    return ""


def guard_header(path, lines, updates):
    st = updates.get("status")
    mode = updates.get("mode", header_value(lines, "mode"))
    if st in ("approved", "running") and mode not in MODES:
        sys.exit("REFUSED: mode is not set. Ask the user with the approval question "
                 "(approve · checkpointed / approve · autonomous), then set mode=… with the status.")
    if "budget" in updates:
        updates["budget"] = budget_value(header_value(lines, "budget"), updates["budget"])
    pr = updates.get("pr")
    if pr is not None and pr not in PR_VALUES and not re.match(r"https?://\S+$", pr):
        sys.exit(f"REFUSED: pr={pr!r}; use one of {' | '.join(PR_VALUES)} | <PR url>")
    if st == "done":
        check = os.path.join(os.path.dirname(os.path.abspath(__file__)), "close-check.py")
        r = subprocess.run([sys.executable, check, os.path.dirname(os.path.abspath(path))],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("REFUSED: goal can't close yet.\n" + r.stdout)
    prev = header_value(lines, "status")
    logp = os.path.join(os.path.dirname(os.path.abspath(path)), "log.md")
    log = open(logp, encoding="utf-8").read() if os.path.exists(logp) else ""
    first_go = st in ("approved", "running") and prev in ("planning", "waiting") \
        and not re.search(r"^E\d+ \S+ resume", log, re.M)
    if first_go and mode != "quick" and not re.search(r"^E\d+ \S+ research", log, re.M):
        sys.exit("REFUSED: no research recorded. Run the research lenses (rules/research.md), then log "
                 "`E research: <n> findings, <m> cases, <k> open` — or `E research none: <why>` if this goal needs none.")
    budget = updates.get("budget", header_value(lines, "budget"))
    if first_go and mode != "quick" and not SIZE.fullmatch(budget.split("/")[-1].strip()):
        sys.exit("REFUSED: no budget ceiling. Set the size with the approval: budget=S, budget=M "
                 "or budget='L <n>' (e.g. 'L 1.5M').")
    logpy = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.py")
    if st == "waiting" and prev != "waiting" and os.path.exists(logp):
        subprocess.run([sys.executable, logpy, logp, "E", "waiting for the user"], stdout=subprocess.DEVNULL)
    if st == "running" and prev in ("waiting", "paused") and os.path.exists(logp):
        subprocess.run([sys.executable, logpy, logp, "E", "resume"], stdout=subprocess.DEVNULL)
    if st == "running" and prev != "running":
        trello = header_value(lines, "trello")
        logp = os.path.join(os.path.dirname(os.path.abspath(path)), "log.md")
        log = open(logp, encoding="utf-8").read() if os.path.exists(logp) else ""
        if trello not in ("", "none", "—") and not re.search(r"^E\d+ \d\d:\d\d trello", log, re.M):
            print("REMINDER: Trello card linked — post the start comment now (what this goal will change), log `trello`.")


def budget_value(cur, new):
    """`~<spent>k / <size>` from what was typed: the spend part is measured by the Stop hook, so the
    current one is kept (a typed one only when there is none yet); only the size is yours to set."""
    size = new.split("/", 1)[1].strip() if "/" in new else new.strip()
    if not SIZE.fullmatch(size):
        hint = " — L needs a number" if size.startswith("L") else ""
        sys.exit(f"REFUSED: budget size {size!r}{hint}; use S, M or 'L <n>', e.g. budget='L 1.5M'")
    m = SPENT.search(cur.split("/")[0]) if "/" in cur else None
    m = m or (SPENT.search(new.split("/")[0]) if "/" in new else None)
    return f"{m.group(0) if m else '~0k'} / {size}"


def set_header(lines, updates):
    end = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    for k, v in updates.items():
        pat = re.compile(rf"(^|\| ){re.escape(k)}: [^|]*?( \||$)")
        for i in range(end):
            if pat.search(lines[i]):
                lines[i] = pat.sub(lambda m: f"{m.group(1)}{k}: {v}{m.group(2)}", lines[i], count=1)
                print(lines[i])
                break
        else:
            sys.exit(f"header field {k!r} not found")


def progress(lines):
    header, rows = table(lines, "## Steps")
    si = header.index("status")
    live = [cells(lines[r])[si] for r in rows]
    live = [s for s in live if s not in LIVE_EXCLUDED]
    done = sum(s == "done" for s in live)
    blocked = sum(s == "blocked" for s in live)
    pct = round(100 * done / len(live)) if live else 0
    for j, l in enumerate(lines):
        if l.startswith("progress:"):
            rest = l.split("|", 2)[2] if l.count("|") >= 2 else " budget: —"
            lines[j] = f"progress: {done}/{len(live)} ({pct}%) | blocked: {blocked} |{rest}"
            print(lines[j])
            return


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    path, what = sys.argv[1], sys.argv[2]
    updates = parse_updates(sys.argv[3:])
    goal = os.path.dirname(os.path.abspath(path))
    with fileio.plan_lock(path):  # the Stop hook writes the measured budget under the same lock
        lines, milestone = edit(path, what, updates)
    activity.record(goal)
    if milestone:
        overview.milestone(goal)
    overview.sync(goal)
    est = summary("\n".join(lines))
    if est and what != "--header":
        print(est)


def edit(path, what, updates):
    """Read, change and write plan.md; returns (lines, milestone). Runs under plan_lock."""
    lines = open(path, encoding="utf-8").read().split("\n")
    milestone = False  # something the user would see changed: the overview's prose is due
    if what == "--header":
        before = {k: header_value(lines, k) for k in ("status", "pr")}
        guard_header(path, lines, updates)
        set_header(lines, updates)
        milestone = any(k in updates and updates[k] != v for k, v in before.items())
        if updates.get("status") == "done":
            milestone = False  # close-check already required the final report; the Status line syncs to Done
    elif what in ("S+", "C+"):
        add_row(lines, "## Steps" if what == "S+" else "## Criteria", what[0], updates)
        milestone = header_value(lines, "status") != "planning"  # scope changed mid-run
    elif what == "P+":
        park(lines, updates.get("text", ""))
    elif what.startswith("C"):
        set_row(lines, "## Criteria", what, updates)
    elif what.startswith("S"):
        milestone = set_row(lines, "## Steps", what, updates)
    elif what != "--progress":
        sys.exit(f"unknown target {what!r}")
    progress(lines)
    fileio.write_atomic(path, "\n".join(lines))
    return lines, milestone


if __name__ == "__main__":
    main()
