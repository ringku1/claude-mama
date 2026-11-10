#!/usr/bin/env python3
"""Check a mama goal is ready to close, and draft its lessons metrics line.

Usage: close-check.py <store>/<slug>
Prints each missing item, then a prefilled metrics line (fill the `?` fields from memory
of the run). Exit 0 = ready to set status done; exit 1 = something is missing.
"""
import datetime, os, re, sys

OPEN_STEP = {"todo", "running", "testing", "fixing", "blocked"}


def table(text, section):
    m = re.search(rf"^## {section}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return [], []
    rows = [[c.strip() for c in l.strip().strip("|").split("|")]
            for l in m.group(1).splitlines() if l.lstrip().startswith("|")]
    if len(rows) < 2:
        return [], []
    return rows[0], [r for r in rows[2:] if r and r[0]]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    goal = sys.argv[1].rstrip("/")
    slug, store = os.path.basename(goal), os.path.dirname(goal)
    plan = open(os.path.join(goal, "plan.md"), encoding="utf-8").read()
    log = open(os.path.join(goal, "log.md"), encoding="utf-8").read()
    head = dict(re.findall(r"(\w[\w ]*?): ([^|\n]*)", plan.split("## ")[0]))
    head = {k.strip(): v.strip() for k, v in head.items()}
    missing = []

    hdr, steps = table(plan, "Steps")
    si = {k: i for i, k in enumerate(hdr)}
    live = [s for s in steps if s[si["status"]] not in ("obsolete", "parked")]
    for s in live:
        if s[si["status"]] in OPEN_STEP:
            missing.append(f"step {s[0]} is still {s[si['status']]}")
        if s[si["status"]] == "done" and not (s[si["start"]] and s[si["end"]]):
            missing.append(f"step {s[0]} has no start/end time (plan-set.py ... start=now / end=now)")

    for s in live:
        a, b = s[si["start"]], s[si["end"]]
        if a and b and re.fullmatch(r"\d\d:\d\d", a) and re.fullmatch(r"\d\d:\d\d", b) and b < a \
                and not (a > "20:00" and b < "04:00"):
            missing.append(f"step {s[0]} ends ({b}) before it starts ({a})")

    for name, text in (("plan.md", plan.split("## ")[0]), ("log.md", log)):
        junk = re.findall(r"<[a-z][^<>\n]*\|[^<>\n]*>|<!--|HH:MM", text)
        if junk:
            missing.append(f"{name} still has template placeholders ({', '.join(sorted(set(junk))[:3])})")

    if re.search(r"budget: ~0k", plan) and re.search(r"^E\d+ \S+ (dispatch|wait)", log, re.M):
        missing.append("budget still ~0k though work ran — the Stop hook writes it; run scripts/spend.py <transcript> <plan> --write")

    chdr, crit = table(plan, "Criteria")
    ci = {k: i for i, k in enumerate(chdr)}
    for c in crit:
        if c[ci["evidence"]] in ("", "—", "-"):
            missing.append(f"criterion {c[0]} has no evidence (plan-set.py <plan> {c[0]} \"evidence=...\")")

    if head.get("trello", "none") not in ("none", "—", "") and not re.search(r"^E\d+ \d\d:\d\d trello", log, re.M):
        missing.append("Trello card linked but no `trello` log line")

    lessons_p = os.path.join(store, "lessons.md")
    lessons = open(lessons_p, encoding="utf-8").read() if os.path.exists(lessons_p) else ""
    if not re.search(rf"^- ?\d{{4}}-\d\d-\d\d {re.escape(slug)} \S+ \| steps ", lessons, re.M):
        missing.append(f"no metrics line for {slug} in lessons.md (draft below)")

    started = head.get("started", "")
    patterns_p = os.path.expanduser("~/.claude/mama/patterns.md")
    try:
        start_ts = datetime.datetime.strptime(started, "%Y-%m-%d %H:%M").timestamp()
        if os.path.getmtime(patterns_p) < start_ts:
            missing.append("patterns.md not updated during this goal (choices, size, real time/tokens)")
    except (ValueError, OSError):
        pass

    profile_p = os.path.join(store, "profile.md")
    try:
        start_ts = datetime.datetime.strptime(started, "%Y-%m-%d %H:%M").timestamp()
        if os.path.getmtime(profile_p) < start_ts and not re.search(r"^E\d+ \S+ profile\b", log, re.M):
            missing.append("profile.md not refreshed — update facts this goal changed, or log `E profile none`")
    except (ValueError, OSError):
        pass

    times = re.findall(r"^[EDFQ]\d+ (\d\d:\d\d) ", log, re.M)
    mins = "?"
    if times:
        a, b = (datetime.datetime.strptime(t, "%H:%M") for t in (times[0], times[-1]))
        mins = int((b - a).total_seconds() // 60) % (24 * 60)
    est = sum(int(m) for s in live for m in re.findall(r"(\d+)m", s[si["est"]]))
    att = sum(int(s[si["att"]] or 0) for s in live if s[si["att"]].isdigit())
    budget = head.get("budget", "?")
    size = budget.split("/")[-1].strip() if "/" in budget else "?"
    spent = budget.split("/")[0].strip().lstrip("~") if "/" in budget else "?"
    line = (f"- {datetime.date.today()} {slug} {head.get('type', '?')} | steps {len(live)} | "
            f"time est {est}m (sum of steps) / actual {mins}m | tokens est {size} / ~{spent} | "
            f"questions {len(re.findall(r'^Q', log, re.M))} (changed plan: ?) | fix rounds {att} | "
            f"checker findings ? | compactions {len(re.findall(r'^E\d+ \S+ compaction', log, re.M))} | "
            f"wrong assumptions ? | reversed decisions {len(re.findall(r'supersedes', log))}")

    for m in missing:
        print("MISSING:", m)
    print("METRICS:", line)
    print("OK — ready to close" if not missing else f"NOT READY — {len(missing)} missing")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
