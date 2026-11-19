# Goals on disk: isolation, guards, learning

## Several goals at once

- **Worktree:** also for research goals that commit a deliverable; on the goal's branch, recorded in the plan header. Prefix shell commands with `cd <worktree> &&`; use absolute paths for file tools. Research-only goals work read-only in the main checkout.
- **Shared files** (`profile.md`, `lessons.md`, `info/exclude`, `patterns.md`): create only if absent (`set -C`), add exclude lines only if missing, append/edit under `scripts/lock.py <store>/.shared.lock` (`~/.claude/mama/.patterns.lock` for patterns).
- **Heavy runs:** verifies touching shared services (database, Redis), every full gate, builds and e2e run under `scripts/lock.py <store>/.heavy.lock <cmd>` (shell syntax in `bash -c '…'`).
- **Agent limit:** `scripts/resources.py <ready> <store> <own slug>` subtracts other goals' running steps.
- **`git fetch` / `git push`** run as `git -C <main checkout> ...` (refs are shared with the worktree; works for any remote URL).
- **Same branch, two goals:** a branch is checked out only once, so the second goal shares the first's worktree and runs after it, never in parallel. Both overviews say one push carries both goals' commits; never push one goal's commits while the other has uncommitted work in the tree.

## Which session owns a goal

`step.py`, `log.py`, `plan-set.py` and `new-goal.py` record each write's session (`CLAUDE_CODE_SESSION_ID`; without it they warn and record nothing) in `~/.claude/mama/activity.log`. Hooks use that record, never a guess, to find this session's goal (a goal no record ties to it is never claimed); `spend.py` uses it to count tokens (recorded sessions, plus a transcript scan only for goals older than `activity.log`). Goal files written any other way leave the goal unowned and unmeasured.

Waiting time is logged so estimates use active time: `plan-set --header status=waiting` logs `E waiting` and the switch back logs `E resume` by themselves; questions are `Q` lines, answers `D … tag: user`.

## Guards (scripts and hooks enforce these — don't work around them)

- `plan-set.py`:
  - stamps step start/end; warns on a step started before its deps; refuses a typed end before the start (past midnight: `end=now`);
  - refuses `status=approved|running` without a mode;
  - refuses a full or standard goal's first approval without `E research …`, `E expectations …`, `E playback …` (build/fix/mixed: `E db …` before the playback) and `budget=…` in the same call; a quick goal's without its one-line playback; a budget below tokens likely without `D budget … (tag: user)`;
  - refuses `status=done` until `close-check.py` passes;
  - keeps `budget` as `~<n>k / S|M|L <n>k|M` (e.g. `L 800k`, `L 1.5M`); refuses a raise past 2× the `approved:` size without `D budget … (tag: user)`;
  - allows `pr` only as `ask-at-end | auto | none | declined | <url>`;
  - fills blank template rows on `S+`/`C+`, parks ideas with `P+`, regenerates the overview's generated block, prints the estimate (critical path, sum, steps at once, likely time and tokens), reminds you of the Trello start comment;
  - warns "the Stop hook hasn't run for <n> min" when a turn ended on the goal (an `E wait …` / `waiting` line over 10 min old) and `.heartbeat` is older than it: the hooks aren't firing — check they're installed (`install.py`) and tell the user; spend and the guards below are off until they are.
- `step.py` is plan-set + log in one call (same checks, same output).
- `close-check.py` checks criteria evidence, step times, placeholders, Trello, metrics, patterns, profile (or `E profile none`); for code goals, a last bug-hunt round with 0 real bugs or a `D hunt: deliver with known issues … (tag: user)` after it, a `D hunt: extra round … (tag: user)` before each round past the tier's cap, every round naming `/code-review` (round 1 `high` unless quick), and a push after the last hunt; a goal whose turn ended (`E wait` / `waiting` line) but has no `.heartbeat` (the Stop hook never ran). It refuses this goal's commits (on the branch since `started:`, also when base == branch) with attribution lines or loop internals (mama, plan.md, "step S3" / "criterion C2"; bare IDs pass). At close and every turn, the overview fails on this goal's step/log IDs, file:line refs (not URLs or host:port) or length over one screen.
- The Stop hook records real token spend in the plan header each turn end (`scripts/spend.py`) and blocks, listing every problem, when your goal:
  - is `running` at ≥70% of budget after its one auto-raise (`rules/loop.md` → Budget);
  - has a cap hunt round with real bugs and no `D hunt: …` after it (ask: deliver with known issues / one more low round);
  - can't measure spend: "spend not measured: <error> — see ~/.claude/mama/hook-errors.log" → read that log, fix the cause if it's in this goal (e.g. a broken plan header), else tell the user; never carry on as if the budget were checked;
  - is `running` without a final `E dispatch …` or `E wait …` line;
  - is quick and past 300k tokens or 30 active minutes with no `D … quick …` answer (offer a full goal);
  - changed scope, went `waiting` or closed after the overview's hand-written parts were last written;
  - has a user decision with no learning after it (not in quick mode);
  - is `done` while the close check fails.

  It blocks when a problem appears or the list changes, never twice on an identical list. Hook failures never block; they go to `~/.claude/mama/hook-errors.log`. Each Stop on an open goal writes `<goal>/.heartbeat` (time + spend).

## Learning the user

Beyond SKILL.md: a pattern also shapes the plan and overview; explicit user instructions and repo rules beat it.
- **Learn** immediately when the user corrects your work or plan, overrides a recommendation or states a preference; at close, their choices (options, mode, PR), goal size, estimate vs actual.
- **Write** with `scripts/learn.py seen|contra|stated|goal "<pattern>"` (locks, counts, dates, promotes). After any user decision: learn.py, or log `E learn none`.
- **Format**: `<pattern> — <n>/<m> — last <date>`, one line each. Learned at ≥3 consistent observations, else under "Watching"; a preference stated outright is learned at once (`stated`). A contradiction lowers the count; two in a row move a learned line back to Watching; one contradicted down to 0 is deleted.
- **Never** record secrets, client data or repo facts (those go in `profile.md` / `lessons.md`).

## Overview

`overview.md` has a generated block between `<!-- mama:auto:start -->` and `<!-- mama:auto:end -->`: Status line, Done means, Timeline, Where we are, Needs your input. `step.py` / `plan-set.py` / `log.py U` rewrite it from plan and log; never edit inside it. Its Timeline is the `U` lines: `log.py <log> U "<plain text>"` at milestones the user would care about (a part working end to end, hunt done, budget raised, pushed, blocked) — a few per goal, not one per step; the start and the approval rows come from plan-set's own log lines. Hand-written parts outside it (title, Goal, Key decisions, What changed, Deliverables, Final report) are refreshed only when the plan is shown, scope changes, the goal goes `waiting`, and at close. An old overview without the markers keeps only its Status line in sync: write the rest by hand as before.
