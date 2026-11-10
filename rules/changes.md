# Changes mid-goal

Goals, tests and wishes change. Handle each change so finished work isn't lost and nothing silently contradicts an earlier decision.

## Running a change (`/mama change`)

1. **Re-enter** the goal if this session isn't already in it (SKILL.md → Re-entry). Never change another session's open goal unless the user named its slug.
2. **Hold:** dispatch nothing new. A running agent whose step the change affects → stop it (TaskStop) and set that step back to `todo`; unaffected agents keep going.
3. **Unclear request** → one AskUserQuestion batch (`rules/questions.md`), nothing more.
4. **Draft the diff** — classify each part (goal / test / deliverable, sections below) and list: steps added, altered, made obsolete; criteria added or changed; decisions to revisit; effect on time and budget size.
5. **Approve:** show the diff as one compact table (change · step · effect). Material change (new area, bigger size, a done step reopened, a decision reversed) → AskUserQuestion: apply (recommended) / change something. Small → apply and say so in one line.
6. **Apply** only with `plan-set.py`: new rows `S+` / `C+` (next id, verify required), altered rows `S3 key=…`, dropped work `status=obsolete "notes=dropped: <why>"` — never delete rows or rewrite done steps. Size grew → `--header budget='… / M'`.
7. **Record:** `log.py E "change: <what> — +S9,S10; S4 obsolete; D3 revisit"`, plus a `D` line (`tag: user`) per user choice, then `learn.py` or `E learn none`.
8. **Resume:** regenerate overview.md (Goal section current, "What changed along the way" gets one line), restore the status the goal had (running → continue the loop at the next ready step; waiting/paused → stay).

## Goal change

1. Diff old goal vs new: what's added, removed, altered.
2. Steps: no longer needed → `obsolete` (never delete rows); new work → new steps; done work that still fits → keep.
3. Decisions: re-check each one that depended on the old goal → mark `active` / `revisit` / `obsolete`.
4. Done criteria: update; criteria removed keep their row with status note.
5. Log one `change` event: what changed and the impact (`+S9,S10; S4 obsolete; D3 revisit`).
6. Update the Goal section of overview (plain, current-state wording) and "What changed along the way".
7. Scope moved materially (new area, much bigger) → re-validate and show the plan table again for approval. Small → continue and tell the user in one line.

**New behaviour vs. reopened step**: a change that adds or alters behaviour → a new step (history stays readable, done work stays done). A change only to how a step is proven → reopen that step (below).

**Ambiguity introduced by a change** (e.g. "add an ellipsis" — does it count toward the limit?): apply the decision rules in `rules/planning.md`; reversible → decide, log, flag in overview "Key decisions" for review.

## Test change ("change these tests", new proof required)

- Update the affected steps' verify and the criteria they prove.
- Rerun only those steps' verifies. Steps already `done` whose proof changed go back to `testing`.
- Never weaken or delete a test to make it pass unless the user explicitly asks; if a requested change looks like weakening, say so in one line and do it only on confirmation.
- A new test case can hide a behaviour choice (e.g. "combining accents" → reverse by code point, or by visible character which needs a new library). Apply the decision rules in `rules/planning.md`: reversible → decide, log, flag in overview; one-way (like a new dependency) → ask.
- A reopened step's new commit is its own commit; list both hashes in the step's notes.
- Log `change`.

## New deliverable

Add a `document` step with its output path; log `change`; continue.

## Research result changes the goal

If a research step shows the goal is wrong, impossible or much bigger than thought: stop dispatching, put it in overview "Needs your input" with your recommendation, wait.

## Base branch moved / someone else changed the branch

Detect on each commit (`git status`, `git log -1 origin/<branch>`). Unexpected commits or changes you didn't make → stop, report, wait.
