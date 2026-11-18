# Changes mid-goal

Keep finished work; never silently contradict an earlier decision.

## Running a change (`/mama change`)

0. **Closed goal** (`done`): reopen it (`plan-set.py --header status=running`, log `E reopen: <why>`) and run the new work like the first round: new steps, close check, a new metrics line appended to `lessons.md` (append-only; close-check reads the latest), Trello comment after the push. Never change a closed goal's code off the books (e.g. only a note in `tests.md`). Removed worktree → recreate it on the branch; merged branch → a new goal instead.
1. **Re-enter** the goal if this session isn't in it (SKILL.md → Re-entry). Never change another session's open goal unless the user named its slug.
2. **Hold:** dispatch nothing new. Stop (TaskStop) a running agent whose step the change affects and set that step back to `todo`; others keep going.
3. **Unclear request** → one AskUserQuestion batch (`rules/questions.md`), nothing more.
4. **Draft the diff:** classify each part (goal / test / deliverable, below); list steps added, altered, obsolete; criteria added or changed; decisions to revisit; effect on time and budget size.
5. **Approve:** show the diff as one compact table (change · step · effect). Material (new area, bigger size, a done step reopened, a decision reversed) → AskUserQuestion: apply (recommended) / change something. Small → apply and say so in one line.
6. **Apply** only with `plan-set.py`: new rows `S+` / `C+` (next id, verify required), altered rows `S3 key=…`, dropped work `status=obsolete "notes=dropped: <why>"`. Never delete rows or rewrite done steps. Size grew → `--header budget=M` (or `budget='L <n>k|M'`); measured spend is kept.
7. **Record:** `log.py E "change: <what> — +S9,S10; S4 obsolete; D3 revisit"`, a `D` line (`tag: user`) per user choice, then `learn.py` or `E learn none`.
8. **Resume:** regenerate overview.md (Goal section current, one line in "What changed along the way"); restore the previous status (running → continue the loop at the next ready step; waiting/paused → stay).

## Fix goal (`/mama fix`)

Input: the source goal's report, `F` lines and Parked list (no slug: this session's last goal). Start with `new-goal.py <store> <slug> fix "findings of <source slug>"`, verify the findings against the code in parallel (a read-only agent per area), then questions (first: which findings to fix) → plan as usual. Never write to the source goal's files.

## Goal change

On top of the steps above:

- Done work that still fits stays; removed criteria keep their row with a status note.
- Decisions that depended on the old goal → `active` / `revisit` / `obsolete`.
- A new or altered database change → discuss it first (`rules/questions.md` → Database changes) and log the new `D … db:` lines before re-planning.
- Scope moved materially (new area, much bigger) → re-validate and show the plan table again for approval.

**New behaviour vs. reopened step**: added or altered behaviour → a new step (history stays readable, done work stays done). A change only to how a step is proven → reopen that step (below).

**Ambiguity introduced by a change**, including a behaviour choice hidden in a new test case (e.g. "add an ellipsis": does it count toward the limit? "combining accents": by code point, or by visible character, which needs a new library): use the decision rules in `rules/planning.md`. Reversible → decide, log, flag in overview "Key decisions" for review; one-way (like a new dependency) → ask.

## Test change ("change these tests", new proof required)

- Update the affected steps' verify and the criteria they prove; rerun only those verifies. `done` steps whose proof changed go back to `testing`.
- Never weaken or delete a test to make it pass unless the user explicitly asks. A requested change that looks like weakening → say so in one line; do it only on confirmation.
- A reopened step's new commit is its own commit; list both hashes in the step's notes.

## New deliverable

Add a `document` step with its output path; log `change`; continue.

## Research result changes the goal

Goal wrong, impossible or much bigger → stop dispatching, put it in overview "Needs your input" with your recommendation, wait.

## Base branch moved / someone else changed the branch

Check on each commit (`git status`, `git log -1 origin/<branch>`). Commits or changes you didn't make → stop, report, wait.
