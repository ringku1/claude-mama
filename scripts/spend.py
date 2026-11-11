#!/usr/bin/env python3
"""Measure a goal's token spend from the session transcripts — no guessing.

Usage: spend.py [<transcript.jsonl>] <plan.md> [--write]   (transcript found automatically if omitted)
Counts, between the goal's `started:` time and its last log line (or now, if open):
  main thread + every subagent of this session: input + cache-creation + output tokens per
  API message (cache reads excluded: they re-read context already paid for).
Prints `spend=<n>k pct=<p>` (pct of the size ceiling S 300k / M 1M / L <n>); --write puts
`~<n>k` into the plan header's budget field.
"""
import datetime, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import activity  # noqa: E402
import fileio  # noqa: E402

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
    one this session last wrote to (reads don't switch it); timeline collects (time, current slug) for subagents."""
    seen, total, current = set(), 0, None
    for t, line, u in messages(path):
        if slug is not None:
            hits = written_slugs(line) if '"tool_use"' in line else []
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


GOAL_DIR = re.compile(r"\.claude/mama/([a-z0-9][a-z0-9-]*)(?![\w.-])")
# a shell command that changes files: the skill's writers, redirects, tee, in-place edits, python writes
WRITE_HINT = re.compile(r"(?:log|plan-set|new-goal)\.py|(?<![\d&])>>?(?!&)\s*(?!/dev/null)[\w\"'$/]|\btee\b|sed -i|\.write\(")
# working on the skill itself (cd into its folder) is not running a goal, even when it tests on one
SKILL_DEV = re.compile(r"cd\s+\S*\.claude/skills/mama\b")
NEW_GOAL = re.compile(r"new-goal\.py\S*\s+\S*(?:mama/?|\$\w+)\"?\s+([a-z0-9][a-z0-9-]*)")


def written_slugs(path_or_data):
    """Goals this session wrote to (tool calls that create or change their files), in order.
    Reading a goal's files doesn't count — only the session running a goal writes them.
    Shell writes count when the command names the goal folder (literal, in a variable, or cd)."""
    data = path_or_data
    if "\n" not in data and os.path.isfile(data):
        try:
            data = open(data, encoding="utf-8", errors="ignore").read()
        except OSError:
            return []
    out = []
    for line in data.splitlines():
        if '"tool_use"' not in line or ".claude/mama/" not in line and "new-goal" not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        for b in r.get("message", {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            inp = b.get("input", {})
            if b.get("name") in ("Write", "Edit"):
                out += SLUG_RE.findall(inp.get("file_path", ""))
            elif b.get("name") == "Bash":
                cmd = inp.get("command", "")
                if WRITE_HINT.search(cmd) and not SKILL_DEV.search(cmd):
                    out += GOAL_DIR.findall(cmd)
                out += NEW_GOAL.findall(cmd)
    return list(dict.fromkeys(out))


def transcript_of(sid):
    hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{sid}.jsonl"))
    return hits[0] if hits else None


def find_transcripts(plan):
    """Every session transcript that wrote to this goal (a resumed goal spans several):
    the recorded sessions (activity.log); for goals from before it, read the transcripts."""
    recorded = [t for t in map(transcript_of, activity.sessions_for(os.path.dirname(os.path.abspath(plan)))) if t]
    lo, _, _ = window(plan)
    if recorded and activity.entries()[0][0] <= lo:
        return recorded  # the record covers this goal's whole life
    slug = os.path.basename(os.path.dirname(os.path.abspath(plan)))
    found = []
    for p in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
        if datetime.datetime.fromtimestamp(os.path.getmtime(p)) < lo:
            continue
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                data = f.read()
        except OSError:
            continue
        if slug in data and slug in written_slugs(data):
            found.append(p)
    return list(dict.fromkeys(recorded + found))


def find_transcript(plan):
    t = find_transcripts(plan)
    return t[0] if t else None


def ran_mama(data):
    """True if the user typed /mama in this session (not just text mentioning it)."""
    for line in data.splitlines():
        if "command-name>/mama<" not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "user":
            continue
        c = r.get("message", {}).get("content")
        texts = [c] if isinstance(c, str) else [b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text"]
        if any("<command-name>/mama</command-name>" in t for t in texts):
            return True
    return False


def measure(plan, transcript=None):
    """Tokens this goal spent (main thread + its subagents) over every session that wrote to
    it, or None if none found. A given transcript only counts if it wrote to the goal."""
    slug = os.path.basename(os.path.dirname(os.path.abspath(plan)))
    found = find_transcripts(plan)
    if transcript and transcript not in found:
        return None if not found else sum(measure_one(plan, t) for t in found)
    if not found:
        return None
    return sum(measure_one(plan, t) for t in found)


def usage_where(path, lo, hi, keep):
    seen, total = set(), 0
    for t, _, u in messages(path):
        if not u or not u[0] or not t or not (lo <= t <= hi) or u[1] in seen or not keep(t):
            continue
        seen.add(u[1])
        total += cost(u[0])
    return total


def measure_one(plan, transcript):
    lo, hi, _ = window(plan)
    goal = os.path.dirname(os.path.abspath(plan))
    slug = os.path.basename(goal)
    acts = activity.timeline(os.path.splitext(os.path.basename(transcript))[0])
    timeline = []
    usage_in(transcript, lo, hi, slug, timeline)  # read from the transcript: used before the first record

    def owns(t):
        if acts and t >= acts[0][0]:
            return activity.goal_at(acts, t) == goal
        return slug_at(timeline, t) == slug
    total = usage_where(transcript, lo, hi, owns)
    sub_dir = os.path.join(os.path.splitext(transcript)[0], "subagents")
    for p in glob.glob(os.path.join(sub_dir, "*.jsonl")):
        if datetime.datetime.fromtimestamp(os.path.getmtime(p)) < lo:
            continue
        first = next((t for t, _, _ in messages(p) if t), None)
        if first and lo <= first <= hi and owns(first):
            total += usage_in(p, lo, hi)
    return total


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = [a for a in sys.argv[1:] if a != "--write"]
    transcript, plan = (args[0], args[1]) if len(args) > 1 else (None, args[0])
    _, _, size = window(plan)
    total = measure(plan, transcript)
    if total is None:
        sys.exit("no transcript found for this goal")
    k = round(total / 1000)
    c = ceiling(size)
    pct = round(100 * total / c) if c else -1
    print(f"spend={k}k pct={pct}" + ("" if c else "  (size has no ceiling: write L as e.g. 'L 1.5M')"))
    if "--write" in sys.argv:
        text = open(plan, encoding="utf-8").read()
        text = re.sub(r"(budget: )[^/|\n]*(/)", rf"\g<1>~{k}k \g<2>", text, count=1)
        fileio.write_atomic(plan, text)


if __name__ == "__main__":
    main()
