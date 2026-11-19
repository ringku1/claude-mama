#!/usr/bin/env python3
"""Create a goal's tracking folder, clean, in one step.

Usage: new-goal.py <store> <slug> <type> "<where it came from>" [--tier quick|standard|full] [--quick]
  type: build | fix | research | mixed
  --tier: the header's tier (— until research picks it; rules/research.md)
  --quick: same as --tier quick: mode quick, and a 3-line overview instead of the full one
Creates <store>/<slug>/ (suffix -2, -3… if taken) with plan.md (header filled: slug, type,
status planning, started now), overview.md (template) and log.md (empty, then E1 via log.py).
Template comments are stripped; the start is marked as the first milestone (.milestone, see
overview.py). Prints the goal folder path.
"""
import datetime, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402
import overview  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "..", "templates")


QUICK_OVERVIEW = """# <task in plain words>

**Status:** Planning · <progress, e.g. "1 of 2 done">

**Done means:** <one line> · **Result:** <at close: what changed, how it was checked, branch / commit>
"""


def strip_comments(text):
    return re.sub(r"<!--.*?-->\n*", "", text, flags=re.S)


TIERS = ("quick", "standard", "full")


def parse(argv):
    """(positional args, tier or None); exits with the usage on a bad --tier."""
    args, tier, i = [], None, 0
    while i < len(argv):
        a = argv[i]
        if a == "--quick":
            tier = "quick"
        elif a == "--tier" or a.startswith("--tier="):
            if a == "--tier":
                i += 1
                a = "--tier=" + (argv[i] if i < len(argv) else "")
            tier = a.split("=", 1)[1]
            if tier not in TIERS:
                sys.exit(f"bad --tier {tier!r}; use one of {' | '.join(TIERS)}\n\n" + __doc__)
        else:
            args.append(a)
        i += 1
    return args, tier


def main():
    args, tier = parse(sys.argv[1:])
    quick = tier == "quick"
    if len(args) != 4 or args[2] not in {"build", "fix", "research", "mixed"}:
        sys.exit(__doc__)
    store, base, kind, source = args
    base = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-")[:48]
    os.makedirs(store, exist_ok=True)
    slug, n = base, 1
    while True:
        try:
            os.mkdir(os.path.join(store, slug))
            break
        except FileExistsError:
            n += 1
            slug = f"{base}-{n}"
    goal = os.path.join(store, slug)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    plan = strip_comments(open(os.path.join(TPL, "plan.md"), encoding="utf-8").read())
    plan = plan.replace("goal: <slug>", f"goal: {slug}")
    plan = re.sub(r"type: <[^>]*>", f"type: {kind}", plan, count=1)
    plan = re.sub(r"status: <[^>]*>", "status: planning", plan, count=1)
    plan = re.sub(r"mode: <[^>]*>", "mode: quick" if quick else "mode: —", plan, count=1)
    plan = re.sub(r"tier: <[^>]*>", f"tier: {tier or '—'}", plan, count=1)
    plan = re.sub(r"progress: <[^|]*\| blocked: <n>", "progress: 0/0 (0%) | blocked: 0", plan, count=1)
    plan = re.sub(r"budget: ~<spent>k / <[^>]*>", "budget: ~0k / —", plan, count=1)
    plan = re.sub(r"started: <[^>]*>", f"started: {now}", plan, count=1)
    head, sep, rest = plan.partition("\n## ")
    head = re.sub(r"(\w[\w ]*?): <[^>]*>", r"\1: —", head)  # unknown yet → —, set when known
    plan = head + sep + rest
    fileio.write_atomic(os.path.join(goal, "plan.md"), plan)

    raw = open(os.path.join(TPL, "overview.md"), encoding="utf-8").read()
    rules = re.search(r"<!--(.*?)-->", raw, re.S)
    ov = QUICK_OVERVIEW if quick else strip_comments(raw)
    overview.milestone(goal)  # the start counts: the overview written next is fresh
    fileio.write_atomic(os.path.join(goal, "overview.md"), ov)

    open(os.path.join(goal, "log.md"), "w", encoding="utf-8").close()
    subprocess.run([sys.executable, os.path.join(HERE, "log.py"), os.path.join(goal, "log.md"), "E",
                    f"start {kind} from {source}"], check=True, stdout=subprocess.DEVNULL)
    print(goal)
    if rules and not quick:
        print("Overview rules:" + rules.group(1).rstrip())


if __name__ == "__main__":
    main()
