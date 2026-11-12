# Questions

Questions turn a vague goal into specific context, so the result matches what the user expects in every way. Every question must be one the code, docs, lessons or profile couldn't answer, and whose answer would change the work.

## Before asking

- Research is done, every lens returned (`rules/research.md`). Cite what you found: "Courses use soft delete (store.go:88). Should lessons follow that?" — not "How should deletion work?"
- If research found the thing **already exists**, lead with that: reuse, extend, or build anyway?
- **Value filter**: if every option leads to the same work, drop the question; decide and log it (tag `inferred`).
- **Patterns**: a learned line in `~/.claude/mama/patterns.md` that answers a question settles it — log it (tag `user`, "from patterns") and mention it in one line. Patterns only set the recommended option for the base branch; it is still always asked.
- **Overrides teach**: when the user picks something other than your recommendation, update `patterns.md` right away.
- **Cover the case map**: walk every `case:` line. A case the code, precedent, the input or patterns settles → decide, log it (`inferred`), and list the product-facing ones in the overview's Key decisions. A case left open whose answer changes the work → a question. Several small open cases in one area → one question with the recommended handling for all of them.
- **Pre-mortem**: imagine the goal failed. The likely reasons are your most valuable questions.

## Expectations — what "done right" means to the user

The work is judged by what the user expected, not by what the plan said. Before asking, walk this checklist. Settle each point from the input, the code, precedent or patterns, citing the source and logging a `D … (tag: inferred)`. Otherwise ask it. A point that can't apply gets one word in the log ("n/a: no UI"). Don't fold points into a vague "anything else?".

1. **Outcome** — what the user sees, gets or can do when it's done, in their words. What they'll check first.
2. **People & access** — who uses it, which roles or permissions, what others must not see or do.
3. **Behaviour & edge cases** — the open `case:` lines from research: empty, limits, errors, concurrency, undo, old data.
4. **Look & copy** — the design or screen to follow, wording, states (loading, empty, error), and what must look exactly like an existing screen.
5. **Data & interfaces** — shapes, names, migrations, API contract, compatibility with existing clients.
6. **Speed & scale** — data sizes and response times that must hold; "no worse than today" counts.
7. **Must not change** — existing behaviour, screens, APIs or other teams' work that must stay as is.
8. **Proof** — which tests or checks prove it, and what the user will try by hand.
9. **Delivery** — base branch, PR, where deliverables go (see "Always asked").

Research goals use the same list where it fits: outcome = the question answered and how deep, people = who reads it, proof = how claims are sourced, delivery = format and path.

After the batch, log `E expectations: <n> settled, <m> asked` — plan approval is refused without it.

## Playback — confirm before planning

After the answers, and before the plan, show the user what they will get, so a wrong picture is caught before any work. One AskUserQuestion with a preview:

- 4–8 **concrete examples** of the finished work, each one observable: "A teacher with no files opens Storage → sees 'No files yet' and an Upload button." Cover the main path, the edge cases the user cares about, and one example of each must-not-change.
- **Not included**: the non-goals, in one line each.
- Options: "Yes, that's what I expect (Recommended)" / "Change something" (they type what).

Corrections become `D … (tag: user)` lines and change the examples. Show the playback again only if a correction changed the outcome itself. Log `E playback: confirmed` or `E playback: corrected <n>`; plan approval is refused without it. The confirmed examples become the criteria (`rules/planning.md`) and are what the bug hunt checks against (`rules/loop.md`).

Quick goals skip the checklist log and the playback; their one-line task is the example.

## Always asked

| Goal                         | Must ask                                                                                                                                                                         |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| build / fix / mixed          | **Base branch** — options: the repo's default branch (recommended), plus other relevant branches (current, recent), no duplicates; free text allowed. When the work continues an unmerged feature branch, offer "commit on <branch> itself" and "new branch off <branch>". Always asked, never assumed. **PR** — ask me at the end (recommended) / open automatically / no PR → header `pr=ask-at-end | auto | none`. No remote (`git remote` empty): don't ask PR — set `pr=none`, commit only, and say so. |
| research with a file deliverable | **Commit it?** — leave it uncommitted for you (recommended) / commit on a branch (then base branch + PR are asked too). Plus scope, depth, output path.                       |
| research, findings only      | Scope, depth. No git questions.                                                                                                                                                  |
| quick                        | Base branch; PR choice if it changes code.                                                                                                                                       |

**After the answers:** for every answer that overrode the recommended option or stated a preference, run `scripts/learn.py seen|stated "<pattern>"` now, before planning. Nothing new → log `E learn none`. (The Stop hook blocks until one of the two follows the last `tag: user` decision.)

**Mode** (checkpointed — recommended for a repo's first goals / autonomous) is asked together with plan approval, as the approval question's options — not in the question batch, and never left unanswered.

## How to ask

- AskUserQuestion: ≤4 questions per screen, 2-4 options, recommended first with "(Recommended)", one-line trade-off each. The user can always type their own.
- Broad → specific; answers narrow the next round. Ask every checklist point that is still open, even if that takes a third round; more than ~3 rounds means the goal should be split, so propose that. Each option names its concrete effect ("the list shows deleted files greyed out"), never an abstract label.
- Log each question as a `Q` line before asking.

## After answers

- Each answer → `D` line, tag `user`.
- Unanswered and non-blocking → `D` line with your recommended default, tag `assumed`, shown in overview "Needs your input" until confirmed. Confirm it before any step that depends on it starts.
- Answers that will recur (test style, naming) → `profile.md`, so they're never asked again.

## Mid-run

Ask only for: one-way choices (see `rules/planning.md` → Reversibility), a real goal change, a blocker you can't route around. Everything else: decide, log, and flag it in overview "Key decisions" if the user may want to review it.
