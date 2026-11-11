# The loop

Run until every criterion has evidence. Builder and checker are kept apart where it matters, because a worker grading its own judgement passes things that don't work. Where the proof is a command result (tests, typecheck), the command is the independent judge.

## Per step, by kind

| Kind     | Worker                                                    | Proof                                                                                   | Output                        |
| -------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------- |
| build    | you or a dev agent (see sizing)                           | step verify passes + related tests; for judgement-heavy steps a test agent also checks the tests really exercise the criterion | commit                        |
| fix      | same; first write a test that reproduces the bug          | the test failed before the fix and passes after; related tests pass                    | commit                        |
| research | you or read-only agents in parallel                       | findings you read yourself are `verified`; agent-reported findings are spot-checked by you, and the report marks which were confirmed by you vs. reviewer-only — never call reviewer-only findings verified; a checker agent only for claims going into a deliverable | findings in log / deliverable |
| document | you or a writer agent                                     | reader check: fits audience, meets criteria, every factual claim sourced, no loop state | file at chosen path           |
| decide   | you                                                       | user answer, or decision rules applied and logged                                        | decision line                 |
| release  | you                                                       | `rules/delivery.md`                                                                      | push / PR                     |

## Sizing: who does the work

- **Tiny** — a handful of tool calls (a one-line fix, a rename, a config value): do it in the main thread while agents run; the verify command is the proof. Read your diff once before committing.
- **Everything else** runs in its own agent, in parallel with the other ready steps (`rules/agents.md`) — mechanical steps included, so the main thread stays free to orchestrate.
- **Judgement-heavy** — design choices or a proof that needs judgement ("does this test cover the criterion?"): a dev agent builds and a separate test agent checks; the test agent can write the tests from the criterion while the build runs.
- Claims in a deliverable (a doc someone will read) get the citation checker — a wrong citation misleads more than a missing one. Internal findings don't: you read the code, that's the proof.

## Cycle

1. **Dispatch** every ready step (deps passed — not just started; owners free) at once, up to the limits from `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/resources.py <ready> <store> <slug>` — one message, several background Agent calls. Status `running`; log one `dispatch` line naming them all. Refill as each returns: a finished step frees a slot for the next ready one.
2. **Self-check**: the worker runs the cheapest checks on touched files (format, typecheck) before handing off.
3. **Verify**: run the step's verify (and the checker, if the step needs one) while the other agents keep working; independent verifies run as parallel background commands, heavy ones queue on the lock. Status `testing`.
4. **Pass** → record evidence and covered files in notes, status `done`, `end=now`, commit (`rules/delivery.md`), log `pass` + `commit`. When this completes a criterion's proof, fill its `evidence` cell (`plan-set.py <plan> C2 "evidence=..."`) — pre-delivery reads evidence from the Criteria table, not from the overview.
5. **Fail** → focused fix: the failing output (trimmed), the file, the expected behaviour — failures in different areas get parallel fix agents. Status `fixing`, att +1. Trivial fixes (a checker's nit, a typo) are made inline and re-proven by the command only — no new checker round.
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

- **Scope**: anything outside the goal becomes a `parked` line (`plan-set.py <plan> P+ "text=…"`), not work. Existing code that breaks a repo rule is out of scope too — new code follows the rules; old violations are parked unless the goal is about them.
- **Budget**: measured, not estimated — the Stop hook writes the real spend (main thread + this goal's subagents, from the transcripts) into the plan header at every turn end and blocks at 70%. Read it after every step and compare: at ~70% of the size's ceiling (S 210k, M 700k, L the number set at planning), stop dispatching, set status `waiting`, and ask: continue / cut scope / stop. On continue, raise the ceiling once (`--header budget='L <n>k|M'`, e.g. `L 1.5M`) with headroom — measured spend + the remaining steps' estimate + 30% — never in small steps that re-ask every turn (a merge-and-feature goal once asked 7 times). This check is not optional — it's the user's guard against runaway cost.
- **Stop at done**: all criteria evidenced → deliver. No polish beyond the criteria.

## Interruptions

User messages mid-run, sorted immediately:
- question → answer; loop continues
- new requirement / test change / goal change → `rules/changes.md`
- stop / pause → record state, stop now
- side idea → `parked`, acknowledge in one line

## Environment

Before a verify that needs services (DB, Redis, a running app), check them with the command in `profile.md`. Down → report and wait. Run such verifies, and heavy ones, under `scripts/lock.py <store>/.heavy.lock` — other goals may be using the same services. Never start, stop, restart or reseed shared services or running dev stacks.
