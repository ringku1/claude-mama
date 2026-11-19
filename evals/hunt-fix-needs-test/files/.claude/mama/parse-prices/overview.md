# Parse prices as shown on the site

**Status:** Paused · 1 of 3 parts done

## Goal

Turn prices as the site shows them ("$5.99", "$1,200.50") into numbers the cart can add up.

**Started from:** your message

## Done means

- [ ] "$5.99" becomes 5.99 and "$1,200.50" becomes 1200.5

## Timeline

| When  | What                                  |
| ----- | ------------------------------------- |
| 09:00 | Started; looked at the cart code      |
| 09:04 | Plan approved, runs on its own        |
| 09:12 | Prices are parsed                     |
| 09:17 | Paused at your ask while checking for bugs |

## Where we are

The parser is built. The bug check flagged a problem with prices over a thousand; next: confirm and fix it.

## Branch & PR

Branch `feat/parse-prices` from `main` · PR: you'll open it yourself
