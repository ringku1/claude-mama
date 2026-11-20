# The loop

Keep builder and checker apart where judgement is involved; where the proof is a command result (tests, typecheck), the command is the judge.

## Per step, by kind

Worker → proof → output:
- **build**: you or a dev agent (see sizing) → step verify + related tests pass (judgement-heavy: see sizing) → commit.
- **fix**: same; first a test that reproduces the bug → it failed before the fix, passes after; related tests pass → notes carry `failing-first: <test>` or `no test: <why>` (close-check refuses a done fix step with neither) → commit.
- **research**: you or read-only agents in parallel → findings you read yourself are `verified`; spot-check agent-reported ones; the report marks confirmed-by-you vs. reviewer-only (never call reviewer-only verified); a citation checker only for claims going into a deliverable (internal findings: you read the code, that's the proof) → findings in log / deliverable.
- **document**: you or a writer agent → reader check: fits audience, meets criteria, every factual claim sourced, no loop state → file at chosen path.
- **hunt**: see Bug hunt → a clean round, or the cap round then the hunt decision → hunt line in log.
- **decide**: you → user answer, or decision rules applied and logged → decision line.
- **release**: you → `rules/delivery.md` → push / PR.

## Sizing: who does the work

- **Tiny** (a handful of tool calls: one-line fix, rename, config value): main thread — an agent costs 14–36k tokens before it starts working; the verify command is the proof. Read your diff once before committing.
- **Everything else**, mechanical included, gets its own agent, parallel with the other ready steps (`rules/agents.md`).
- **Judgement-heavy** (design choices, or a proof like "does this test cover the criterion?"): a dev agent builds; a separate test agent checks the tests really exercise the criterion, and can write them from the criterion while the build runs.

## Cycle

1. **Dispatch** every ready step (deps passed, not just started; owners free) at once, up to the limits from `scripts/resources.py <ready> <store> <slug>`, as background Agent calls in one message. Status `running`; log one `dispatch` line naming them all. Refill as each returns.
2. **Self-check**: the worker runs the cheapest checks on touched files (format, typecheck) before handing off.
3. **Verify**: run the step's verify (and checker, if needed) while other agents work; independent verifies run as parallel background commands, heavy ones queue on the lock. Status `testing`.
4. **Pass** → commit (`rules/delivery.md`), then one call: `step.py <plan> S3 done "<evidence, covered files>" --commit <sha> [--crit C2="<evidence>"]` — row status and stamps, notes, the `E` line, criterion evidence (pre-delivery reads it from the Criteria table), overview block. Same call for every status change: `running`, `testing`, `fixing "<failing line>"`, `unverified "<what didn't run>"`.
5. **Fail** → focused fix: trimmed failing output, the file, expected behaviour; failures in different areas get parallel fix agents. Status `fixing` (plan-set counts rounds in `att`). Trivial fixes (a checker's nit, a typo): inline, re-proven by the command only.
6. **Flaky?** A failure that doesn't reproduce on one rerun is logged, not counted.
7. **Cap**: after 2 failed fix rounds, or the same error twice, rethink (never retry blindly): re-read decisions in force, check `lessons.md`, try another approach. Third failure → `blocked`, reason in log and overview "Needs your input"; continue other steps.
8. **Can't run here**: a verify needing a service or tool this machine lacks (after the `profile.md` check) → status `unverified`, notes say what didn't run and where it will (e.g. CI), log it, continue other steps. A criterion it proves gets evidence `unverified: …`. At close the user must accept them: `D unverified accepted: <step ids> … (tag: user)`; close-check refuses otherwise.

**Pipeline**: verify A while B is worked on; no phase barriers. Don't re-verify a done step whose covered files haven't changed.

## Bug hunt — capped by tier

Starts when every build and fix step is done, before the pre-delivery gate; covers the goal's whole change. **Cap** (rounds): full 2, standard 1, quick 1.

**One round** (k = 1, 2, …), both in parallel:
- **Review**: built-in `/code-review <level> <goal branch>` (Skill tool). Round 1: `high` on the goal's changes since its base (quick: `low`). Round 2+: `low` on only the fix commits since the last round, plus the code they call.
- **Expectations check** (not quick): one read-only Explore agent gets the confirmed playback examples, the criteria, the `case:` lines and the diff; for each: handled? where (file:line)? proven by which test? It returns only the gaps. Round 2+: only the fixes' cases.

**Triage every finding before fixing it**: reproduce it with a failing test or a command. Not reproducible, or out of scope = not a bug: log why (`F … not a bug: …`), park out-of-scope ones. A reproduced finding is **real** only when a user hits it, data is lost, wrong or exposed, a promised example fails, or a test the repo or a criterion requires is missing (fix: the test, plus code if it fails). Anything else that reproduces (robustness past what was promised, unlikely edge, naming, dead code, cleanup) is **minor**: one `P+` parked line each for the report's follow-ups, fixed only if it's a line or two inside a fix step that runs anyway. A finding that reverses an earlier round's fix or decision is a **trade-off**, not real: `F … trade-off: <both sides>`, kept for the report. Minor and trade-off findings never extend the hunt.

**Fix**: each real bug becomes a fix step (`plan-set.py <plan> S+ kind=fix …`), test first, through the normal cycle, parallel by area; its notes carry `failing-first: <test>` (failed before, passes after) or `no test: <why>`. A fix for a rule or lint finding keeps the user-visible behaviour of the code it replaces, proven by a test. Log each round once, when it ends: `E hunt <k>: <n> found, <r> real, <x> fixed, <m> minor[, <t> trade-off] — /code-review <level> + expectations check`. Progress in between avoids `hunt <k>:` (e.g. `fixes for round 2 verified`). A test-suite run is verify, not a hunt; the close check refuses a round that doesn't name `/code-review`.

**Stop rule**: a round with **0 real** ends the hunt. Below the cap, a round with real bugs → fix them, hunt again. The **cap round** with real bugs → still fix them (failing-first), then one decision — status `waiting`, ask: deliver with the known issues listed (recommended when fixes were small) / one extra `low` round on the fixes. Log it as `D hunt: deliver with known issues … (tag: user)` or `D hunt: extra round … (tag: user)`; an extra round that again finds real bugs needs another such D line. Never run a round past the cap unasked. The Stop hook blocks once when a cap round with real bugs has no hunt decision after it; the close check refuses a code goal whose last hunt wasn't clean unless that decision follows it (an older `D deliver with known issues … (tag: user)` still counts).

**Before the push**: hunt what will be delivered; the close check refuses a goal whose last push precedes its last hunt (push again once clean, and log it). **After the push**: CI on it must be green (`rules/delivery.md` → Push); red CI is a failed verify — fix, push, check again, like any other.

**No code changed** (research, docs only): log `E hunt none: <why>`.

## Milestones and checkpoints

- Milestones are steps marked ★ in `plan.md` (`rules/planning.md`). At each ★: a **drift check** (recent work vs Goal and non-goals; correct and log if off).
- **Checkpointed mode** pauses at each ★ and once before delivery (before the push / the deliverable is final): let running steps finish, dispatch nothing new, status `waiting`, regenerate overview with what's ready to look at, log `checkpoint`, wait for the user's go. Autonomous: log and continue.
- **Before delivery**: hunt clean, full gate run, every criterion evidenced. Criteria proven by judgement (behaviour read from a diff, a doc's accuracy, "the test really covers X") get one independent checker agent, unless one already covered all criteria in the final step. If all are proven by command results, the full gate is the check.
- Order: pre-delivery checks, then the pre-delivery checkpoint, so the user sees the result.

## Guards

- **Scope**: anything outside the goal becomes a `parked` line (`plan-set.py <plan> P+ "text=…"`), not work. That includes existing code breaking a repo rule, unless the goal is about it; new code follows the rules.
- **Budget**: mandatory; measured, not estimated. At approval set `budget=` to cover the **tokens likely** plan-set prints (S 300k, M 1M, else `L <n>k|M`; smaller is refused unless `D budget … (tag: user)` accepts it) and `auto-raise=1.5x` (the user may pick 1x–2x; `1x` = always ask). The Stop hook writes real spend (main thread + this goal's subagents, from the transcripts) into the plan header at every turn end. Every step update prints `budget: <pct>% of <ceiling>`, with a WARNING from 70% — read it. At 70% of the ceiling:
  - first time, ceiling below approved × auto-raise → the Stop hook raises it to approved × auto-raise itself and logs `D budget auto-raised to <size> (tag: auto)`; mention it in the overview's next `U` line and continue.
  - after that → stop dispatching, status `waiting`, ask: continue / cut scope / stop. On continue, raise once (`--header budget='L <n>k|M'`) to measured spend + remaining estimate + 30%, never in small steps that re-ask every turn. **Autonomous** with the rest already in the approved plan may instead raise it itself up to 2× `approved:` (`D budget raised to … (tag: auto)`); plan-set refuses past 2× without `D budget … (tag: user)`.
- **Stop at done**: all criteria evidenced → deliver. No polish beyond the criteria.

## Interruptions

Mid-run user messages, sorted at once:
- question → answer; loop continues
- new requirement / test change / goal change → `rules/changes.md`
- stop / pause → record state, stop now
- side idea → `parked`, acknowledge in one line

## Environment

Before a verify that needs services (DB, Redis, a running app), check them with the command in `profile.md`; down → report and wait; absent on this machine (no service or tool to run it) → `unverified` (Cycle §8). Run such verifies, and heavy ones, under `scripts/lock.py <store>/.heavy.lock` (other goals share the services). Never start, stop, restart or reseed them.
