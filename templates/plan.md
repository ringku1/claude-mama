<!-- plan.md — machine file, source of truth. Only the orchestrator writes it. Update step rows with scripts/plan-set.py; header lines with Edit. Unknown-yet values: —. Delete this comment. -->

goal: <slug> | type: <build|fix|research|mixed> | status: <planning|approved|running|waiting|paused|blocked|done|aborted> | mode: <checkpointed|autonomous|quick|—>
progress: <done>/<live> (<pct>%) | blocked: <n> | budget: ~<spent>k / <S|M|L>
base: <branch|n/a> | branch: <branch|n/a> | worktree: <abs path|n/a> | pr: <ask-at-end|auto|none|declined|url> | deliverable commit: <yes|no|n/a> | trello: <url|none>
started: <YYYY-MM-DD HH:MM>

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1  |           | S1,S2     |          |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1  | build |       | —    |      |        | todo   | 0   | 15m |       |     |       |

<!--
kind: build | fix | research | document | decide | release
status: todo | running | testing | fixing | done | blocked | obsolete | parked
milestone: "★" in notes on a step that ends a milestone (rules/planning.md → Milestones). Goal status `waiting` = stopped at a checkpoint for the user.
notes: confidence (L = research/ask first), decision refs (D3), evidence pointer, covered files after pass.
progress counts live steps (excludes obsolete, parked).
budget: ~spent is measured from the session transcripts by the Stop hook (scripts/spend.py); you set only the size.
-->

## Parked

- <out-of-scope idea or follow-up>
