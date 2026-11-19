# Questions

Ask only what the code, docs, lessons or profile can't answer and whose answer changes the work.

## Before asking

- Every research lens has returned (`rules/research.md`). Cite findings: "Courses use soft delete (store.go:88). Should lessons follow that?" — not "How should deletion work?"
- Thing **already exists** → lead with that: reuse, extend, or build anyway?
- **Value filter**: every option leads to the same work → no question; decide and log it (tag `inferred`).
- **Patterns** settle what they answer (SKILL.md → Learning the user): log it (tag `user`, "from patterns").
- **Cover the case map**: walk every `case:` line. Settled by code, precedent, input or patterns → decide, log (`inferred`), list product-facing ones in overview Key decisions. Open and changes the work → a question; several small ones in one area → one question with recommended handling for all.
- **Pre-mortem**: the likely reasons the goal would fail are your best questions.

## Database changes — settle these first

When research found any database change (`F … db:`), discuss the whole design **before** other questions and any plan, in a message of its own with no other question in it: the other answers depend on it.

1. **Propose it whole**, in one AskUserQuestion with a preview: each table and column (type, null, default), keys, foreign keys (on delete), indexes, constraints, enums; existing rows (default, backfill, moved or deleted); the migration (one file per repo rules and naming, reversible or not, locks on large tables); its readers and writers (queries, API shape, caches). Follow and cite repo precedent.
2. **Suggest, don't just ask**: recommend one design and offer the real alternatives (e.g. column vs new table, soft vs hard delete, enum vs lookup table), each with a one-line trade-off. Options: recommended design (Recommended) · each alternative · change something.
3. **Discuss until agreed.** Fold questions and corrections into a revised proposal and show it again until the user approves.

Each agreed part → `D … db: <decision> (tag: user)`. Then log `E db: agreed <n> changes`; no database change → `E db: none — <why>`. Plan approval of a build, fix or mixed goal is refused without it; the playback comes after it. A different schema later, or a database change found mid-run, goes back to the user the same way (`D … db:` again) before any step uses it.

## Expectations — what "done right" means to the user

Walk this checklist: settle each point from input, code, precedent or patterns with a cited `D … (tag: inferred)`, else ask it. An inapplicable point gets one word in the log ("n/a: no UI"); never fold points into a vague "anything else?".

1. **Outcome** — what the user sees, gets or can do, in their words; what they check first.
2. **People & access** — who uses it, roles or permissions, what others must not see or do.
3. **Behaviour & edge cases** — open `case:` lines: empty, limits, errors, concurrency, undo, old data.
4. **Look & copy** — design or screen to follow, wording, states (loading, empty, error), what must match an existing screen.
5. **Data & interfaces** — the agreed design ("Database changes"), shapes, names, API contract, existing-client compatibility.
6. **Speed & scale** — data sizes and response times that must hold; "no worse than today" counts.
7. **Must not change** — behaviour, screens, APIs or other teams' work to keep as is.
8. **Proof** — tests or checks that prove it; what the user tries by hand.
9. **Delivery** — base branch, PR, where deliverables go ("Always asked").

Research goals use what fits: outcome = question answered and depth, people = readers, proof = how claims are sourced, delivery = format and path.

After the batch, log `E expectations: <n> settled, <m> asked` — plan approval is refused without it.

## Playback — confirm before planning

Show what the user will get, in one AskUserQuestion with a preview:

- 4–8 **concrete examples**, each observable: "A teacher with no files opens Storage → sees 'No files yet' and an Upload button." Cover the main path, the edge cases the user cares about, and one per must-not-change.
- **Not included**: non-goals, one line each.
- Options: "Yes, that's what I expect (Recommended)" / "Change something" (they type what).

Corrections → `D … (tag: user)` lines and changed examples; show it again only if one changed the outcome. Log `E playback: confirmed` or `E playback: corrected <n>`; plan approval is refused without it. Confirmed examples become the criteria (`rules/planning.md`) and what the bug hunt checks (`rules/loop.md`).

Quick goals skip the checklist log; their playback is one line ("You'll get: …" + not included), one more option set in the quick questions' AskUserQuestion — most needed for a page, document or review, where a wrong picture costs a redo.

Standard goals have no database change (one makes them full): log `E db: none — <why>`, ask everything in one batch, then the playback — a second batch only if an answer opens a new case.

## Always asked

| Goal | Must ask |
| --- | --- |
| build / fix / mixed | **Base branch** — options: repo's default branch (recommended), other relevant branches (current, recent), no duplicates, free text allowed; continuing an unmerged feature branch → offer "commit on <branch> itself" and "new branch off <branch>". Never assumed. **PR** — ask me at the end (recommended) / open automatically / no PR → header `pr=ask-at-end | auto | none`. No remote (`git remote` empty): don't ask; set `pr=none`, commit only, say so. |
| research with a file deliverable | **Commit it?** — leave uncommitted (recommended) / commit on a branch (then base branch + PR). Plus scope, depth, output path. |
| research, findings only | Scope, depth. No git questions. |
| quick | Base branch; PR choice if it changes code. |

**After the answers:** each override of a recommendation or stated preference → `scripts/learn.py seen|stated "<pattern>"` before planning; nothing new → log `E learn none`. The Stop hook blocks until one follows the last `tag: user` decision.

**Mode** is asked only with plan approval (SKILL.md step 4), never in the question batch; checkpointed is recommended for a repo's first goals.

## How to ask

- AskUserQuestion: ≤4 questions per screen, 2-4 options, recommended first with "(Recommended)", one-line trade-off each.
- A Recommended option that depends on code is checked feasible first (file:line or a quick probe); otherwise its description says "unproven".
- Broad → specific, each round narrowed by answers. Ask every open checklist point, even in a third round; more than ~3 rounds → propose splitting the goal. Each option names its concrete effect ("the list shows deleted files greyed out"), never an abstract label.
- Log each question as a `Q` line before asking.

## After answers

- Each answer → `D` line, tag `user`.
- Unanswered and non-blocking → `D` line with your recommended default, tag `assumed`, shown in overview "Needs your input"; confirm it before a step that depends on it starts.
- Answers that will recur (test style, naming) → `profile.md`, never asked again.

## Mid-run

Ask only for one-way choices (`rules/planning.md` → Reversibility), a real goal change, or a blocker you can't route around. Otherwise decide, log, and flag in overview "Key decisions" what the user may want to review.

Autonomous with agents running: never block on AskUserQuestion. Decide reversible things (`D … (tag: assumed)`, flagged in overview), keep verifying and committing, and ask only at a point where status goes `waiting`.
