<!-- profile.md — per-repo facts, created on first /mama use from AGENTS.md/CLAUDE.md/CONTRIBUTING/package scripts. Machine file.
Fill what the repo states, unmarked. Only where the repo states nothing: write the default shown, marked "(default)". Only facts you can't check without touching services: "unknown". Update when a fact proves wrong. Delete this comment. -->

repo: <name> | default branch: <main> | created: <YYYY-MM-DD>

## Commands (narrowest first)

- format: <cmd>
- typecheck (one package/file): <cmd>
- lint (one package): <cmd>
- unit test (one test / one package): <cmd>
- e2e (one spec): <cmd | none>
- full gate (before push only): <cmd>
- missing tools: <tools the repo expects but this checkout lacks — tell the user; never borrow from another checkout>

## Conventions

- branch: <repo rule | `<type>/<kebab-summary>` (default)>
- commits: <repo rule | Conventional Commits `type(scope): description` (default)>
- PR template: <path | none>
- merge base into branch: merge commit, never rebase
- other rules that bind every goal: <one line each>

## Never

- <services/stacks not to stop or reseed>
- <files never hand-edited, e.g. generated files>
- <hooks never bypassed>

## Environment

- services needed for tests: <list | none | unknown> — check cmd: <cmd>
- resource notes: <e.g. installs per worktree are slow>

## Trello

- process: <link to CONTRIBUTING section | none>
