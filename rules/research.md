# Research

Questions and plan are only as good as this map of the work, so explore every branch of it before asking anything — cases found mid-run cost a second round (a merge brief that listed only the obvious placeholders missed half).

## Lenses

Read `rules/agents.md`, then dispatch the **research lenses** as read-only agents, all in one message (`read_limit`); while they run, read the repo rules, `~/.claude/mama/patterns.md` (learned lines only), `lessons.md` and `profile.md` (create it if absent) yourself:

| Lens | Finds |
| ---- | ----- |
| **Exists & precedent** | Does this (or most of it) already exist — then the goal may shrink or change? The closest similar feature end to end: the template to copy. |
| **Architecture & reach** | Every layer and module the work touches — data (tables, migrations, existing rows), API (routes, services, permissions, jobs, cache, events), web (routes, screens, shared components, generated clients) — and every caller or consumer of what changes, found by search, never hand-picked. |
| **Cases** | Every branch the work must handle: entity variants and types, roles and permissions, states and transitions, tenancy, empty / limits / errors, concurrency, existing data, i18n — each with how the code handles it today, or "unknown". |
| **Rules & proof** | The repo rules, skills and enforcement tests that apply; how this area is tested and what the tests need (DB env, fixtures). |
| **Design** (UI work) | The design screen(s): regions, states, copy — what the input asks for that the design lacks, and the reverse. |

## Ask what the work is for first

A review, audit or "check X" goal whose wanted outcome isn't stated — a report only, or fixes too; which severities; which area — gets that one question before any lens runs, and the research is sized to the answer. Seven review lenses for findings the user then didn't want fixed cost a whole goal's budget.

## Size and record

Size it to the goal — economy matters as much as coverage: a small goal gets one or two lenses (or none, in quick mode), a large one all of them, and a big area can be split across more agents by module. Merge the returns: findings → `F` lines (tag what you checked yourself `verified`), each case → an `F … case:` line, then one `E research: <n> findings, <m> cases, <k> open` line. Open cases feed the questions; the plan must cover every case. Plan a research step only for what is still open after this phase — never re-prove a finding.

## Lens brief (≤ ~200 words)

```
Goal (1 line): ...    Repo: <absolute path> — read only, change nothing.
Lens: <Exists & precedent | Architecture & reach | Cases | Rules & proof | Design> — scope: <dirs / modules>
Already known (don't re-prove): F2 <claim>, F5 <claim>
Search, don't hand-pick: every caller/usage comes from a grep, not memory.
Return ≤15 lines: `claim — file:line` · `case: <branch> — handled how today (file:line) | unknown` · open questions only the user can answer.
```

Lenses return claims with `file:line`, never file dumps; merge them yourself and spot-check what the plan will rest on.
