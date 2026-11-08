# Agents and resources

## Model

Every subagent: `model: "opus"`, `effort: "medium"`. This is the user's explicit instruction, so set both on every spawn. Don't switch to cheaper models to save tokens — save tokens with the rules below instead.

## When to spawn

Spawn only when the work is big enough to repay an agent's setup (it reads files from scratch — a checker costs tens of thousands of tokens). Do it yourself when it's a handful of tool calls. Batch tiny steps into one agent. Parallel research is worth it when questions are independent; one targeted search is not. Sizing for builds and when checkers are required: `rules/loop.md`.

## Concurrency

Before each dispatch wave: `bash ${CLAUDE_SKILL_DIR}/scripts/resources.sh <ready steps> <store> <own slug>` → prints `limit=N` = min(ready, cores ÷ 2 (halved if load is high), free RAM GB ÷ 1.5, 5) minus steps other goals are running.

- Heavy verifies (full build, e2e) and anything touching shared services run one at a time across all goals: `flock <store>/.heavy.lock <cmd>`.
- Read-only agents share the working tree.
- All agents of a goal work in the goal's worktree (give the absolute path in the brief). One editing agent at a time can work there directly.
- Exception: parallel editing agents may share the goal worktree when their `owns` are disjoint top-level areas (e.g. `apps/api/**` vs `apps/web/**`), neither commits, and you commit per area after each verify — cheaper than a step worktree that needs a fresh install. Log it as a decision.
- Otherwise, parallel editing agents each get a step worktree branched from the goal branch — `git -C <goal worktree> worktree add <goal worktree>.<step> -b <branch>-<step>` — never the Agent tool's own worktree isolation (it branches from the session's checkout, not the goal branch). Merge each into the goal branch in planned order; you resolve conflicts; remove the step worktree and branch after merging.

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

Test-agent brief: same frame, but "Check, don't fix: run <verify>, read the diff for <files>, judge whether the test really exercises <criterion>. Return pass/fail + evidence."

Never pass the conversation, the whole plan or the log. Agents never write `plan.md`, `log.md` or `overview.md` — you record what they report.

## Token hygiene (for you and agents)

- Search, then read line ranges; don't read large files whole.
- Commands quiet: `-q`, failures only, `| tail -n 40`; long output → file, read only on failure.
- Narrow tests per step; full gate once before delivery.
- Reuse findings from `log.md` instead of re-reading code.
