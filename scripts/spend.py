#!/usr/bin/env python3
"""Measure a goal's token spend from the session transcripts — no guessing.

Usage: spend.py <transcript.jsonl> <plan.md> [--write]
Counts, between the goal's `started:` time and its last log line (or now, if open):
  main thread + every subagent of this session: input + cache-creation + output tokens per
  API message (cache reads excluded: they re-read context already paid for).
Prints `spend=<n>k pct=<p>` (pct of the size ceiling S 300k / M 1M / L <n>); --write puts
`~<n>k` into the plan header's budget field.
"""
import datetime, glob, json, os, re, sys

CEIL = {"S": 300_000, "M": 1_000_000}


def parse_ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)


SLUG_RE = re.compile(r"\.claude/mama/([a-z0-9][a-z0-9-]*)/(?:plan|log|overview)\.md")


def messages(path):
    """Yield (time, line, usage-or-None, message id) for every transcript line."""
    try:
        f = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        return
    for line in f:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t = parse_ts(r["timestamp"]) if r.get("timestamp") else None
        u = None
        if r.get("type") == "assistant":
            m = r.get("message", {})
            u = (m.get("usage"), m.get("id") or r.get("uuid"))
        yield t, line, u


def cost(u):
    return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0)


def usage_in(path, lo, hi, slug=None, timeline=None):
    """Sum usage in [lo, hi]. With slug: in the main transcript, only while that goal is the
    one this session last touched; timeline collects (time, current slug) for subagents."""
    seen, total, current = set(), 0, None
    for t, line, u in messages(path):
        if slug is not None:
            hits = SLUG_RE.findall(line)
            if hits:
                current = hits[-1]
            if t and timeline is not None:
                timeline.append((t, current))
        if not u or not u[0] or not t or not (lo <= t <= hi) or u[1] in seen:
            continue
        if slug is not None and current != slug:
            continue
        seen.add(u[1])
        total += cost(u[0])
    return total


def slug_at(timeline, t):
    cur = None
    for ts, s in timeline:
        if ts > t:
            break
        cur = s
    return cur


def window(plan_path):
    head = open(plan_path, encoding="utf-8").read(3000)
    started = re.search(r"started: (\d{4}-\d\d-\d\d \d\d:\d\d)", head)
    status = re.search(r"status: (\w+)", head)
    budget = re.search(r"budget: ([^|\n]*)", head)
    lo = datetime.datetime.strptime(started.group(1), "%Y-%m-%d %H:%M")
    hi = datetime.datetime.now()
    if status and status.group(1) in ("done", "aborted"):
        log = os.path.join(os.path.dirname(plan_path), "log.md")
        times = re.findall(r"^[EDFQ]\d+ (\d\d:\d\d) ", open(log, encoding="utf-8").read(), re.M)
        if times:
            hh, mm = map(int, times[-1].split(":"))
            hi = lo.replace(hour=hh, minute=mm) + datetime.timedelta(minutes=1)
            if hi < lo:
                hi += datetime.timedelta(days=1)
    size = budget.group(1).split("/")[-1].strip() if budget else "?"
    return lo, hi, size


def ceiling(size):
    if size[:1] in CEIL:
        return CEIL[size[:1]]
    m = re.search(r"([\d.]+)\s*([kM])", size)
    if m:
        return int(float(m.group(1)) * (1_000_000 if m.group(2) == "M" else 1_000))
    return None


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    transcript, plan = sys.argv[1], sys.argv[2]
    lo, hi, size = window(plan)
    slug = os.path.basename(os.path.dirname(os.path.abspath(plan)))
    timeline = []
    total = usage_in(transcript, lo, hi, slug, timeline)
    sub_dir = os.path.join(os.path.splitext(transcript)[0], "subagents")
    for p in glob.glob(os.path.join(sub_dir, "*.jsonl")):
        if datetime.datetime.fromtimestamp(os.path.getmtime(p)) < lo:
            continue
        first = next((t for t, _, _ in messages(p) if t), None)
        if first and lo <= first <= hi and slug_at(timeline, first) == slug:
            total += usage_in(p, lo, hi)
    k = round(total / 1000)
    c = ceiling(size)
    pct = round(100 * total / c) if c else -1
    print(f"spend={k}k pct={pct}" + ("" if c else "  (size has no ceiling: write L as e.g. 'L 1.5M')"))
    if "--write" in sys.argv:
        text = open(plan, encoding="utf-8").read()
        text = re.sub(r"(budget: )[^/|\n]*(/)", rf"\g<1>~{k}k \g<2>", text, count=1)
        open(plan, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main()
