# Questions

Questions turn a vague goal into specific context. Every question must be one the code, docs, lessons or profile couldn't answer, and whose answer would change the plan.

## Before asking

- Research is done, every lens returned (`rules/research.md`). Cite what you found: "Courses use soft delete (store.go:88). Should lessons follow that?" — not "How should deletion work?"
- If research found the thing **already exists**, lead with that: reuse, extend, or build anyway?
- **Value filter**: if every option leads to the same work, drop the question; decide and log it (tag `inferred`).
- **Patterns**: a learned line in `~/.claude/mama/patterns.md` that answers a question settles it — log it (tag `user`, "from patterns") and mention it in one line. Patterns only set the recommended option for the base branch; it is still always asked.
- **Overrides teach**: when the user picks something other than your recommendation, update `patterns.md` right away.
- **Cover the case map**: walk every `case:` line. A case the code, precedent, the input or patterns settles → decide, log it (`inferred`), and list the product-facing ones in the overview's Key decisions. A case left open whose answer changes the work → a question. Several small open cases in one area → one question with the recommended handling for all of them.
- **Pre-mortem**: imagine the goal failed. The likely reasons are your most valuable questions.

## Categories (skip what doesn't apply)

1. Goal type, if ambiguous (build / fix / research / mixed)
2. Scope & non-goals
3. Behaviour & edge cases (the open cases from research)
4. Data / API shape
5. UI / design reference
6. Testing — which tests, what counts as proof
7. Constraints — repo rules, performance, security
8. Deliverables — what files, where, for whom

### Always asked

| Goal                         | Must ask                                                                                                                                                                         |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| build / fix / mixed          | **Base branch** — options: the repo's default branch (recommended), plus other relevant branches (current, recent), no duplicates; free text allowed. When the work continues an unmerged feature branch, offer "commit on <branch> itself" and "new branch off <branch>". Always asked, never assumed. **PR** — ask me at the end (recommended) / open automatically / no PR → header `pr=ask-at-end | auto | none`. |
| research with a file deliverable | **Commit it?** — leave it uncommitted for you (recommended) / commit on a branch (then base branch + PR are asked too). Plus scope, depth, output path.                       |
| research, findings only      | Scope, depth. No git questions.                                                                                                                                                  |
| quick                        | Base branch; PR choice if it changes code.                                                                                                                                       |

**After the answers:** for every answer that overrode the recommended option or stated a preference, run `scripts/learn.py seen|stated "<pattern>"` now, before planning. Nothing new → log `E learn none`. (The Stop hook blocks until one of the two follows the last `tag: user` decision.)

**Mode** (checkpointed — recommended for a repo's first goals / autonomous) is asked together with plan approval, as the approval question's options — not in the question batch, and never left unanswered.

## How to ask

- AskUserQuestion: ≤4 questions per screen, 2-4 options, recommended first with "(Recommended)", one-line trade-off each. The user can always type their own.
- Broad → specific; answers narrow the next round. Stop by ~3 rounds — needing more means the goal should be split; propose that.
- Log each question as a `Q` line before asking.

## After answers

- Each answer → `D` line, tag `user`.
- Unanswered and non-blocking → `D` line with your recommended default, tag `assumed`, shown in overview "Needs your input" until confirmed. Confirm it before any step that depends on it starts.
- Answers that will recur (test style, naming) → `profile.md`, so they're never asked again.

## Mid-run

Ask only for: one-way choices (see `rules/planning.md` → Reversibility), a real goal change, a blocker you can't route around. Everything else: decide, log, and flag it in overview "Key decisions" if the user may want to review it.
