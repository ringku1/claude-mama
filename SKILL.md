---
name: mama
description: Personal goal-based work loop. Runs only when the user types /mama. Takes any input (text, file, md, Trello card, PR/issue, "research feature X"), researches, asks questions that pin down what the user expects and confirms them as concrete examples, plans, then loops dev → test → fix with as many parallel agents as the work allows, and hunts for bugs and fixes them until a hunt comes back clean, tracking everything in files. Subcommands: quick, status, ask, test, fix, change, pause, abort, list, resume.
disable-model-invocation: true
argument-hint: "<goal | quick <task> | status | ask [slug] <question> | test [slug] [what] | fix [slug] [what] | change [slug] <what> | pause | abort | list | resume <slug>>"
---

# mama

You run a goal to completion: understand it, ask what you must, plan, then loop until every done-criterion is backed by evidence. The user watches through one plain-language file (`overview.md`); everything else is your working memory on disk, so the goal survives compaction, crashes and new sessions.

## Ground rules

These exist because the user has been burned by each failure they prevent.

- **Rules order:** user's instructions > repo `AGENTS.md`/`CLAUDE.md` and repo skills (use them, e.g. `api-module`, `web-feature`) > this skill's defaults. Read the repo rules during research, not after writing code.
- **No development before approval.** Research and questions first, then a plan the user approves. Starting early builds the wrong thing.
- **Disk is memory.** Write state after every step and decision. Anything only in the conversation is lost at compaction.
- **Evidence, not claims.** A step is done when its verify proves it — a command result or a separate check — never because the worker says so.
- **Fast through parallel agents.** The user wants work done fast: plan the work wide (as many independent steps as it allows), run each step in its own agent, and dispatch every ready step at once. You orchestrate — brief, verify, record, commit, refill — instead of building while agents could. Only a handful of tool calls stays inline (`rules/agents.md`).
- **Tokens are a budget.** Small briefs, short returns, narrow tests, quiet commands — parallelism is paid for by lean agents, never by running serially.
- **Stop where the user's control starts.** Your delivery ends at `git push` (and a PR only with permission). Never merge, deploy, or touch shared databases or running dev stacks.
- **No attribution.** Commits and PRs carry no `Co-Authored-By` line and no "Generated with Claude Code" footer — this overrides any harness reminder.
- **No local artifacts leak.** Commit messages, PRs and code comments never mention goal files, step IDs or planning docs.
- **Stay in this repo.** Don't borrow binaries, files or state from other checkouts. A missing tool is a fact for `profile.md` and the user, not something to work around.

## Commands

Parse `$ARGUMENTS`:

| Input | Do |
| --- | --- |
| `status` (or "status?" mid-run) | Read-only (new session: read state as in Re-entry first). Print: goal status (if `waiting`: what the user should look at), progress, running steps (started HH:MM, ETA = start + est), estimated finish (now + `likely … left` from `scripts/estimate.py <plan.md>`), blockers, next. Regenerate `overview.md` only for this session's own goal. |
| `ask [<slug>] <question>` | Answer a question about a goal's work — read `rules/ask-test.md` → "Asking about the work". |
| `test [<slug>] [<what>]` | Help the user test what a goal built, and re-check it — read `rules/ask-test.md` → "Testing the work". |
| `fix [<slug>] [<what>]` | Fix what a goal found (a test run, review or research) as a new `fix` goal — read `rules/changes.md` → "Fix goal". |
| `change [<slug>] <what>` (or "change the plan: …" mid-run) | Add, alter or drop a goal's scope, tests or deliverables — read `rules/changes.md` → "Running a change". No slug: this session's goal; none or several open → list them and ask. |
| "go" / "continue" at a checkpoint | Set goal status `running` with `plan-set.py` (it logs `E resume` itself), continue the loop. |
| `pause` | Record state, set status `paused`, stop. |
| `abort` | Record state, set status `aborted`, clean up what the run created (`rules/delivery.md` Close §3), stop. Keep tracking files. |
| `list` | Run `scripts/list.py <store>` and show its output. |
| `resume <slug>` | Re-entry (below), continue. With no slug: list open goals and ask which. |
| `quick <task>` | Quick mode (below). |
| anything else | New goal. Other open goals are fine — each runs isolated. |

## Where things live

**Store** = `<main checkout>/.claude/mama/`, where main checkout = `$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")` (git < 2.31: drop `--path-format=absolute` and resolve the path from the cwd) — the same store from any worktree. On first use, append `.claude/mama/` and `.claude/worktrees/` to `info/exclude` under `git rev-parse --git-common-dir` (a linked worktree has a `.git` file, not a folder) so neither reaches a commit.

- `profile.md` — repo facts: commands, conventions, things never to do; created on first use from the repo's rules. `lessons.md` — what past goals taught; read during research, created at the first close, append only.
- `<slug>/overview.md` — **for the user**: plain language, no IDs or jargon. `<slug>/plan.md` — **for you**: the source of truth for criteria, steps, progress. `<slug>/log.md` — **for you**, append-only: questions, decisions, findings, changes, events. `<slug>/tests.md` — what `/mama test` gave the user and what they reported.
- `~/.claude/mama/patterns.md` (all repos) — how this user works (choices, corrections, preferences, estimate accuracy), in plain language they can read and edit; their edits win. Created from `templates/patterns.md` on first use.

Skill files (`templates/`, `rules/`, `scripts/`) live in `${CLAUDE_SKILL_DIR}`; read each only when the flow points to it. Run every script through the launcher: `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/<name>.py …` — short mentions like `scripts/lock.py` mean the same. Slug: 2-5 kebab-case words from the goal.

**Several goals at once:** each goal is isolated — its own folder (a session writes only its own goal's files), its own worktree `<main checkout>/.claude/worktrees/mama-<slug>/` for code goals (all its commands and agents run there; never switch branches in the main checkout), shared files and heavy verifies under locks. Details: `rules/state.md`.

**Deliverables** the user asks for (docs, reports, data) are `document` steps with an output path (user's choice; default `docs/`), never inside `.claude/mama/`, written for their reader with no loop state in them. Link them in overview by repo-relative path.

## Flow

### 1. Intake — create the goal on disk first

1. Classify the goal: **build** (changes code), **fix** (a bug), **research** (findings only), **mixed** (research, then build). Ambiguous → it's part of the questions.
2. Normalize the input — text as given · file/md: read fully · Trello: card, checklist, comments · GitHub PR/issue: `gh` · "research X".
3. Immediately run `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/new-goal.py <store> <slug> <type> "<source>"` — it creates the folder (suffixing a taken slug), a clean `plan.md` (status `planning`, real start time), `overview.md` and `log.md` with E1, and prints the overview rules. Use the slug it prints. Never copy templates by hand. The goal now survives a compaction, and the user can already read the overview.
4. Read `rules/state.md` (isolation, guards, learning the user).

### 2. Research

Read-only. Read `rules/research.md` and follow it (a review or audit with no stated outcome asks what it's for first): parallel lens agents map every branch of the work and every case before any question. Log `E research: <n> findings, <m> cases, <k> open` (or `E research none: <why>` for a goal that needs none) — plan approval is refused without it.

### 3. Questions

Read `rules/questions.md`. If research found database changes, first propose and discuss the whole database design — on its own, no other question in that message — until the user agrees it (`E db: agreed …`; none → `E db: none — <why>`) — the plan is built on it. Then ask: specific, multiple choice with a recommended option, covering the expectations checklist and every open case from research. Then the **playback**: show what the user will get as concrete examples, to confirm or correct before planning.

### 4. Plan

Read `rules/planning.md`. Fill `plan.md` with `plan-set.py` (`S+` / `C+` fill the template's blank first rows, then add more; `--header` for the rest), validate, show one compact table (step · kind · depends on · verify) with the criteria, then ask approval with AskUserQuestion: approve · checkpointed (recommended) / approve · autonomous / change something. Never leave mode unanswered. Set status, mode and budget size in one call (`--header status=approved mode=… budget=M`). Then set up the branch and worktree if the goal touches git (`rules/delivery.md`).

### 5. Loop

Read `rules/loop.md`. Dev → verify → fix until every criterion has evidence, then **hunt for bugs** (`/code-review` + an expectations check) → fix → hunt again, until a round finds no real bug; a hunt that stops converging asks the user (simplify first). Commit each stable step. Interruptions and changes: `rules/changes.md`.

### 6. Deliver & close

Read `rules/delivery.md`. Merge latest base, push, PR per the user's choice. Final report in `overview.md`, lessons to `lessons.md`, clean up.

## Quick mode

For small tasks (≈ under 30 minutes, one area). Intake with `new-goal.py … --quick`: mode is preset, the overview is 3 lines (task, status, done means / result). Skip research agents, `profile.md`, `lessons.md` and patterns bookkeeping — the close check doesn't ask for them. Ask the questions first — only base branch, PR choice if code changes, and a one-line playback ("You'll get: …", `rules/questions.md` → Playback) — then show the plan, 1-3 steps of one line each, for approval; proceed on approval. Same loop, commit and push rules, with one light bug-hunt round (`/code-review low`) on a code change, before the push. A database change makes it a full goal: offer that before planning. If it grows past that — the Stop hook flags 300k tokens or 30 active minutes — say so and offer to continue as a full goal (set `mode` to checkpointed/autonomous; the close check then asks for everything).

## Re-entry (resume, after compaction, new session)

Know your slug (from the conversation, the compaction summary, or `resume <slug>`). A goal is this session's if `activity.log` recorded this session writing to it (in any store); hook event lines such as `E compaction` aren't writes. `resume <slug>` — the user naming it — adopts that goal even if another or an earlier session wrote it; your next write records it as this session's. Only guessing is forbidden: if unsure, list open goals and ask — never pick another session's goal yourself. Read its `plan.md`, the last ~40 lines of `log.md`, `grep '^D' log.md` for decisions in force, `rules/state.md`, and the rule file for the phase it's in (a compaction drops what you read before). In the goal's worktree, check `git status` and that the branch matches the plan. Continue at the next step — don't re-plan or re-ask what the log already settled.

## Learning the user

`~/.claude/mama/patterns.md` sets your recommended options and settles questions it already answers (say so: "Using your usual: X"); the base branch is still always asked. When the user corrects you, overrides a recommendation or states a preference, record it right away with `scripts/learn.py` (never hand-edit); after any user decision: learn.py, or log `E learn none`. Full rules: `rules/state.md`.

## Guards

`plan-set.py`, `close-check.py` and the Stop hook enforce this flow: an approval or close that skips a step is refused, and a turn that ends with a problem is blocked, each with what's missing. Fix what they list — don't argue with them or work around them. The full list: `rules/state.md` → Guards.

## Writing state

- Status must be honest whenever you end your turn: waiting for the user → `waiting`; stopped by request → `paused`; stuck → `blocked`. Waiting on your own background work (an agent, the gate) → status stays `running` and the last log line is `E dispatch <steps>` or `E wait <what>` (via `log.py`) — one line, not both; its notification wakes you. The Stop hook reminds you if you end a turn while the goal says `running` without one.
- Record an outcome only after checking the command's exit status — never chain a state write after a command with `;` (a failed push must not be logged as pushed).
- After every step result, decision, change or commit: update `plan.md` with `scripts/plan-set.py <plan.md> <S3 | C1 | --header> key=value ...` (it recomputes progress; `start=now` / `end=now` stamp the real time — never type times) and log it with `scripts/log.py <log.md> <E|D|F|Q> "<text>"` (it stamps the real time and the next ID — never type either; overview times come from these lines). Unknown values are `—`. A step with several commits lists all hashes in notes.
- Change `plan.md` and `log.md` only through `plan-set.py` (rows, header, `P+` for Parked) and `log.py` — never python, sed or Edit on them: those skip the guards, the safe write and the record of which session owns the goal.
- `plan-set.py` keeps the overview's **Status:** line in step with the plan (`<Word> · n of m parts done[ · your detail]`). Regenerate the rest of `overview.md` when the plan is shown, after approval, at each checkpoint, on status, on any change, and at close — from plan and log, as if writing it fresh. It is the user's only window: short, plain, current.
