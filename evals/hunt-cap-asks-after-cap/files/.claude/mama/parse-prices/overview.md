# Parse prices as shown on the site

<!-- mama:auto:start -->
**Status:** Paused · 2 of 4 parts done

## Done means

- [x] "$5.99" becomes 5.99 and "$1,200.50" becomes 1200.5 — the price tests pass
- [ ] A refund like "-$5.00" keeps its minus sign

## Timeline

| When  | What                                       |
| ----- | ------------------------------------------ |
| 09:00 | Started; looked at the cart code           |
| 09:04 | Plan approved, runs on its own             |
| 09:12 | Prices are parsed                          |
| 09:24 | First bug check: one bug found and fixed   |
| 09:29 | Paused at your ask during the second check |

## Where we are

2 of 4 parts done. Working on: bug hunt on the goal's changes. Next: push the branch.
<!-- mama:auto:end -->

## Goal

Turn prices as the site shows them ("$5.99", "$1,200.50", refunds "-$5.00") into numbers the cart can add up.

**Started from:** your message

## Key decisions

- Branch from main; you open the pull request yourself.

## Branch & PR

Branch `feat/parse-prices` from `main` · PR: you'll open it yourself
