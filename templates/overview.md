<!--
overview.md — the ONLY file the user reads. Rules:
- Plain language a non-engineer could follow. No step IDs, decision IDs, status codes or file:line refs.
- Current state only: written fresh each time, no "was / replaces / updated" history notes.
- Short: aim to fit on one screen; detail belongs in plan.md / log.md.
- Drop sections that are empty (except Goal, Done means, Timeline, Where we are).
- Between the mama:auto markers is generated (scripts/overview.py, after every plan write): Status, Done means, Timeline (from `log.py <log> U "<plain text>"` lines), Where we are, Needs your input. Never edit inside the markers; only an optional ` · detail` after the Status line's progress is kept.
- Hand-write everything outside the markers.
- Delete this comment block in the real file.
-->

# <Goal title in plain words>

<!-- mama:auto:start -->
**Status:** Planning

## Done means

- [ ] Set when the plan is ready

## Timeline

| When | What |
| ---- | ---- |

## Where we are

Planning: research and questions come first.
<!-- mama:auto:end -->

## Goal

<2-4 sentences: what we're building or finding out, and why.>

**Started from:** <the input in one line — "Trello card: Course filters", "your message", "docs/x.md">

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
