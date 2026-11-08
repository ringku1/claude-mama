#!/usr/bin/env python3
"""Update a mama plan.md safely and recompute the progress line.

Usage:
  plan-set.py <plan.md> S3 status=done end=11:42 "notes=★ D2"   # a Steps row
  plan-set.py <plan.md> C1 "evidence=go test ./... ok @11:40"     # a Criteria row
  plan-set.py <plan.md> --header status=waiting pr=none           # header fields
  plan-set.py <plan.md> --progress                                # only recompute

Row columns are matched by the table's header. Header fields are the `key: value`
pairs in the lines above the first section. Prints what changed and the progress line.
"""
import re
import sys

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
        vals[header.index(k)] = v
    lines[target] = render(vals)
    print(lines[target])


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
