# The loop

Keep builder and checker apart where judgement is involved; where the proof is a command result (tests, typecheck), the command is the judge.

## Per step, by kind

Worker → proof → output:
- **build**: you or a dev agent (see sizing) → step verify + related tests pass (judgement-heavy: see sizing) → commit.
- **fix**: same; first a test that reproduces the bug → it failed before the fix, passes after; related tests pass → commit.
- **research**: you or read-only agents in parallel → findings you read yourself are `verified`; spot-check agent-reported ones; the report marks confirmed-by-you vs. reviewer-only (never call reviewer-only verified); a citation checker only for claims going into a deliverable (internal findings: you read the code, that's the proof) → findings in log / deliverable.
- **document**: you or a writer agent → reader check: fits audience, meets criteria, every factual claim sourced, no loop state → file at chosen path.
- **hunt**: see Bug hunt → a round with 0 real bugs → hunt line in log.
- **decide**: you → user answer, or decision rules applied and logged → decision line.
- **release**: you → `rules/delivery.md` → push / PR.

## Sizing: who does the work

- **Tiny** (a handful of tool calls: one-line fix, rename, config value): main thread; the verify command is the proof. Read your diff once before committing.
- **Everything else**, mechanical included, gets its own agent, parallel with the other ready steps (`rules/agents.md`).
- **Judgement-heavy** (design choices, or a proof like "does this test cover the criterion?"): a dev agent builds; a separate test agent checks the tests really exercise the criterion, and can write them from the criterion while the build runs.

## Cycle

1. **Dispatch** every ready step (deps passed, not just started; owners free) at once, up to the limits from `scripts/resources.py <ready> <store> <slug>`, as background Agent calls in one message. Status `running`; log one `dispatch` line naming them all. Refill as each returns.
2. **Self-check**: the worker runs the cheapest checks on touched files (format, typecheck) before handing off.
3. **Verify**: run the step's verify (and checker, if needed) while other agents work; independent verifies run as parallel background commands, heavy ones queue on the lock. Status `testing`.
4. **Pass** → evidence and covered files in notes, status `done`, `end=now`, commit (`rules/delivery.md`), log `pass` + `commit`. If this completes a criterion's proof, fill its `evidence` cell (`plan-set.py <plan> C2 "evidence=..."`); pre-delivery reads evidence from the Criteria table.
5. **Fail** → focused fix: trimmed failing output, the file, expected behaviour; failures in different areas get parallel fix agents. Status `fixing` (plan-set counts rounds in `att`). Trivial fixes (a checker's nit, a typo): inline, re-proven by the command only.
6. **Flaky?** A failure that doesn't reproduce on one rerun is logged, not counted.
7. **Cap**: after 2 failed fix rounds, or the same error twice, rethink (never retry blindly): re-read decisions in force, check `lessons.md`, try another approach. Third failure → `blocked`, reason in log and overview "Needs your input"; continue other steps.

**Pipeline**: verify A while B is worked on; no phase barriers. Don't re-verify a done step whose covered files haven't changed.

## Bug hunt — until a round is clean

Starts when every build and fix step is done, before the pre-delivery gate; covers the goal's whole change.

**One round** (k = 1, 2, …), both in parallel:
- **Review**: built-in `/code-review high <goal branch>` (Skill tool) on the goal's changes since its base. From round 2: only commits since the last round, plus the code they call.
- **Expectations check**: one read-only agent gets the confirmed playback examples, the criteria, the `case:` lines and the diff; for each: handled? where (file:line)? proven by which test? It returns only the gaps.

**Triage every finding before fixing it**: reproduce it with a failing test or a command. Not reproducible, or out of scope = not a bug: log why (`F … not a bug: …`), park out-of-scope ones. A reproduced finding is **real** only when a user hits it, data is lost, wrong or exposed, a promised example fails, or a test the repo or a criterion requires is missing (fix: the test, plus code if it fails). Anything else that reproduces (robustness past what was promised, unlikely edge, naming, dead code, cleanup) is **minor**: one `P+` parked line each for the report's follow-ups, fixed only if it's a line or two inside a fix step that runs anyway. Minor findings never keep the hunt going.

**Fix**: each real bug becomes a fix step (`plan-set.py <plan> S+ kind=fix …`), test first, through the normal cycle, parallel by area. Log each round once, when it ends: `E hunt <k>: <n> found, <r> real, <x> fixed, <m> minor — /code-review <level> + expectations check`. Progress in between avoids `hunt <k>:` (e.g. `fixes for round 3 verified`). A test-suite run is verify, not a hunt; the close check refuses a round that doesn't name `/code-review`.

**Stop rule**: a round with **0 real** bugs ends the hunt; while rounds find fewer real bugs, go again. **Not converging** (a round finds 2+ real bugs, at least as many as the one before): stop fixing, set status `waiting`, ask: simplify the part that keeps breaking (recommended) / fix and hunt again / deliver with the known issues listed. The Stop hook flags it. After 4 rounds that still find some: status `waiting`, ask: hunt again / deliver with the known issues listed in the report / stop. Log "deliver" as `D deliver with known issues … (tag: user)`. The close check refuses a code goal whose last hunt wasn't clean, unless that decision follows it.

**Before the push**: hunt what will be delivered; the close check refuses a goal whose last push precedes its last hunt (push again once clean, and log it).

**Quick goals**: one `/code-review low` round, no expectations agent; fix what it confirms, don't repeat. **No code changed** (research, docs only): log `E hunt none: <why>`.

## Milestones and checkpoints

- Milestones are steps marked ★ in `plan.md` (`rules/planning.md`). At each ★: a **drift check** (recent work vs Goal and non-goals; correct and log if off).
- **Checkpointed mode** pauses at each ★ and once before delivery (before the push / the deliverable is final): let running steps finish, dispatch nothing new, status `waiting`, regenerate overview with what's ready to look at, log `checkpoint`, wait for the user's go. Autonomous: log and continue.
- **Before delivery**: hunt clean, full gate run, every criterion evidenced. Criteria proven by judgement (behaviour read from a diff, a doc's accuracy, "the test really covers X") get one independent checker agent, unless one already covered all criteria in the final step. If all are proven by command results, the full gate is the check.
- Order: pre-delivery checks, then the pre-delivery checkpoint, so the user sees the result.

## Guards

- **Scope**: anything outside the goal becomes a `parked` line (`plan-set.py <plan> P+ "text=…"`), not work. That includes existing code breaking a repo rule, unless the goal is about it; new code follows the rules.
- **Budget**: mandatory; measured, not estimated. The Stop hook writes real spend (main thread + this goal's subagents, from the transcripts) into the plan header at every turn end and blocks at 70%. Read it after every step. At ~70% of the size's ceiling (S 210k, M 700k, L as set at planning):
  - **autonomous**, what's left is in the approved plan, and the new ceiling stays within 2× of the header's `approved:` size → raise it yourself, log `D budget raised to … (tag: auto)`, note it in the overview, continue. plan-set refuses past 2×; only `D budget … (tag: user)` makes a new size the approved one.
  - otherwise (checkpointed, new scope, or past 2×) → stop dispatching, status `waiting`, ask: continue / cut scope / stop. On continue, raise the ceiling once (`--header budget='L <n>k|M'`, e.g. `L 1.5M`) to measured spend + remaining estimate + 30%, never in small steps that re-ask every turn.
- **Stop at done**: all criteria evidenced → deliver. No polish beyond the criteria.

## Interruptions

Mid-run user messages, sorted at once:
- question → answer; loop continues
- new requirement / test change / goal change → `rules/changes.md`
- stop / pause → record state, stop now
- side idea → `parked`, acknowledge in one line

## Environment

Before a verify that needs services (DB, Redis, a running app), check them with the command in `profile.md`; down → report and wait. Run such verifies, and heavy ones, under `scripts/lock.py <store>/.heavy.lock` (other goals share the services). Never start, stop, restart or reseed them.
