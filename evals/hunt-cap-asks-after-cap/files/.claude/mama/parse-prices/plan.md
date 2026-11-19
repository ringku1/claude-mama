goal: parse-prices | type: build | status: paused | mode: autonomous | tier: full
progress: 2/4 (50%) | blocked: 0 | budget: ~0k / M | approved: M | auto-raise: 1.5x
base: main | branch: feat/parse-prices | worktree: __WORKTREE__ | pr: none | deliverable commit: n/a | trello: none
started: 2026-11-12 09:00

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1 | parse_price turns prices as shown on the site into numbers: "$5.99" → 5.99, "$1,200.50" → 1200.5 | S1,S4 | test_price: 3 passed |
| C2 | refunds keep their sign: "-$5.00" → -5.0 | S1 | — |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1 | build | parse_price(text) for prices as shown on the site, with tests | — | price.py, test_price.py | python -m unittest test_price | done | 0 | 10m | 09:05 | 09:12 | test_price 2 passed; commit __S1SHA__; covers price.py, test_price.py |
| S2 | hunt | bug hunt on the goal's changes | S1 | — | a round with 0 real bugs | running | 0 | 10m | 09:13 |  | round 1: 1 real, fixed in S4; round 2 running |
| S3 | release | push the branch | S2 | — | git push exits 0 | todo | 0 | 5m |  |  |  |
| S4 | fix | prices with a thousands separator | S1 | price.py, test_price.py | python -m unittest test_price | done | 0 | 10m | 09:17 | 09:24 | failing-first: test_price.ParsePriceTest.test_thousands; test_price 3 passed; commit __FIXSHA__ |

## Parked

- <out-of-scope idea or follow-up>
