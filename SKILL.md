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

| Input                            | Do                                                                                                                   |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `status` (or "status?" mid-run)  | In a new session, read state first (Re-entry, read-only). Print: goal status (if `waiting`: what the user should look at), progress line, running steps (step, started HH:MM, ETA = start + est), estimated finish (now + the `likely … left` from `scripts/estimate.py <plan.md>`, which is scaled by past goals), blockers, next. Regenerate `overview.md` only if the goal is this session's — another session's goal stays read-only. |
| `ask [<slug>] <question>`       | Answer a question about a goal's work, during or after it — read `rules/ask-test.md` → "Asking about the work". |
| `test [<slug>] [<what>]`        | Help the user test what a goal built, and check it ourselves — read `rules/ask-test.md` → "Testing the work". |
| `fix [<slug>] [<what>]`         | Fix what a goal found (a test run, review or research): a new `fix` goal whose input is that goal's findings — its report, `F` lines and Parked list (no slug: this session's last goal). Start it with `new-goal.py <store> <slug> fix "findings of <source slug>"`, verify the findings against the code in parallel (a read-only agent per area), then questions (first: which findings to fix) → plan as usual. Don't write to the source goal's files. |
| `change [<slug>] <what>` (or "change the plan: …" mid-run) | Modify the plan of an existing goal — add, alter or drop scope, tests or deliverables. Read `rules/changes.md` → "Running a change" and follow it. No slug: this session's goal; none, or several open → list them and ask. |
| "go" / "continue" at a checkpoint | Set goal status `running` with `plan-set.py` (it logs `E resume` itself), continue the loop.                         |
| `pause`                          | Record state, set status `paused`, stop.                                                                              |
| `abort`                          | Record state, set status `aborted`, clean up what the run created (`rules/delivery.md` Close §3), stop. Keep tracking files. |
| `list`                           | Run `scripts/list.py <store>` and show its output (one line per goal: slug, status, progress, worktree).              |
| `resume <slug>`                  | Re-entry (below), continue. With no slug: list open goals and ask which.                                             |
| `quick <task>`                   | Quick mode (below).                                                                                                   |
| anything else                    | New goal. Other open goals are fine — each runs isolated (see "Several goals at once").                             |

## Where things live

**Store** = `<main checkout>/.claude/mama/`, where main checkout = `$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")` (git < 2.31: drop `--path-format=absolute` and resolve the path from the cwd) — the same store from any worktree. On first use, append `.claude/mama/` and `.claude/worktrees/` to `info/exclude` under `git rev-parse --git-common-dir` (a linked worktree has a `.git` file, not a folder) so neither reaches a commit.

- `profile.md` — repo facts: commands, conventions, things never to do. Create on first use from the repo's rules; reuse after.
- `lessons.md` — what past goals taught. Read during research if it exists; created at the first close. Append only.
- `<slug>/overview.md` — **for the user.** Plain language, no IDs or jargon.
- `<slug>/plan.md` — **for you.** Source of truth for criteria, steps, progress.
- `<slug>/log.md` — **for you.** Append-only: questions, decisions, findings, changes, events.
- `<slug>/tests.md` — what `/mama test` gave the user and what they reported (created on first use).

**User-level**, all repos: `~/.claude/mama/patterns.md` — how this user works (choices, corrections, preferences, estimate accuracy). Created from `templates/patterns.md` on first use. It's about the user, so it's written in plain language they can read and edit; their edits win.

Skill files (`templates/`, `rules/`, `scripts/`) live in `${CLAUDE_SKILL_DIR}`; read each only when the flow points to it. Run every script through the launcher: `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/<name>.py …` — short mentions like `scripts/lock.py` mean the same. Slug: 2-5 kebab-case words from the goal.

### Several goals at once

The user may run several goals in parallel sessions. Each goal is isolated:
- **Its own tracking folder** `<store>/<slug>/`; a session only ever writes its own goal's files. Remember your slug — it's in every re-entry.
- **Its own worktree** for build/fix/mixed goals (and research goals that commit a deliverable): `<main checkout>/.claude/worktrees/mama-<slug>/` on the goal's branch, recorded in the plan header. All code work, commands and agents for the goal happen there — prefix shell commands with `cd <worktree> &&` and use absolute paths for file tools. Research-only goals work read-only in the main checkout. Never switch branches in the main checkout; it belongs to the user.
- **Shared, so coordinated**:
  - Shared files (`profile.md`, `lessons.md`, `info/exclude`, `patterns.md`): create only if absent (`set -C`), add exclude lines only if missing, and append/edit under `scripts/lock.py <store>/.shared.lock` (`~/.claude/mama/.patterns.lock` for patterns).
  - Verifies that touch shared services (database, Redis), every full gate, and heavy runs (build, e2e) go under `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/lock.py <store>/.heavy.lock <cmd>` (wrap shell syntax in `bash -c '…'`) so goals don't collide.
  - The agent limit (`scripts/resources.py <ready> <store> <own slug>`) subtracts other goals' running steps.
  - `git fetch` and `git push` run as `git -C <main checkout> ...` — refs are shared with the worktree, and it works for any remote URL.

**Same branch, two goals:** a branch can be checked out only once, so a goal that targets a branch another open goal works on shares that goal's worktree and runs after it, never in parallel with it. Say in both overviews that one push carries both goals' commits, and never push one goal's commits while the other has uncommitted work in the tree.

**Times and IDs:** every `log.md` line goes through `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/log.py <log.md> <E|D|F|Q> "<text>"` — it stamps the real time and the next ID, so never type either by hand. Overview timeline times come from those log lines.

**Deliverables** the user asks for (docs, reports, data) are `document` steps with an output path (user's choice; default `docs/`), never inside `.claude/mama/`, written for their reader with no loop state in them. Link them in overview by repo-relative path.

## Flow

### 1. Intake — create the goal on disk first

1. Classify the goal: **build** (changes code), **fix** (a bug), **research** (findings only), **mixed** (research, then build). Ambiguous → it's part of the questions.
2. Normalize the input — text as given · file/md: read fully · Trello: card, checklist, comments · GitHub PR/issue: `gh` · "research X".
3. Immediately run `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/new-goal.py <store> <slug> <type> "<source>"` — it creates the folder (suffixing a taken slug), a clean `plan.md` (status `planning`, real start time), `overview.md` and `log.md` with E1, and prints the overview rules. Use the slug it prints. Never copy templates by hand. The goal now survives a compaction, and the user can already read the overview.

### 2. Research

Read-only. Read `rules/research.md` and follow it: parallel lens agents map every branch of the work and every case before any question. Log `E research: <n> findings, <m> cases, <k> open` (or `E research none: <why>` for a goal that needs none) — plan approval is refused without it.

### 3. Questions

Read `rules/questions.md`, then ask: specific, multiple choice with a recommended option, covering the expectations checklist and every open case from research. Then the **playback**: show what the user will get as concrete examples, to confirm or correct before planning.

### 4. Plan

Read `rules/planning.md`. Fill `plan.md` with `plan-set.py` (`S+` / `C+` fill the template's blank first rows, then add more; `--header` for the rest), validate, show one compact table (step · kind · depends on · verify) with the criteria, then ask approval with AskUserQuestion: approve · checkpointed (recommended) / approve · autonomous / change something. Never leave mode unanswered. Set status, mode and budget size in one call (`--header status=approved mode=… budget=M`). Then set up the branch and worktree if the goal touches git (`rules/delivery.md`).

### 5. Loop

Read `rules/loop.md`. Dev → verify → fix until every criterion has evidence, then **hunt for bugs** (`/code-review` + an expectations check) → fix → hunt again, until a round finds no real bug (cap 4 rounds, then ask). Commit each stable step. Interruptions and changes: `rules/changes.md`.

### 6. Deliver & close

Read `rules/delivery.md`. Merge latest base, push, PR per the user's choice. Final report in `overview.md`, lessons to `lessons.md`, clean up.

## Quick mode

For small tasks (≈ under 30 minutes, one area). Intake with `new-goal.py … --quick`: mode is preset, the overview is 3 lines (task, status, done means / result). Skip research agents, `profile.md`, `lessons.md` and patterns bookkeeping — the close check doesn't ask for them. Ask the questions first — only base branch, and PR choice if code changes — then show the plan, 1-3 steps of one line each, for approval; proceed on approval. Same loop, commit and push rules, with one light bug-hunt round (`/code-review low`) on a code change. If it grows past that, say so and offer to continue as a full goal (set `mode` to checkpointed/autonomous; the close check then asks for everything).

## Re-entry (resume, after compaction, new session)

Know your slug (from the conversation, the compaction summary, or `resume <slug>`). A goal is this session's if `activity.log` recorded this session writing to it (in any store); hook event lines such as `E compaction` aren't writes. `resume <slug>` — the user naming it — adopts that goal even if another or an earlier session wrote it; your next write records it as this session's. Only guessing is forbidden: if unsure, list open goals and ask — never pick another session's goal yourself. Read its `plan.md`, the last ~40 lines of `log.md`, and `grep '^D' log.md` for decisions in force. In the goal's worktree, check `git status` and that the branch matches the plan. Continue at the next step — don't re-plan or re-ask what the log already settled.

## Learning the user

`patterns.md` makes each goal fit the user better than the last.
- **Use** (intake, questions, planning): a learned pattern sets the recommended option, settles a question whose answer it already knows (say so in one line: "Using your usual: X"), and shapes the plan and overview. The base branch is still always asked. The user's explicit instructions and repo rules beat any pattern.
- **Learn immediately** when the user corrects your work or plan, overrides a recommendation, or states a preference: add or update a line. Don't wait for close — that's when it's fresh.
- **Learn at close**: their choices this goal (options, mode, PR), goal size, estimate vs actual.
- **Write it with** `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/learn.py seen|contra|stated|goal "<pattern>"` — it locks, counts, dates and promotes; never hand-edit. After any user decision: learn.py, or log `E learn none`.
- **Format**: one line per pattern — `<pattern> — <n>/<m> — last <date>`. Learned at ≥3 consistent observations, else it stays under "Watching". A preference the user states outright is learned at once — write `stated` instead of a count. A contradiction lowers the count; two contradictions in a row move a learned line back to Watching; one contradicted down to 0 is deleted.
- **Never** record secrets, client data, or repo facts (those belong in `profile.md` / `lessons.md`).

## Guards (scripts and hooks enforce these — don't work around them)

- `plan-set.py` stamps step start/end itself, warns on a step started before its deps, refuses `status=approved|running` without a mode, refuses a full goal's first approval until research, the expectations checklist and the playback are logged (`E research …`, `E expectations …`, `E playback …`), refuses `status=done` until `close-check.py` passes (criteria evidence, step times, placeholders, Trello, metrics, patterns, profile — or `E profile none` — and, for code goals, a last bug-hunt round with 0 real bugs), refuses a typed end time before the start (a step that crossed midnight: `end=now`), keeps `budget` as `~<n>k / S|M|L <n>k|M` (e.g. `L 800k`, `L 1.5M`) and refuses a full goal's first approval without the size (`budget=…` in the same call), allows `pr` only as `ask-at-end | auto | none | declined | <url>`, fills the template's blank rows on `S+`/`C+`, parks ideas with `P+`, keeps the overview's Status line in sync, prints the estimate (critical path, sum, steps at once), and reminds you of the Trello start comment.
- Every write through `log.py` / `plan-set.py` / `new-goal.py` records which session worked on which goal (`~/.claude/mama/activity.log`, from `CLAUDE_CODE_SESSION_ID`). That record — not guessing — tells the hooks which goal is this session's (a goal no record ties to this session is never claimed) and tells `spend.py` whose tokens count: it counts the sessions recorded there, plus a transcript scan only for goals started before `activity.log` existed. Writes need `CLAUDE_CODE_SESSION_ID` (Claude Code sets it); without it the scripts warn and record nothing. Writing goal files any other way leaves the goal unowned and unmeasured.
- Waiting for the user is measured, so estimates calibrate on active time: `plan-set --header status=waiting` logs `E waiting` and the switch back logs `E resume` on their own; questions are `Q` lines and their answers `D … tag: user`.
- The close check also refuses this goal's commits (on the branch since `started:`, also when base == branch) with attribution lines or loop internals (mama, plan.md, or step/criterion references like "step S3" / "criterion C2" — bare IDs aren't refused), and the overview is checked (close and every turn) for this goal's own step/log IDs, file:line refs (URLs and host:port don't count) and length over one screen.
- The Stop hook measures the goal's real token spend into the plan header at every turn end (`scripts/spend.py`), and blocks, listing every problem, when your goal: is `running` at ≥70% of its budget (autonomous mode: raise it yourself within 2× of the approved ceiling and go on); says `running` without a final `E dispatch …` or `E wait …` line; reached a milestone (a ★ step done, a step blocked, status, PR or scope changed) after `overview.md` was last written; has a user decision with no learning after it (not in quick mode); or says `done` while the close check fails. It blocks when a problem appears or the list changes, never twice for an identical list. Fix what it lists, don't argue with it. Hook failures never block; they go to `~/.claude/mama/hook-errors.log`.

## Writing state

- Status must be honest whenever you end your turn: waiting for the user → `waiting`; stopped by request → `paused`; stuck → `blocked`. Waiting on your own background work (an agent, the gate) → status stays `running` and the last log line is `E dispatch <steps>` or `E wait <what>` (via `log.py`) — one line, not both; its notification wakes you. The Stop hook reminds you if you end a turn while the goal says `running` without one.
- Record an outcome only after checking the command's exit status — never chain a state write after a command with `;` (a failed push must not be logged as pushed).
- After every step result, decision, change or commit: update `plan.md` with `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/plan-set.py <plan.md> <S3 | C1 | --header> key=value ...` (it also recomputes progress; `start=now` / `end=now` stamp the real time — never type times), and append to `log.md` with `scripts/log.py`. Unknown values are written `—`. A step with several commits lists all hashes in notes.
- Change `plan.md` and `log.md` only through `plan-set.py` (rows, header, `P+` for Parked) and `log.py` — never python, sed or Edit on them: those skip the guards, the safe write and the session record.
- `plan-set.py` keeps the overview's **Status:** line in step with the plan (`<Word> · n of m parts done[ · your detail]`). Regenerate the rest of `overview.md` when the plan is shown, after approval, at each checkpoint, on status, on any change, and at close — from plan and log, as if writing it fresh. It is the user's only window: short, plain, current.
