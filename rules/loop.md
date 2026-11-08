# The loop

Run until every criterion has evidence. Builder and checker are kept apart where it matters, because a worker grading its own judgement passes things that don't work. Where the proof is a command result (tests, typecheck), the command is the independent judge.

## Per step, by kind

| Kind     | Worker                                                    | Proof                                                                                   | Output                        |
| -------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------- |
| build    | you or a dev agent (see sizing)                           | step verify passes + related tests; for judgement-heavy steps a test agent also checks the tests really exercise the criterion | commit                        |
| fix      | same; first write a test that reproduces the bug          | the test failed before the fix and passes after; related tests pass                    | commit                        |
| research | you or read-only agents in parallel                       | findings you read yourself are `verified`; agent-reported findings are spot-checked by you; a checker agent only for claims going into a deliverable | findings in log / deliverable |
| document | you or a writer agent                                     | reader check: fits audience, meets criteria, every factual claim sourced, no loop state | file at chosen path           |
| decide   | you                                                       | user answer, or decision rules applied and logged                                        | decision line                 |
| release  | you                                                       | `rules/delivery.md`                                                                      | push / PR                     |

## Sizing: who does the work

- **Small** — mechanical, a few files, proof is a command (≈ under 50 changed lines): do it in the main thread; the verify command is the proof. Read your diff once before committing.
- **Large or judgement-heavy** — design choices, many files, or a proof that needs judgement ("does this test cover the criterion?"): dev agent builds, a separate test agent checks.
- Claims in a deliverable (a doc someone will read) get the citation checker — a wrong citation misleads more than a missing one. Internal findings don't: you read the code, that's the proof.

## Cycle

1. **Dispatch** ready steps (deps done, owners free) up to the limit from `${CLAUDE_SKILL_DIR}/scripts/resources.sh <ready>`. Status `running`; log `dispatch`.
2. **Self-check**: the worker runs the cheapest checks on touched files (format, typecheck) before handing off.
3. **Verify**: run the step's verify (and the checker, if the step needs one). Status `testing`.
4. **Pass** → record evidence and covered files in notes, status `done`, commit (`rules/delivery.md`), log `pass` + `commit`.
5. **Fail** → focused fix: the failing output (trimmed), the file, the expected behaviour. Status `fixing`, att +1. Trivial fixes (a checker's nit, a typo) are made inline and re-proven by the command only — no new checker round.
6. **Flaky?** A failure that doesn't reproduce on one rerun is logged and not counted.
7. **Cap**: after 2 failed fix rounds, rethink — re-read decisions in force, check `lessons.md`, consider another approach. Same error twice = rethink, never a blind retry. Third failure → `blocked`, reason in log and overview "Needs your input"; continue other steps.

**Pipeline**: verify step A while work on B continues; no phase barriers. **Skip redundant verifies**: a done step whose covered files haven't changed isn't re-run.

## Milestones and checkpoints

- Milestones are steps marked ★ in `plan.md` (`rules/planning.md`).
- At each ★: a **drift check** (recent work vs Goal and non-goals; correct and log if off).
- **Checkpointed mode** pauses at each ★ and always once before delivery (before the push / before the deliverable is final): let running steps finish, dispatch nothing new, set goal status `waiting`, regenerate overview with what's ready to look at, log `checkpoint`, wait for the user's go. Autonomous: log and continue.
- **Before delivery**: run the full gate, then confirm every criterion has evidence. If any criterion's proof involves judgement (behaviour read from a diff, a doc's accuracy, "the test really covers X"), one independent checker agent reviews those criteria — catches "claimed done, isn't". If every criterion is proven by a command result, the full gate is the independent check; no agent. A checker that already covered all criteria in the final step counts.
- Order: pre-delivery checks first, then the pre-delivery checkpoint, so the user sees the result.

## Guards

- **Scope**: anything outside the goal becomes a `parked` line, not work. Existing code that breaks a repo rule is out of scope too — new code follows the rules; old violations are parked unless the goal is about them.
- **Budget**: track approximate spend (subagent token counts from task notifications + rough main-thread estimate) in the plan header. Pause and ask (continue / cut scope / stop) at ~70% of the size's ceiling: S 140k, M 700k, L — set a number at planning.
- **Stop at done**: all criteria evidenced → deliver. No polish beyond the criteria.

## Interruptions

User messages mid-run, sorted immediately:
- question → answer; loop continues
- new requirement / test change / goal change → `rules/changes.md`
- stop / pause → record state, stop now
- side idea → `parked`, acknowledge in one line

## Environment

Before a verify that needs services (DB, Redis, a running app), check them with the command in `profile.md`. Down → report and wait. Run such verifies, and heavy ones, under `flock <store>/.heavy.lock` — other goals may be using the same services. Never start, stop, restart or reseed shared services or running dev stacks.
