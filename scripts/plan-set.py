#!/usr/bin/env python3
"""Update a mama plan.md safely and recompute the progress line.

Usage:
  plan-set.py <plan.md> S3 status=done end=now "notes=★ D2"     # a Steps row (now = real HH:MM)
  plan-set.py <plan.md> C1 "evidence=go test ./... ok @11:40"     # a Criteria row
  plan-set.py <plan.md> --header status=waiting pr=none           # header fields
  plan-set.py <plan.md> --progress                                # only recompute

Row columns are matched by the table's header. Header fields are the `key: value`
pairs in the lines above the first section. Prints what changed and the progress line.

Guards (they enforce the skill's rules, so state can't drift):
- a step set to running/testing/fixing gets start=now if empty; done/obsolete gets end=now if empty
- a step set to running whose deps aren't done prints a WARNING
- header status approved/running needs mode checkpointed|autonomous|quick (ask the user)
- header status done runs close-check.py and is refused until it prints OK
- first switch to running with a linked Trello card and no `trello` log line prints a REMINDER
"""
import datetime
import os
import re
import subprocess
import sys

NOW = lambda: datetime.datetime.now().strftime("%H:%M")
MODES = {"checkpointed", "autonomous", "quick"}

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


def set_row(lines, section, row_id, updates):
    header, rows = table(lines, section)
    target = next((r for r in rows if cells(lines[r])[0] == row_id), None)
    if target is None:
        sys.exit(f"{row_id} not found in {section}")
    vals = cells(lines[target]) + [""] * len(header)
    vals = vals[: len(header)]
    for k, v in updates.items():
        if k not in header:
            sys.exit(f"unknown column {k!r}; columns: {', '.join(header)}")
        vals[header.index(k)] = NOW() if v == "now" else v
    if "status" in header and "status" in updates:
        st, col = updates["status"], {h: i for i, h in enumerate(header)}
        if st in ("running", "testing", "fixing") and "start" in col and not vals[col["start"]]:
            vals[col["start"]] = NOW()
        if st in ("done", "obsolete") and "end" in col and not vals[col["end"]]:
            vals[col["end"]] = NOW()
        if st == "running" and "deps" in col:
            done = {cells(lines[r])[0] for r in rows if cells(lines[r])[col["status"]] in ("done", "obsolete")}
            open_deps = [d for d in expand(vals[col["deps"]]) if d not in done]
            if open_deps:
                print(f"WARNING: {row_id} started before its deps are done: {', '.join(open_deps)}")
    if "start" in header and "end" in header:
        a, b = vals[header.index("start")], vals[header.index("end")]
        if re.fullmatch(r"\d\d:\d\d", a or "") and re.fullmatch(r"\d\d:\d\d", b or "") and b < a \
                and not (a > "20:00" and b < "04:00"):
            sys.exit(f"REFUSED: {row_id} end {b} is before start {a}")
    lines[target] = render(vals)
    print(lines[target])


def expand(deps):
    """'S1-S4, S6a' -> ['S1','S2','S3','S4','S6a']"""
    out = []
    for part in re.split(r"[,\s]+", deps):
        m = re.fullmatch(r"S(\d+)-S?(\d+)", part)
        if m:
            out += [f"S{n}" for n in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif re.fullmatch(r"S\d+\w*", part):
            out.append(part)
    return out


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
    b = updates.get("budget", "")
    cur = header_value(lines, "budget")
    if b and "/" in b and "/" in cur:
        # the spend part is measured by the Stop hook — keep it; only the size is yours to set
        updates["budget"] = cur.split("/")[0].strip() + " / " + b.split("/", 1)[1].strip()
    if re.search(r"/\s*L\s*$", b):
        sys.exit("REFUSED: size L needs a number, e.g. budget='~0k / L 1.5M'")
    if st == "done":
        check = os.path.join(os.path.dirname(os.path.abspath(__file__)), "close-check.py")
        r = subprocess.run([sys.executable, check, os.path.dirname(os.path.abspath(path))],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("REFUSED: goal can't close yet.\n" + r.stdout)
    if st == "running" and header_value(lines, "status") != "running":
        trello = header_value(lines, "trello")
        logp = os.path.join(os.path.dirname(os.path.abspath(path)), "log.md")
        log = open(logp, encoding="utf-8").read() if os.path.exists(logp) else ""
        if trello not in ("", "none", "—") and not re.search(r"^E\d+ \d\d:\d\d trello", log, re.M):
            print("REMINDER: Trello card linked — post the start comment now (what this goal will change), log `trello`.")


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
    lines = open(path, encoding="utf-8").read().split("\n")
    updates = parse_updates(sys.argv[3:])
    if what == "--header":
        guard_header(path, lines, updates)
        set_header(lines, updates)
    elif what.startswith("C"):
        set_row(lines, "## Criteria", what, updates)
    elif what.startswith("S"):
        set_row(lines, "## Steps", what, updates)
    elif what != "--progress":
        sys.exit(f"unknown target {what!r}")
    progress(lines)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
