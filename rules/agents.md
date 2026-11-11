# Agents and resources

## Model

Every subagent: `model: "opus"`, `effort: "medium"` — set both on every spawn, unless the user's own instructions say otherwise. Don't switch to cheaper models to save tokens — save tokens with the rules below instead.

## When to spawn — parallel by default

The user wants work done fast, so parallel agents are the default:

- **Every step runs in its own agent**, and every ready step goes out at once — one message with several Agent calls, in the background. As each returns, verify it and dispatch the next ready step right away (no waves).
- **You orchestrate.** While agents run: verify finished steps, write the next briefs, commit, record state. Build inline only what is a handful of tool calls (a one-line fix, a rename) — never something that holds up a dispatch.
- **Fan out inside a step too**: independent research questions, review areas or dimensions, test suites (API and web as parallel background commands), and fixes for failures in different areas each get their own agent or command.
- **What doesn't fan out**: a step whose deps aren't done, two edits to the same files, and verifies under the heavy lock (they queue — keep them short).
- Batch steps into one agent only when they are tiny and touch the same files. Sizing for builds and when checkers are required: `rules/loop.md`.

## Concurrency

Before dispatching: `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/resources.py <ready steps> <store> <own slug>` → prints
- `limit=N` for agents that edit and build (they run compilers and tests): min(ready, cores ÷ 2 (halved if load is high), free RAM GB ÷ 1.5, 8) minus steps other goals are running;
- `read_limit=M` for read-only agents (research, review, test design): min(ready, 8) — they put no load on the machine.

Fill both up to their limits.

- Heavy verifies (full build, e2e) and anything touching shared services run one at a time across all goals: `scripts/lock.py <store>/.heavy.lock <cmd>`.
- Read-only agents share the working tree.
- All agents of a goal work in the goal's worktree (give the absolute path in the brief).
- **Parallel editing agents share it** whenever their `owns` are disjoint files or directories, at any depth (two modules, two screens, a test file next to the code it tests). No agent commits; each runs only its own area's checks; you commit each step with `git add <its owns>` after its verify. Generated files have one owner, or you regenerate them once after the parallel steps land. A typecheck error in files another agent owns isn't the agent's to fix: it reports it. Sharing is cheaper than a step worktree, which needs a fresh install.
- Only when owns must overlap, or a step needs its own build state, parallel editing agents each get a step worktree branched from the goal branch — `git -C <goal worktree> worktree add <goal worktree>.<step> -b <branch>-<step>` — never the Agent tool's own worktree isolation (it branches from the session's checkout, not the goal branch). Merge each into the goal branch in planned order; you resolve conflicts; remove the step worktree and branch after merging.

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
Rules: no commits (orchestrator commits); no tracking-file edits; quiet commands, failures only.
Return ≤10 lines: done? · files changed · verify result (pass/fail + key line) · issues/decisions you had to make.
```

Research-lens brief: `rules/research.md`.

Test-agent brief: same frame, but "Check, don't fix: run <verify>, read the diff for <files>, judge whether the test really exercises <criterion>. Return pass/fail + evidence."

Never pass the conversation, the whole plan or the log. Agents never write `plan.md`, `log.md` or `overview.md` — you record what they report.

## Token hygiene (for you and agents)

- Search, then read line ranges; don't read large files whole.
- Commands quiet: `-q`, failures only, `| tail -n 40`; long output → file, read only on failure.
- Narrow tests per step; full gate once before delivery.
- Reuse findings from `log.md` instead of re-reading code.
