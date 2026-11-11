#!/usr/bin/env python3
"""Measure a goal's token spend from the session transcripts — no guessing.

Usage: spend.py [<transcript.jsonl>] <plan.md> [--write]   (the transcript only hints where transcripts live)
Counts, for every session that recorded writes to the goal (activity.log), the time that
session spent on it — from each switch to the goal until the session's next switch — within the
goal's life (`started:` to its last log line, or now if open): main thread + the subagents it
started then; input + cache-creation + output tokens per API message (cache reads excluded:
they re-read context already paid for). Time before activity.log existed is read from the
transcripts (written_slugs). A session that never wrote to the goal adds nothing.
Prints `spend=<n>k pct=<p>` (pct of the size ceiling S 300k / M 1M / L <n>); --write puts
`~<n>k` into the plan header's budget field.

One pass per transcript, cached in <goal>/.spend-cache.json (per file: size, offset read,
per-second sums), so later turns read only the bytes added since.
"""
import calendar, datetime, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import activity  # noqa: E402
import clock  # noqa: E402
import fileio  # noqa: E402

CEIL = {"S": 300_000, "M": 1_000_000}
CACHE = ".spend-cache.json"
CACHE_V = 1
INF = float("inf")

# paths may use / or \ (Windows tools write C:\Users\…\.claude\mama\<slug>\plan.md)
SLUG_RE = re.compile(r"\.claude[\\/]+mama[\\/]+([a-z0-9][a-z0-9-]*)[\\/]+(?:plan|log|overview)\.md")
GOAL_DIR = re.compile(r"\.claude[\\/]+mama[\\/]+([a-z0-9][a-z0-9-]*)(?![\w.-])")
# a shell command that changes files: the skill's writers, redirects, tee, in-place edits, python writes
WRITE_HINT = re.compile(r"(?:log|plan-set|new-goal)\.py|(?<![\d&])>>?(?!&)\s*(?!/dev/null)[\w\"'$/]|\btee\b|sed -i|\.write\(")
# working on the skill itself (cd into its folder) is not running a goal, even when it tests on one
SKILL_DEV = re.compile(r"cd\s+\S*\.claude[\\/]+skills[\\/]+mama\b")
# raw JSON lines escape \\ as \\\\, so the quick pre-check allows any run of separators
ANY_GOAL = re.compile(r"\.claude[\\/]+mama[\\/]+")
ANY_GOAL_B = re.compile(rb"\.claude[\\/]+mama[\\/]+")
NEW_GOAL = re.compile(r"new-goal\.py\S*\s+\S*(?:mama[\\/]?|\$\w+)\"?\s+([a-z0-9][a-z0-9-]*)")
MSG_ID = re.compile(rb'"id":"([^"]+)"')
TOKENS = re.compile(rb'"(input_tokens|cache_creation_input_tokens|output_tokens)":(\d+)')


def projects_dir():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join("~", ".claude")
    return os.path.join(os.path.expanduser(base), "projects")


def epoch(s):
    """Whole seconds since the epoch for a transcript timestamp ("2026-01-02T03:04:05.678Z"), or None."""
    try:
        if s.endswith("Z"):
            return calendar.timegm((int(s[0:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]), int(s[14:16]), int(s[17:19])))
        return int(datetime.datetime.fromisoformat(s).timestamp())
    except (ValueError, TypeError, IndexError, AttributeError):
        return None


def cost(u):
    return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0)


def _role(line):
    """The message role of a compact transcript line ("message":{"model",…,"role"} comes first),
    or None when it isn't near the start."""
    r = line.find(b'"role":"', 0, 1000)
    return None if r == -1 else line[r + 8:line.find(b'"', r + 8)]


def _top_message(line):
    """True when the line is compact JSON whose top-level "message" object opens within the
    first 1000 bytes and reaches its "role" before any nested object."""
    mp = line.find(b'"message":{', 0, 1000)
    r = line.find(b'"role":"', mp, 1000)
    return mp != -1 and r != -1 and line.find(b"{", 1, mp) == -1 and line.find(b"{", mp + 11, r) == -1


def _usage(line, seen, role):
    """(time, message id, tokens) for an assistant line with usage whose message id isn't in
    seen, else None. The fast path reads those fields straight from compact JSON (the
    message's "id" comes before its content; its "usage", then the line's "type" and
    "timestamp", after it); anything else is parsed whole."""
    i = line.rfind(b'"usage":')
    if i == -1:
        return None
    t = line.rfind(b'"timestamp":"')
    m = MSG_ID.search(line)
    if role == b"assistant" and line.startswith(b"{", i + 8) and t > i and m and _top_message(line) \
            and line.find(b'"type":"assistant"', i) != -1:
        mid = m.group(1).decode("ascii", "ignore")
        if mid in seen:
            return None
        u = {}
        for k, v in TOKENS.findall(line, i):
            u.setdefault(k.decode(), int(v))
        ts = epoch(line[t + 13:line.find(b'"', t + 13)].decode("ascii", "ignore"))
        if ts is not None:
            return ts, mid, cost(u)
    try:
        rec = json.loads(line)
    except ValueError:
        return None
    if not isinstance(rec, dict) or rec.get("type") != "assistant":
        return None
    msg = rec.get("message") or {}
    u, ts, mid = msg.get("usage"), epoch(rec.get("timestamp")), msg.get("id") or rec.get("uuid")
    if not isinstance(u, dict) or ts is None or mid in seen:
        return None
    return ts, mid, cost(u)


def _ts(line):
    if b'"timestamp"' not in line:
        return None
    try:
        return epoch(json.loads(line).get("timestamp"))
    except (ValueError, AttributeError):
        return None


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
        if '"tool_use"' in line and (ANY_GOAL.search(line) or "new-goal" in line):
            out += _line_slugs(line)
    return list(dict.fromkeys(out))


def _line_slugs(line):
    try:
        r = json.loads(line)
    except ValueError:
        return []
    out = []
    blocks = (r.get("message") or {}).get("content") if isinstance(r, dict) else None
    for b in blocks if isinstance(blocks, list) else []:
        if not isinstance(b, dict) or b.get("type") != "tool_use":
            continue
        inp = b.get("input") or {}
        if b.get("name") in ("Write", "Edit"):
            out += SLUG_RE.findall(inp.get("file_path", ""))
        elif b.get("name") == "Bash":
            cmd = inp.get("command", "")
            if WRITE_HINT.search(cmd) and not SKILL_DEV.search(cmd):
                out += GOAL_DIR.findall(cmd)
            out += NEW_GOAL.findall(cmd)
    return list(dict.fromkeys(out))


def scan(path, entry, since):
    """One transcript's cache entry brought up to date, reading only the bytes past entry["off"].
    Entry: {size, off, first/last (times), ids (message ids counted), use {sec: tokens},
    writes [[sec, slug]]}. Per-second sums before `since` are dropped (the goal didn't exist)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if entry.get("off", 0) > size:
        entry = {}  # rewritten, not grown
    if entry and entry.get("size") == size:
        return entry
    off, first, last = entry.get("off", 0), entry.get("first"), entry.get("last")
    use, writes, ids = dict(entry.get("use", {})), list(entry.get("writes", [])), list(entry.get("ids", []))
    seen = set(ids)
    try:
        f = open(path, "rb")
    except OSError:
        return None
    with f:
        f.seek(off)
        for line in f:
            if not line.endswith(b"\n"):
                break  # still being written: read it next time
            off += len(line)
            if first is None:
                first = _ts(line)
            # only assistant lines carry usage and tool calls; the rest (prompts, tool results,
            # attachments, snapshots — most of the bytes) are skipped on their first 1000 bytes
            role = _role(line)
            if role != b"assistant" and (role is not None or line.find(b'"assistant"', 0, 1000) == -1):
                continue
            hit = _usage(line, seen, role)
            if hit:
                last, mid, c = hit
                seen.add(mid)
                ids.append(mid)
                if c and last >= since:
                    k = str(last)
                    use[k] = use.get(k, 0) + c
            # a write to a goal names its folder (.claude/mama/<slug>) or new-goal.py, both under mama
            if b"mama" in line and b'"tool_use"' in line and (b"new-goal" in line or ANY_GOAL_B.search(line)):
                s = _line_slugs(line.decode("utf-8", "ignore"))
                if s:
                    ts = _ts(line)
                    writes.append([last if ts is None else ts, s[-1]])
    return {"size": size, "off": off, "first": first, "last": last, "ids": ids, "use": use, "writes": writes}


def windows_of(goal, sid, writes, lo, hi, birth):
    """Epoch intervals [(a, b)] in which session sid worked on goal: from each recorded switch
    to the goal until its next switch; before activity.log existed (birth), from its transcript
    writes to the goal until its next write elsewhere."""
    out = []
    tl = [(t.timestamp(), g) for t, g in activity.timeline(sid)]
    for i, (t, g) in enumerate(tl):
        if g == goal:
            out.append((max(t, lo), min(tl[i + 1][0] if i + 1 < len(tl) else INF, hi)))
    if lo < birth:
        slug = os.path.basename(goal)
        ev = sorted((t, s) for t, s in writes if t is not None)
        for i, (t, s) in enumerate(ev):
            if s == slug:
                out.append((max(t, lo), min(ev[i + 1][0] if i + 1 < len(ev) else INF, hi, birth)))
    return [(a, b) for a, b in out if a <= b]


def inside(t, wins):
    return any(a <= t <= b for a, b in wins)


def window(plan_path):
    """(start, end, size): start from `started:`; end one minute after the last log line when
    done/aborted (dated across days by clock.timeline), else now."""
    text = open(plan_path, encoding="utf-8").read()
    head = text[:3000]
    status = re.search(r"status: (\w+)", head)
    budget = re.search(r"budget: ([^|\n]*)", head)
    now = datetime.datetime.now()
    lo = clock.start_of(head) or now
    hi = now
    if status and status.group(1) in ("done", "aborted"):
        try:
            log = open(os.path.join(os.path.dirname(plan_path), "log.md"), encoding="utf-8").read()
        except OSError:
            log = ""
        tl = clock.timeline(log, lo)
        if tl:
            hi = max(tl[-1][0] + datetime.timedelta(minutes=1), lo)
    size = budget.group(1).split("/")[-1].strip() if budget else "?"
    return lo, hi, size


def ceiling(size):
    if size[:1] in CEIL:
        return CEIL[size[:1]]
    m = re.search(r"([\d.]+)\s*([kM])", size)
    if m:
        return int(float(m.group(1)) * (1_000_000 if m.group(2) == "M" else 1_000))
    return None


def transcript_of(sid, hint=None):
    if hint:
        p = os.path.join(os.path.dirname(os.path.abspath(hint)), f"{sid}.jsonl")
        if os.path.isfile(p):
            return p
    hits = glob.glob(os.path.join(glob.escape(projects_dir()), "*", f"{sid}.jsonl"))
    return hits[0] if hits else None


def _load(goal, lo):
    try:
        with open(os.path.join(goal, CACHE), encoding="utf-8") as f:
            c = json.load(f)
        if c.get("v") == CACHE_V and c.get("lo") == lo and isinstance(c.get("files"), dict):
            return c
    except (OSError, ValueError, AttributeError):
        pass
    return {"v": CACHE_V, "lo": lo, "files": {}}


def measure(plan, transcript=None):
    """Tokens this goal spent (main threads + their subagents) over every session that recorded
    writes to it, each only in its own time on the goal; None if no session worked on it.
    transcript (optional) only hints where the session transcripts live."""
    goal = activity.canon(os.path.dirname(os.path.abspath(plan)))
    slug = os.path.basename(goal)
    lo_dt, hi_dt, _ = window(plan)
    lo, hi = int(lo_dt.timestamp()), hi_dt.timestamp()
    ents = activity.entries()
    birth = ents[0][0].timestamp() if ents else INF
    cache = _load(goal, lo)
    files, dirty = cache["files"], False

    def entry(path):
        nonlocal dirty
        old = files.get(path, {})
        new = scan(path, old, lo)
        if new is not None and new is not old:
            files[path], dirty = new, True
        return new

    sessions = {}
    for sid in activity.sessions_for(goal):
        p = transcript_of(sid, transcript)
        if p:
            sessions[p] = sid
    if lo < birth:  # the goal predates the record: find its earlier sessions in the transcripts
        for p in glob.glob(os.path.join(glob.escape(projects_dir()), "*", "*.jsonl")):
            try:
                if p in sessions or os.path.getmtime(p) < lo:
                    continue
                if p not in files:
                    with open(p, "rb") as f:
                        if (_ts(f.readline()) or INF) >= birth:
                            continue  # began after the record did: its writes are recorded
            except OSError:
                continue
            e = entry(p)
            if e and any(s == slug and t is not None and t < birth for t, s in e["writes"]):
                sessions[p] = os.path.splitext(os.path.basename(p))[0]

    total, counted = 0, False
    for p, sid in sessions.items():
        e = entry(p)
        wins = windows_of(goal, sid, e["writes"], lo, hi, birth) if e else []
        if not wins:
            continue
        counted = True
        total += sum(c for k, c in e["use"].items() if inside(int(k), wins))
        for sub in glob.glob(os.path.join(glob.escape(os.path.splitext(p)[0]), "subagents", "*.jsonl")):
            try:
                if os.path.getmtime(sub) < lo:
                    continue
            except OSError:
                continue
            se = entry(sub)
            if se and se["first"] is not None and inside(se["first"], wins):
                total += sum(c for k, c in se["use"].items() if int(k) <= hi)
    if dirty:
        try:
            fileio.write_atomic(os.path.join(goal, CACHE), json.dumps(cache, separators=(",", ":")))
        except OSError:
            pass
    return total if counted else None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = [a for a in sys.argv[1:] if a != "--write"]
    transcript, plan = (args[0], args[1]) if len(args) > 1 else (None, args[0])
    _, _, size = window(plan)
    total = measure(plan, transcript)
    if total is None:
        sys.exit("no session recorded work on this goal")
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
