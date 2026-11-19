# Research

Map every branch of the work before asking anything; a case found mid-run costs a second round.

## Lenses

Read `rules/agents.md`, then dispatch the **research lenses** as read-only agents in one message (`read_limit`). Meanwhile read the repo rules, `~/.claude/mama/patterns.md` (learned lines only), `lessons.md` and `profile.md` (create it if absent) yourself.

| Lens | Finds |
| ---- | ----- |
| **Exists & precedent** | Whether it (or most of it) exists, shrinking or changing the goal; the closest similar feature end to end, as the template to copy. |
| **Architecture & reach** | Every layer and module touched: data (tables, migrations, existing rows), API (routes, services, permissions, jobs, cache, events), web (routes, screens, shared components, generated clients). Every caller or consumer of what changes, by search, never hand-picked. The **database changes** needed (tables, columns, indexes, constraints, migrations, backfills, deletes), or none. |
| **Cases** | Every branch to handle: entity variants and types, roles and permissions, states and transitions, tenancy, empty / limits / errors, concurrency, existing data, i18n; each with how the code handles it today, or "unknown". |
| **Rules & proof** | Applicable repo rules, skills and enforcement tests; how this area is tested and what tests need (DB env, fixtures). |
| **Design** (UI work) | The design screen(s): regions, states, copy; what the input asks for that the design lacks, and the reverse. |

## Ask what the work is for first

A review, audit or "check X" goal with no stated outcome (report only or fixes too; which severities; which area) gets that one question before any lens runs. Size the research to the answer.

## Size and record

Economy matters as much as coverage: a small goal gets one or two lenses (none in quick mode), a large one all, a big area more agents split by module. Merge the returns yourself: findings → `F` lines (tag what you checked yourself `verified`), each case → an `F … case:` line, each needed database change → an `F … db:` line, then one `E research: <n> findings, <m> cases, <k> open` line. Spot-check what the plan rests on; a recommendation that depends on code is checked feasible (file:line or a quick probe) or marked "unproven". Open cases feed the questions; the plan covers every case. Plan a research step only for what stays open; never re-prove a finding.

## Lens brief (≤ ~200 words)

```
Goal (1 line): ...    Repo: <absolute path> — read only, change nothing.
Lens: <Exists & precedent | Architecture & reach | Cases | Rules & proof | Design> — scope: <dirs / modules>
Already known (don't re-prove): F2 <claim>, F5 <claim>
Search, don't hand-pick: every caller/usage comes from a grep, not memory.
Return ≤15 lines: `claim — file:line` · `case: <branch> — handled how today (file:line) | unknown` · `db: <change needed> — why (file:line)` · open questions only the user can answer.
```
