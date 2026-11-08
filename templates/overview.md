<!--
overview.md — the ONLY file the user reads. Rules:
- Plain language a non-engineer could follow. No step IDs, decision IDs, status codes or file:line refs.
- Current state only: written fresh each time, no "was / replaces / updated" history notes.
- Short: aim to fit on one screen; detail belongs in plan.md / log.md.
- Drop sections that are empty (except Goal, Done means, Timeline, Where we are).
- Delete this comment block in the real file.
-->

# <Goal title in plain words>

**Status:** <Planning | Waiting for you | Working | Paused | Blocked | Done> · <one-line progress, e.g. "7 of 12 parts done">

## Goal

<2-4 sentences: what we're building or finding out, and why.>

**Started from:** <the input in one line — "Trello card: Course filters", "your message", "docs/x.md">

## Done means

- [x] <criterion in plain words> — <how it was proven, plain: "tests for filtering by price pass">
- [ ] <criterion>

## Timeline

| When  | What                                   |
| ----- | -------------------------------------- |
| 10:02 | Started; researching the existing code |
| 10:20 | Plan approved                          |
| 10:41 | Filter API done and tested             |
| now   | Building the filter panel — ETA 11:15  |

**Estimated finish:** <HH:MM, or "unknown until X"> — at close, drop the "now" row and this line; the last row is the finish time.

## Where we are

<2-4 lines: what's working now, what's next.>

## Needs your input

- <question / approval / blocker, in plain words — or omit section>

## Key decisions

- Every decision you made yourself (`inferred`/`assumed`) that changes product behaviour (a limit, a default, a rule users hit) must be listed here so the user can veto it.
- <one plain sentence each, with the reason: "Deleted courses can be restored, because the rest of the app already works that way.">

## What changed along the way

- <plain words: "You added sorting; that's now part of the goal.">

## Deliverables

- [<name>](<repo-relative path>) — <what it is> <"(not committed)" if left untracked>

## Branch & PR

Branch `<name>` from `<base>` · PR: <link | waiting for your OK | not requested>

<!-- At close, add: -->

## Final report

<What was built or found · how it was verified · decisions worth your review · follow-ups parked for later.>
