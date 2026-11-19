goal: parse-prices | type: build | status: paused | mode: autonomous
progress: 1/3 (33%) | blocked: 0 | budget: ~0k / M | approved: M
base: main | branch: feat/parse-prices | worktree: __WORKTREE__ | pr: none | deliverable commit: n/a | trello: none
started: 2026-11-12 09:00

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1 | parse_price turns prices as shown on the site into numbers: "$5.99" → 5.99, "$1,200.50" → 1200.5 | S1 | test_price: 2 passed |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1 | build | parse_price(text) for prices as shown on the site, with tests | — | price.py, test_price.py | python -m unittest test_price | done | 0 | 10m | 09:05 | 09:12 | test_price 2 passed; commit __S1SHA__; covers price.py, test_price.py |
| S2 | hunt | bug hunt on the goal's changes | S1 | — | a round with 0 real bugs | running | 0 | 10m | 09:13 |  | round 1 |
| S3 | release | push the branch | S2 | — | git push exits 0 | todo | 0 | 5m |  |  |  |

## Parked

- <out-of-scope idea or follow-up>
