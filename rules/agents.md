# Agents and resources

## Model

Set `model: "opus"`, `effort: "medium"` on every spawn unless the user's own instructions say otherwise. Save tokens with the rules below, never with cheaper models.

## When to spawn — parallel by default

- Every ready step goes out at once: one message, several background Agent calls. Verify each return and dispatch the next ready step right away (no waves). Inline work never holds up a dispatch.
- **Fan out inside a step too**: independent research questions, review areas or dimensions, test suites (API and web as parallel background commands), fixes for failures in different areas.
- **Doesn't fan out**: a step whose deps aren't done, two edits to the same files, verifies under the heavy lock (they queue; keep them short).
- One agent takes several steps only when they are tiny and touch the same files. Step sizing and when checkers are required: `rules/loop.md`.

## Concurrency

Before dispatching, run `scripts/resources.py <ready steps> <store> <own slug>` and fill both limits it prints:
- `limit=N`, agents that edit and build: min(ready, cores ÷ 2 (halved if load is high), free RAM GB ÷ 1.5, 8) minus steps other goals are running;
- `read_limit=M`, read-only agents (research, review, test design): min(ready, 8).

- Heavy verifies (full build, e2e) and anything touching shared services run one at a time across all goals: `scripts/lock.py <store>/.heavy.lock <cmd>`.
- All agents of a goal work in the goal's worktree (absolute path in the brief).
- **Parallel editing agents share it** when their `owns` are disjoint files or directories at any depth (e.g. two modules, a test and its code); a step worktree costs a fresh install. No agent commits; each runs only its own area's checks; after its verify you commit the step with `git add <its owns>`. Generated files have one owner, or you regenerate them once after the parallel steps land. A typecheck error in another agent's files is reported, not fixed.
- Only when owns must overlap, or a step needs its own build state, a parallel editing agent gets a step worktree from the goal branch: `git -C <goal worktree> worktree add <goal worktree>.<step> -b <branch>-<step>`. Never the Agent tool's worktree isolation (it branches from the session's checkout, not the goal branch). Merge each into the goal branch in planned order, resolve conflicts yourself, then remove the step worktree and branch.

## Brief (what an agent receives) — ≤ ~300 words

```
Goal (1 line): ...
Repo: <absolute path> — work only here.
Your step: <id> <title> — <kind>
You own: <files/dirs>; don't edit anything else.
Done when: <criterion> — proven by: <verify command>
Relevant decisions: D3 <choice>, D7 <choice>
Relevant findings: F2 <claim — file:line>
Repo rules: <the 1-3 that matter, e.g. "use the api-module skill">
Rules: no commits (orchestrator commits); no git stash/checkout/reset/restore/switch (shared worktree); no tracking-file edits; quiet commands, failures only.
Return ≤10 lines: done? · files changed · verify result (pass/fail + key line) · issues/decisions you had to make.
```

Research-lens brief: `rules/research.md`. Test-agent brief: same frame, but "Check, don't fix: run <verify>, read the diff for <files>, judge whether the test really exercises <criterion>. Return pass/fail + evidence."

Read-only agents (research lenses, checkers, reviewers) spawn with `subagent_type: Explore` and a short brief (≤ ~150 words: question, scope, return shape). A spawn costs 14–36k tokens before any work, so anything a handful of tool calls can do stays in the main thread. Never pass the conversation, the whole plan or the log. Agents never write `plan.md`, `log.md` or `overview.md`; you record what they report.

## Token hygiene (for you and agents)

- Search, then read line ranges, not whole large files.
- Quiet commands: `-q`, failures only, `| tail -n 40`; long output → file, read only on failure.
- Narrow tests per step; full gate once before delivery.
- Reuse `log.md` findings instead of re-reading code.
