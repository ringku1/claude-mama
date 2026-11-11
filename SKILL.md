---
name: mama
description: Personal goal-based work loop. Runs only when the user types /mama. Takes any input (text, file, md, Trello card, PR/issue, "research feature X"), researches, asks one batch of questions, plans, then loops dev → test → fix with as many parallel agents as the work allows until every done-criterion has evidence, tracking everything in files. Subcommands: quick, status, ask, test, fix, change, pause, abort, list, resume.
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

| Input                            | Do                                                                                                                   |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `status` (or "status?" mid-run)  | In a new session, read state first (Re-entry, read-only). Print: goal status (if `waiting`: what the user should look at), progress line, running steps (step, started HH:MM, ETA = start + est), estimated finish (now + `left` from `scripts/estimate.py <plan.md>`, calibrated per `rules/planning.md`), blockers, next. Regenerate `overview.md` only if the goal is this session's — another session's goal stays read-only. |
| `ask [<slug>] <question>`       | Answer a question about a goal's work, during or after it — see "Asking about the work". |
| `test [<slug>] [<what>]`        | Help the user test what a goal built, and check it ourselves — see "Testing the work". |
| `fix [<slug>] [<what>]`         | Fix what a goal found (a test run, review or research): a new `fix` goal whose input is that goal's findings — its report, `F` lines and Parked list (no slug: this session's last goal). Start it with `new-goal.py <store> <slug> fix "findings of <source slug>"`, verify the findings against the code in parallel (a read-only agent per area), then questions (first: which findings to fix) → plan as usual. Don't write to the source goal's files. |
| `change [<slug>] <what>` (or "change the plan: …" mid-run) | Modify the plan of an existing goal — add, alter or drop scope, tests or deliverables. Read `rules/changes.md` → "Running a change" and follow it. No slug: this session's goal; none, or several open → list them and ask. |
| "go" / "continue" at a checkpoint | Set goal status `running`, log `E resume`, continue the loop.                                                       |
| `pause`                          | Record state, set status `paused`, stop.                                                                              |
| `abort`                          | Record state, set status `aborted`, clean up what the run created (`rules/delivery.md` Close §3), stop. Keep tracking files. |
| `list`                           | One line per goal folder in the store: slug, status, progress, worktree (from each `plan.md` header).                |
| `resume <slug>`                  | Re-entry (below), continue. With no slug: list open goals and ask which.                                             |
| `quick <task>`                   | Quick mode (below).                                                                                                   |
| anything else                    | New goal. Other open goals are fine — each runs isolated (see "Several goals at once").                             |

## Where things live

**Store** = `<main checkout>/.claude/mama/`, where main checkout = `$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")` — the same store from any worktree. On first use, append `.claude/mama/` and `.claude/worktrees/` to `.git/info/exclude` so neither reaches a commit.

- `profile.md` — repo facts: commands, conventions, things never to do. Create on first use from the repo's rules; reuse after.
- `lessons.md` — what past goals taught. Read during research if it exists; created at the first close. Append only.
- `<slug>/overview.md` — **for the user.** Plain language, no IDs or jargon.
- `<slug>/plan.md` — **for you.** Source of truth for criteria, steps, progress.
- `<slug>/log.md` — **for you.** Append-only: questions, decisions, findings, changes, events.
- `<slug>/tests.md` — what `/mama test` gave the user and what they reported (created on first use).

**User-level**, all repos: `~/.claude/mama/patterns.md` — how this user works (choices, corrections, preferences, estimate accuracy). Created from `templates/patterns.md` on first use. It's about the user, so it's written in plain language they can read and edit; their edits win.

Skill files (`templates/`, `rules/`, `scripts/`) live in `${CLAUDE_SKILL_DIR}`; read each only when the flow points to it. Slug: 2-5 kebab-case words from the goal.

### Several goals at once

The user may run several goals in parallel sessions. Each goal is isolated:
- **Its own tracking folder** `<store>/<slug>/`; a session only ever writes its own goal's files. Remember your slug — it's in every re-entry.
- **Its own worktree** for build/fix/mixed goals (and research goals that commit a deliverable): `<main checkout>/.claude/worktrees/mama-<slug>/` on the goal's branch, recorded in the plan header. All code work, commands and agents for the goal happen there — prefix shell commands with `cd <worktree> &&` and use absolute paths for file tools. Research-only goals work read-only in the main checkout. Never switch branches in the main checkout; it belongs to the user.
- **Shared, so coordinated**:
  - Shared files (`profile.md`, `lessons.md`, `.git/info/exclude`, `patterns.md`): create only if absent (`set -C`), add exclude lines only if missing, and append/edit under `flock <store>/.shared.lock` (`~/.claude/mama/.patterns.lock` for patterns).
  - Verifies that touch shared services (database, Redis), every full gate, and heavy runs (build, e2e) go under `flock <store>/.heavy.lock <cmd>` so goals don't collide.
  - The agent limit (`scripts/resources.sh <ready> <store> <own slug>`) subtracts other goals' running steps.
  - `git fetch` and `git push` run as `git -C <main checkout> ...` — refs are shared with the worktree, and it works for any remote URL.

**Same branch, two goals:** a branch can be checked out only once, so a goal that targets a branch another open goal works on shares that goal's worktree and runs after it, never in parallel with it. Say in both overviews that one push carries both goals' commits, and never push one goal's commits while the other has uncommitted work in the tree.

**Times and IDs:** every `log.md` line goes through `python3 ${CLAUDE_SKILL_DIR}/scripts/log.py <log.md> <E|D|F|Q> "<text>"` — it stamps the real time and the next ID, so never type either by hand. Overview timeline times come from those log lines.

**Deliverables** the user asks for (docs, reports, data) are `document` steps with an output path (user's choice; default `docs/`), never inside `.claude/mama/`, written for their reader with no loop state in them. Link them in overview by repo-relative path.

## Flow

### 1. Intake — create the goal on disk first

1. Classify the goal: **build** (changes code), **fix** (a bug), **research** (findings only), **mixed** (research, then build). Ambiguous → it's part of the questions.
2. Normalize the input — text as given · file/md: read fully · Trello: card, checklist, comments · GitHub PR/issue: `gh` · "research X".
3. Immediately run `python3 ${CLAUDE_SKILL_DIR}/scripts/new-goal.py <store> <slug> <type> "<source>"` — it creates the folder (suffixing a taken slug), a clean `plan.md` (status `planning`, real start time), `overview.md` and `log.md` with E1, and prints the overview rules. Use the slug it prints. Never copy templates by hand. The goal now survives a compaction, and the user can already read the overview.

### 2. Research

Read-only. Read `rules/research.md` and follow it: parallel lens agents map every branch of the work and every case before any question. Log `E research: <n> findings, <m> cases, <k> open` (or `E research none: <why>` for a goal that needs none) — plan approval is refused without it.

### 3. Questions

Read `rules/questions.md`, then ask: one batch, specific, multiple choice with a recommended option — covering every open case from research.

### 4. Plan

Read `rules/planning.md`. Fill `plan.md` with `plan-set.py` (`S+` / `C+` fill the template's blank first rows, then add more; `--header` for the rest), validate, show one compact table (step · kind · depends on · verify) with the criteria, then ask approval with AskUserQuestion: approve · checkpointed (recommended) / approve · autonomous / change something. Never leave mode unanswered. Then set up the branch and worktree if the goal touches git (`rules/delivery.md`).

### 5. Loop

Read `rules/loop.md`. Dev → verify → fix until every criterion has evidence. Commit each stable step. Interruptions and changes: `rules/changes.md`.

### 6. Deliver & close

Read `rules/delivery.md`. Merge latest base, push, PR per the user's choice. Final report in `overview.md`, lessons to `lessons.md`, clean up.

## Quick mode

For small tasks (≈ under 30 minutes, one area). Intake with `new-goal.py … --quick`: mode is preset, the overview is 3 lines (task, status, done means / result). Skip research agents, `profile.md`, `lessons.md` and patterns bookkeeping — the close check doesn't ask for them. Ask only: base branch, and PR choice if code changes. Plan 1-3 steps, one line each, proceed on approval. Same loop, commit and push rules. If it grows past that, say so and offer to continue as a full goal (set `mode` to checkpointed/autonomous; the close check then asks for everything).

## Asking about the work

`/mama ask [<slug>] <question>`, e.g. "why did you pick a soft delete?", "which files changed?", "how was the upload limit tested?". Works on open and closed goals, from any session.

- **Which goal:** the slug given; else this session's goal; else the most recently updated goal in the store — name it in the first line of the answer ("About storage-page:"). Unsure between several → list them and ask.
- **Sources, cheapest first:** `overview.md` → `plan.md` (criteria evidence, step verify and notes) → `log.md` (`grep '^D'` decisions, `^F` findings, `^Q` questions) → the code: the goal's worktree if it still exists, else `git -C <main checkout> log/diff <base>...<branch>` (the branch outlives the worktree) → `tests.md` → `lessons.md`. Read the code only when the files don't answer it.
- **Answer** in a few plain lines, citing where it comes from (a decision and its reason, a commit, a `file:line`, a test). Say plainly what the record doesn't show — never fill gaps with a guess.
- **Read-only:** no edits to the goal's files or code (a log line after close would stretch its measured time). If the answer shows something is wrong or missing, say so and offer `/mama change <slug> …` (open goal) or a new goal (closed one) — don't act until the user picks.

## Testing the work

`/mama test [<slug>] [<what>]`, e.g. "test the storage page upload", "test empty folders", or just `test` for the whole goal. Goal choice as in `ask`.

1. **Scope:** the criteria and steps that match `<what>` (all criteria if none given). Read their verify, evidence, the decisions behind them, and the code they touched.
2. **Manual test guide for the user** — they test in their own running app; never start, stop, reseed or migrate it. Per scenario: where (URL / screen / command, which branch must be running), any setup data, the exact steps, the expected result in plain words. Cover the happy path, edges and errors the code actually handles (empty, limits, permissions), and say what is out of scope. Tell them which branch to run if theirs isn't it.
3. **Our own check, in parallel:** rerun the automated tests that prove those criteria (narrow, not the full suite), in the goal's worktree — or, if it's gone, a temporary one `.claude/worktrees/mama-<slug>-test` on the branch, removed after. Shared services under `flock <store>/.heavy.lock`. Report pass/fail with the command.
4. **Record** in `<slug>/tests.md` (not log.md — a closed goal's log stays closed): date, scope, scenarios given, automated result, and later what the user reports.
5. **The user reports back** ("upload of 0-byte file fails"): reproduce or read the code to confirm, add it to `tests.md`, then offer the fix via `/mama change <slug>` — on a closed goal that reopens it (`rules/changes.md` step 0) so the fix gets steps, commits, log and a new close. Don't fix before they pick.

## Re-entry (resume, after compaction, new session)

Know your slug (from the conversation, the compaction summary, or `resume <slug>`; if unsure, list open goals and ask — never adopt another session's goal by guess). Read its `plan.md`, the last ~40 lines of `log.md`, and `grep '^D' log.md` for decisions in force. In the goal's worktree, check `git status` and that the branch matches the plan. Continue at the next step — don't re-plan or re-ask what the log already settled.

## Learning the user

`patterns.md` makes each goal fit the user better than the last.
- **Use** (intake, questions, planning): a learned pattern sets the recommended option, settles a question whose answer it already knows (say so in one line: "Using your usual: X"), and shapes the plan and overview. The base branch is still always asked. The user's explicit instructions and repo rules beat any pattern.
- **Learn immediately** when the user corrects your work or plan, overrides a recommendation, or states a preference: add or update a line. Don't wait for close — that's when it's fresh.
- **Learn at close**: their choices this goal (options, mode, PR), goal size, estimate vs actual.
- **Write it with** `python3 ${CLAUDE_SKILL_DIR}/scripts/learn.py seen|contra|stated|goal "<pattern>"` — it locks, counts, dates and promotes; never hand-edit. After any user decision: learn.py, or log `E learn none`.
- **Format**: one line per pattern — `<pattern> — <n>/<m> — last <date>`. Learned at ≥3 consistent observations, else it stays under "Watching". A preference the user states outright is learned at once — write `stated` instead of a count. A contradiction lowers the count; contradicted twice in a row → back to Watching or deleted.
- **Never** record secrets, client data, or repo facts (those belong in `profile.md` / `lessons.md`).

## Guards (scripts and hooks enforce these — don't work around them)

- `plan-set.py` stamps step start/end itself, warns on a step started before its deps, refuses `status=approved|running` without a mode, refuses a full goal's first approval until research is logged (`E research …`), refuses `status=done` until `close-check.py` passes (criteria evidence, step times, placeholders, Trello, metrics, patterns, profile — or `E profile none`), refuses an end time before the start, refuses size L without a number, fills the template's blank rows on `S+`/`C+`, parks ideas with `P+`, keeps the overview's Status line in sync, prints the estimate (critical path, sum, steps at once), and reminds you of the Trello start comment.
- Every write through `log.py` / `plan-set.py` / `new-goal.py` records which session worked on which goal (`~/.claude/mama/activity.log`, from `CLAUDE_CODE_SESSION_ID`). That record — not guessing — tells the hooks which goal is this session's and tells `spend.py` whose tokens count. Writing goal files any other way leaves the goal unowned and unmeasured.
- Waiting for the user is measured, so estimates calibrate on active time: `plan-set --header status=waiting` logs `E waiting` and the switch back logs `E resume` on their own; questions are `Q` lines and their answers `D … tag: user`.
- The close check also refuses commits with attribution lines or loop internals (mama, plan.md, step IDs), and the overview is checked (close and every turn) for internal IDs, file:line refs and length over one screen.
- The Stop hook measures the goal's real token spend into the plan header at every turn end (`scripts/spend.py`), and blocks once, listing every problem, when your goal: is `running` at ≥70% of its budget; says `running` without a final `E wait` line; reached a milestone (step done or blocked, status, PR or scope changed) after `overview.md` was last written; has a user decision with no learning after it; or says `done` while the close check fails. Fix what it lists, don't argue with it.

## Writing state

- Status must be honest whenever you end your turn: waiting for the user → `waiting`; stopped by request → `paused`; stuck → `blocked`. Waiting on your own background work (an agent, the gate) → status stays `running` and the last log line is `E wait <what>` (via `log.py`); its notification wakes you. A Stop hook reminds you once if you end a turn while the goal says `running` without that `wait` line.
- Record an outcome only after checking the command's exit status — never chain a state write after a command with `;` (a failed push must not be logged as pushed).
- After every step result, decision, change or commit: update `plan.md` with `python3 ${CLAUDE_SKILL_DIR}/scripts/plan-set.py <plan.md> <S3 | C1 | --header> key=value ...` (it also recomputes progress; `start=now` / `end=now` stamp the real time — never type times), and append to `log.md` with `scripts/log.py`. Unknown values are written `—`. A step with several commits lists all hashes in notes.
- Change `plan.md` and `log.md` only through `plan-set.py` (rows, header, `P+` for Parked) and `log.py` — never python, sed or Edit on them: those skip the guards, the safe write and the session record.
- `plan-set.py` keeps the overview's **Status:** line in step with the plan (`<Word> · n of m parts done[ · your detail]`). Regenerate the rest of `overview.md` when the plan is shown, after approval, at each checkpoint, on status, on any change, and at close — from plan and log, as if writing it fresh. It is the user's only window: short, plain, current.
