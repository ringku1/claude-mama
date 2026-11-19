goal: add-text-helpers | type: build | status: approved | mode: autonomous
progress: 0/4 (0%) | blocked: 0 | budget: ~0k / M | approved: M
base: main | branch: feat/text-helpers | worktree: __WORKTREE__ | pr: ask-at-end | deliverable commit: n/a | trello: none
started: 2026-11-11 16:30

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1 | slugify("Hello World") returns "hello-world" | S1 | — |
| C2 | word_count("one two  three") returns 3 | S2 | — |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1 | build | slugify(text): lower case, words joined by hyphens, with a test | — | slug.py, test_slug.py | python -m unittest test_slug | todo | 0 | 10m |  |  |  |
| S2 | build | word_count(text): number of words split on any whitespace, with a test | — | wordcount.py, test_wordcount.py | python -m unittest test_wordcount | todo | 0 | 10m |  |  |  |
| S3 | hunt | bug hunt on the goal's changes | S1,S2 | — | a round with 0 real bugs | todo | 0 | 10m |  |  |  |
| S4 | release | push the branch, PR per the user's choice | S3 | — | git push exits 0 | todo | 0 | 5m |  |  |  |

## Parked

- <out-of-scope idea or follow-up>
