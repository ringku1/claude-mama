#!/usr/bin/env python3
"""Step estimates: a goal takes about its critical path, not the sum of its steps.

Steps whose deps allow run in parallel, so the time to finish is the longest chain of
dependent steps. Adding every step's estimate over-counted parallel goals 3-4×.

Past goals calibrate it: the metrics lines in the store's lessons.md and the user's
patterns.md record "est <n>m critical path … actual <m>m (active <k>m)"; the median of
active / critical path over the last goals scales the estimate (needs 3 of them). Tokens the
same way: the median measured tokens per step of the last 10 goals in lessons.md (patterns.md
fills in while lessons.md has under 3) × this plan's steps is the likely spend, to size the budget
from (picked sizes ran from half to 4× of what goals used); plan-set refuses a first approval below it.

Usage: estimate.py <plan.md>   # prints the critical path, the sum, what's left, and the likely time
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402,F401  (UTF-8 output)

SKIP = {"obsolete", "parked"}
FINISHED = {"done", "unverified"}  # unverified: its verify couldn't run here; finished all the same


def expand(deps):
    """'S1-S4, S6a' -> ['S1','S2','S3','S4','S6a']"""
    out = []
    for part in re.split(r"[,\s]+", deps or ""):
        m = re.fullmatch(r"S(\d+)-S?(\d+)", part)
        if m:
            out += [f"S{n}" for n in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif re.fullmatch(r"S\d+\w*", part):
            out.append(part)
    return out


def minutes(est):
    """'15m' -> 15, '1h 20m' -> 80, '' -> 0"""
    return sum(int(n) * (60 if u == "h" else 1) for n, u in re.findall(r"(\d+)\s*([hm])", est or ""))


def critical_path(steps, left=False):
    """steps: [(id, deps, est, status)]. Longest chain of dependent steps, in minutes.
    left=True: finished (done/unverified) steps count 0 (the time still to go). Obsolete/parked steps are skipped;
    a dependency cycle is cut instead of looping."""
    live = {s[0]: s for s in steps if s[3] not in SKIP}
    memo, active = {}, set()

    def chain(sid):
        if sid in memo:
            return memo[sid]
        if sid in active:
            return 0
        active.add(sid)
        _, deps, est, status = live[sid]
        own = 0 if left and status in FINISHED else minutes(est)
        memo[sid] = own + max((chain(d) for d in expand(deps) if d in live), default=0)
        active.discard(sid)
        return memo[sid]

    return max((chain(s) for s in live), default=0)


def width(steps, left=False):
    """How many steps can run at once if each starts as soon as its deps finish."""
    live = {s[0]: s for s in steps if s[3] not in SKIP and not (left and s[3] in FINISHED)}
    finish, active = {}, set()

    def end(sid):
        if sid not in finish:
            if sid in active:
                return 0
            active.add(sid)
            start = max((end(d) for d in expand(live[sid][1]) if d in live), default=0)
            finish[sid] = (start, start + max(minutes(live[sid][2]), 1))
            active.discard(sid)
        return finish[sid][1]

    for s in live:
        end(s)
    edges = sorted([(a, 1) for a, _ in finish.values()] + [(b, -1) for _, b in finish.values()],
                   key=lambda e: (e[0], e[1]))
    now = best = 0
    for _, d in edges:
        now += d
        best = max(best, now)
    return best


def total(steps, left=False):
    return sum(minutes(s[2]) for s in steps if s[3] not in SKIP and not (left and s[3] in FINISHED))


def split_row(line):
    """A markdown table row's cells, raw: `\\|` inside a cell (an escaped pipe) doesn't split it."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table(text, section):
    """The `## <section>` markdown table: (header cells, rows). Rows with an empty first cell are
    skipped; short rows are padded so every row indexes like the header."""
    m = re.search(rf"^## {section}\n(.*?)(?=^## |\Z)", text or "", re.M | re.S)
    rows = [[c.replace("\\|", "|") for c in split_row(l)]
            for l in (m.group(1).splitlines() if m else []) if l.lstrip().startswith("|")]
    if len(rows) < 2:
        return [], []
    w = len(rows[0])
    return rows[0], [r + [""] * (w - len(r)) for r in rows[2:] if r and r[0]]


def steps_of(plan_text):
    """[(id, deps, est, status)] for every step row."""
    hdr, rows = table(plan_text, "Steps")
    i = {k: n for n, k in enumerate(hdr)}
    if not {"deps", "est", "status"} <= i.keys():
        return []
    return [(r[0], r[i["deps"]], r[i["est"]], r[i["status"]]) for r in rows]


RECORD = re.compile(r"est (\d+)m critical path[^|]*?actual ~?(\d+)m(?: \(active (\d+)m\))?")


def history(plan_path):
    """(estimate, actual) minute pairs from past goals, oldest first: this repo's lessons.md,
    then the user's patterns.md. Only records whose estimate was the critical path count."""
    pairs = []
    store = os.path.dirname(os.path.dirname(os.path.abspath(plan_path)))
    for f in (os.path.join(store, "lessons.md"), os.path.expanduser("~/.claude/mama/patterns.md")):
        try:
            text = open(f, encoding="utf-8").read()
        except OSError:
            continue
        for m in RECORD.finditer(text):
            pair = (int(m.group(1)), int(m.group(3) or m.group(2)))
            if pair[0] and pair not in pairs:
                pairs.append(pair)
    return pairs


def ratio(plan_path, last=10):
    """Median actual / estimate over the last goals, kept within 0.2-1.5; None under 3 records."""
    r = sorted(a / e for e, a in history(plan_path)[-last:])
    if len(r) < 3:
        return None, 0
    mid = len(r) // 2
    med = r[mid] if len(r) % 2 else (r[mid - 1] + r[mid]) / 2
    return min(max(med, 0.2), 1.5), len(r)


TOKENS = (re.compile(r"\| steps (\d+) \|[^\n]*?tokens est [^/|\n]*/ ~?([\d.]+)([kM])"),        # lessons.md metrics
          re.compile(r", (\d+) steps?\):[^\n]*?/ ~?([\d.]+)([kM]) measured"))                # patterns.md goals


def token_history(plan_path, last=10):
    """(steps, tokens) per past goal, oldest first: the last `last` metrics lines of this repo's
    lessons.md; while those are fewer than 3, the user's patterns.md goals (not already there) fill in."""
    def read(f, rx):
        try:
            text = open(f, encoding="utf-8").read()
        except OSError:
            return []
        return [(int(m.group(1)), round(float(m.group(2)) * (1_000_000 if m.group(3) == "M" else 1_000)))
                for m in rx.finditer(text) if int(m.group(1)) and float(m.group(2))]
    store = os.path.dirname(os.path.dirname(os.path.abspath(plan_path)))
    pairs = read(os.path.join(store, "lessons.md"), TOKENS[0])[-last:]
    if len(pairs) < 3:
        extra = [p for p in read(os.path.expanduser("~/.claude/mama/patterns.md"), TOKENS[1])
                 if p not in pairs]  # a goal in both files counts once
        pairs = (extra + pairs)[-last:]
    return pairs


def token_rate(plan_path, last=10):
    """Median tokens per step over the last goals; (None, 0) under 3 records."""
    r = sorted(t / n for n, t in token_history(plan_path)[-last:])
    if len(r) < 3:
        return None, 0
    mid = len(r) // 2
    return (r[mid] if len(r) % 2 else (r[mid - 1] + r[mid]) / 2), len(r)


def tokens_likely(plan_text, plan_path):
    """(likely tokens, rate, goals) for this plan's live steps; (None, None, 0) without history."""
    steps = len([x for x in steps_of(plan_text) if x[3] not in SKIP])
    rate, n = token_rate(plan_path) if plan_path and steps else (None, 0)
    return (steps * rate if rate is not None else None), rate, n


def size_for(tokens):
    """The smallest budget size that covers `tokens`: S, M, or `L <n>M` rounded up to 0.1M."""
    if tokens <= 300_000:
        return "S"
    if tokens <= 1_000_000:
        return "M"
    m = -(-int(tokens) // 100_000) / 10
    return f"L {m:g}M"


def tokens_line(steps, plan_path, size=None):
    """`tokens likely ~…` for a plan of `steps` live steps, or "" without history."""
    rate, n = token_rate(plan_path) if plan_path and steps else (None, 0)
    if rate is None:
        return ""
    likely = steps * rate
    out = f"tokens likely ~{fmt(likely)} ({steps} steps × ~{fmt(rate)} per step, last {n} goals)"
    try:
        import spend
        cap = spend.ceiling(size) if size else None
    except Exception:
        cap = None
    if cap and cap < likely:
        out += f" — over the budget size {size}: size it to cover this"
    return out


def fmt(tokens):
    return f"{tokens / 1e6:.1f}M" if tokens >= 1e6 else f"{round(tokens / 1e3)}k"


def summary(plan_text, plan_path=None):
    s = steps_of(plan_text)
    if not any(minutes(x[2]) for x in s):
        return ""
    cp, left = critical_path(s), critical_path(s, left=True)
    out = f"estimate: critical path {cp}m (sum {total(s)}m, up to {width(s)} at once) · left {left}m"
    k, n = ratio(plan_path) if plan_path else (None, 0)
    if k is None:
        out += " — no past goals to calibrate yet; runs often take less than the critical path"
    else:
        out += (f" · likely ~{max(round(cp * k), 1)}m, ~{round(left * k)}m left "
                f"(past goals took ×{k:.2f} of the critical path, last {n})")
    size = re.search(r"budget: [^/|\n]*/ ([^|\n]+)", plan_text)
    tok = tokens_line(len([x for x in s if x[3] not in SKIP]), plan_path, size.group(1).strip() if size else None)
    return out + ("\n" + tok if tok else "")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(summary(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1]) or "no step estimates")
