#!/usr/bin/env python3
"""Record what mama learned about the user in ~/.claude/mama/patterns.md (locked, dated, counted).

Usage:
  learn.py seen    "<pattern>" [section]   # one more consistent observation (new → Watching 1/1)
  learn.py contra  "<pattern>"             # the user did the opposite (count down; twice in a row → Watching)
  learn.py stated  "<pattern>" [section]   # the user said it outright → learned at once
  learn.py goal    "<what it was> (<type>, <n> steps): est <m>m / <size>, actual <m>m / ~<n>k"

Match an existing line by copying its pattern text (the part before the first " — ").
At 3/… a Watching line moves to [section] (default "How you like things done").
Sections: "Choices you make", "How you like things done", "Corrections you've made".
"""
import datetime, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402

PATH = os.path.expanduser("~/.claude/mama/patterns.md")
LOCK = os.path.expanduser("~/.claude/mama/.patterns.lock")
WATCH = "## Watching (fewer than 3 observations)"
GOALS = "## Goals and estimates"
DEFAULT = "How you like things done"
STREAK = "contradicted last time"  # marks one contra since the last seen
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "patterns.md")


def find(lines, text):
    key = text.strip().lower()
    for i, l in enumerate(lines):
        if l.startswith("- ") and l[2:].split(" — ")[0].strip().lower() == key:
            return i
    return None


def insert(lines, heading, line):
    try:
        h = lines.index(heading)
    except ValueError:
        lines += ["", heading, ""]
        h = len(lines) - 2
    j = h + 1
    while j < len(lines) and not lines[j].startswith("## "):
        j += 1
    while j > h + 1 and not lines[j - 1].strip():
        j -= 1
    lines.insert(j, line)


def section_of(lines, i):
    for j in range(i, -1, -1):
        if lines[j].startswith("## "):
            return lines[j]
    return ""


def fresh():
    """A new patterns.md from templates/patterns.md: its sections, without the comment or examples."""
    try:
        t = open(TEMPLATE, encoding="utf-8").read()
    except OSError:
        return ["# How you work", ""]
    t = re.sub(r"<!--.*?-->\s*", "", t, flags=re.S)
    return [l for l in t.split("\n") if not l.startswith("- <")]


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in {"seen", "contra", "stated", "goal"}:
        sys.exit(__doc__)
    kind, text = sys.argv[1], " ".join(sys.argv[2].split())
    section = "## " + (sys.argv[3] if len(sys.argv) > 3 else DEFAULT)
    today = datetime.date.today().isoformat()
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(LOCK, "a+") as lk, fileio.locked(lk):
        lines = open(PATH, encoding="utf-8").read().split("\n") if os.path.exists(PATH) else fresh()
        if kind == "goal":
            insert(lines, GOALS, f"- {text} — last {today}")
            out = lines[[i for i, l in enumerate(lines) if l.startswith(f"- {text}")][-1]]
        else:
            i = find(lines, text)
            if i is None and kind == "contra":
                sys.exit(f"not found: {text!r}. To record what the user wants instead, use: learn.py seen \"<their preference>\"")
            old = lines.pop(i) if i is not None else None
            where = section_of(lines, i) if i is not None else WATCH
            if old and " — stated — " in old and kind != "stated":
                # a stated preference keeps its status; only the date moves
                if kind == "contra":
                    print(f"NOTE: the user went against a stated preference — ask once if it changed: {text}")
                lines.insert(i, re.sub(r" — last \S+$", f" — last {today}", old))
                text_out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
                fileio.write_atomic(PATH, text_out.rstrip("\n") + "\n")
                print(lines[i])
                return
            n, m, streak = 0, 0, 0
            if old:
                c = re.search(r" — (\d+)/(\d+) — ", old)
                if c:
                    n, m = int(c.group(1)), int(c.group(2))
                elif " — stated — " in old:
                    n, m = 3, 3
                streak = 1 if STREAK in old else 0
            if kind == "stated":
                line, where = f"- {text} — stated — last {today}", (section if where == WATCH or not old else where)
            else:
                # a seen resets the contradiction streak; two contras in a row demote a learned line
                n, m = (n + 1, m + 1) if kind == "seen" else (max(n - 1, 0), m + 1)
                streak = streak + 1 if kind == "contra" else 0
                if kind == "contra" and where != WATCH and streak >= 2:
                    where, streak = WATCH, 0
                if kind == "seen" and where == WATCH and n >= 3:
                    where = section
                line = f"- {text} — {n}/{m}" + (f" — {STREAK}" if streak else "") + f" — last {today}"
                if n == 0 and m >= 2:
                    print(f"dropped: {text} (contradicted)")
                    line = None
            if line:
                insert(lines, where, line)
            out = line or ""
        text_out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
        fileio.write_atomic(PATH, text_out.rstrip("\n") + "\n")
    print(out)


if __name__ == "__main__":
    main()
