goal: add-verbose-flag | type: build | status: paused | mode: checkpointed
progress: 1/3 (33%) | blocked: 0 | budget: ~0k / S
base: main | branch: feat/verbose-flag | worktree: __WORKTREE__ | pr: none | deliverable commit: n/a | trello: none
started: 2026-11-11 16:37

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1 | --verbose prints a debug line to stderr; output unchanged without it | S2,S3 | — |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1 | build | add --verbose option to the parser | — | cli.py | python cli.py --help shows --verbose | done | 0 | 10m | 16:37 | 16:37 | commit __S1SHA__ |
| S2 | build | print a debug line to stderr when --verbose | S1 | cli.py | python cli.py --verbose 2>&1 >/dev/null / grep -q debug | todo | 0 | 10m |  |  |  |
| S3 | build | test for --verbose | S2 | test_cli.py | python -m unittest test_cli | todo | 0 | 10m |  |  |  |

## Parked

- <out-of-scope idea or follow-up>
