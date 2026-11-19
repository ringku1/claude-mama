goal: text-stats | type: build | status: paused | mode: checkpointed | tier: standard
progress: 1/6 (17%) | blocked: 0 | budget: ~30k / L 40k | approved: L 40k | auto-raise: 1.5x
base: main | branch: feat/text-stats | worktree: __WORKTREE__ | pr: none | deliverable commit: n/a | trello: none
started: 2026-11-13 10:00

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1 | stats.py counts words, characters (spaces excluded) and lines of a text | S1,S2,S3 | — |
| C2 | `python stats.py <file>` prints `words chars lines` for the file | S4 | — |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1 | build | word_count(text), with tests | — | stats.py, test_stats.py | python -m unittest test_stats | done | 0 | 10m | 10:05 | 10:11 | test_stats 2 passed; commit __S1SHA__ |
| S2 | build | char_count(text) without spaces, with tests | S1 | stats.py, test_stats.py | python -m unittest test_stats | todo | 0 | 10m |  |  |  |
| S3 | build | line_count(text), with tests | S2 | stats.py, test_stats.py | python -m unittest test_stats | todo | 0 | 10m |  |  |  |
| S4 | build | command line: python stats.py <file> prints words chars lines, with a test | S3 | stats.py, test_stats.py | python -m unittest test_stats | todo | 0 | 10m |  |  |  |
| S5 | hunt | bug hunt on the goal's changes | S4 | — | a round with 0 real bugs | todo | 0 | 10m |  |  |  |
| S6 | release | commit the branch | S5 | — | git status clean on feat/text-stats | todo | 0 | 5m |  |  |  |

## Parked

- <out-of-scope idea or follow-up>
