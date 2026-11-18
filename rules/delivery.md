# Git, delivery, Trello, close

Research goals: no git. A file deliverable the user chose not to commit stays untracked, marked "not committed" in overview Deliverables and the final message; a committed one follows this file.

## Branch setup (after plan approval)

1. Base branch = the user's answer. Never assume it.
2. Branch name: `profile.md` convention (default `<type>/<kebab-summary>`, e.g. `feat/course-filters`). Log it.
3. `git -C <main checkout> fetch origin`, then from the main checkout:
   `git worktree add --no-track <main checkout>/.claude/worktrees/mama-<slug> -b <branch> origin/<base>`
   (`--no-track`: the first push sets its upstream.) Existing branch → add the worktree on it and merge the latest `origin/<base>`. Record `worktree:` and `branch:` in the plan header.
4. In the worktree, install only what verifies need (e.g. `pnpm install` only if a step touches JS/TS); note slow installs in `profile.md`.
5. Never commit or push to the base branch or `main`.
6. **Continuing an existing feature branch** (user chose "commit on <branch> itself"): `branch:` = that branch, `base:` = its PR target (usually `main`). Checked out in another worktree → work there (`worktree:` = that path), don't remove it at close.
7. **The user chose the default branch itself** ("work directly on main"): commit in the main checkout, `worktree: n/a`. The only case that commits to `main`; still merge nothing else into it, never force-push.

## Merging the base

Before work starts and right before push: `git -C <main checkout> fetch origin`, then in the worktree `git merge origin/<base>` — a merge commit, never rebase. Conflict: keep both intents, run the conflicted files' related tests, log `conflict` with the resolution; one needing a product decision → ask.

## Commits

- Commit only at stable states — the step's verify passed and touched code builds/typechecks; half-working work is never committed.
- One commit per completed step (batched steps share one). Revising earlier work is a new commit; never squash or rewrite pushed history (squashing is the user's call).
- Message: repo convention (Conventional Commits: `type(scope): description`), short, plain, imperative; body only for a non-obvious why.
  - Good: `feat(api): filter courses by price` · `fix(web): keep filters after page reload`
  - Bad: `feat: implement S3 per plan` · `wip` · `update files`
- Ground rules apply (no attribution, no local artifacts); also never mention mama.
- Never bypass hooks (`--no-verify`, `LEFTHOOK=0`); fix the cause.
- Log `commit <shorthash>`.

## Push

When every criterion has evidence, the bug hunt is clean and the milestone check passed: run `profile.md`'s full gate once (under `scripts/lock.py <store>/.heavy.lock`), merge the latest base, push (`git -C <main checkout> push -u origin <branch>`). On exit 0, log `E pushed <sha> to <branch or PR>`. No remote: commit only, `pr: none`, say so.

## Pull request (only per the user's choice)

The header's `pr` is one of `ask-at-end | auto | none | declined | <url>` (plan-set refuses anything else).
- `pr: ask-at-end` → show draft title + body; yes → open, `pr=<url>`; no → `pr=declined`, draft in your final message.
- `pr: auto` → open, `pr=<url>`.
- `pr: none` → skip.

Repo PR template if any. Short body:
- **What** — the change in 2-4 bullets
- **Why** — one or two lines
- **How verified** — checks run and results
- **Notes** — known limits, follow-ups (only if any)

Separate PRs for independent parts if repo rules say so. Log `pr <url>`.

## Trello (if a card is linked and a Trello connector is available)

Comment right after plan approval (what will change, 1-2 lines), after each push, PR and test result, and when a decision changes what the card describes (schema, contract). ≤5 plain lines: done, test result, next. Comments only; card moves per the repo's CONTRIBUTING. Log each as `trello`; a linked card with no `trello` line blocks close. No connector → list what to set in the final message.

## Close

1. Regenerate `overview.md` with the Final report: built/found, how verified, decisions worth review, parked follow-ups, spend.
2. Learning — all required:
   - `<store>/lessons.md` (append under `scripts/lock.py <store>/.shared.lock`) — one metrics line, then any lessons:
     `<date> <slug> <type> | steps <n> | time est <m>m critical path (sum <m>m) / actual <m>m (active <m>m) | tokens est <S/M/L> / ~<n>k | questions <n> (changed plan: <n>) | fix rounds <n> | hunt rounds <n> (real bugs <n>) | checker findings <n> | compactions <n> | wrong assumptions <n> | reversed decisions <n>`
     Actual = first to last log line, across days (log.py writes a `-- YYYY-MM-DD` marker on date change); active excludes user waits and idle gaps over 2h. Tokens: from close-check's `METRICS:` line (run it first; it drafts this line).
   - `<store>/profile.md` — update facts this goal changed (command, convention, shared "keep X in sync").
   - `~/.claude/mama/patterns.md` via `scripts/learn.py` — `seen` per user choice (mode, PR, branch), and `goal "<kind, steps>: est <m>m critical path / <size>, actual <m>m (active <m>m) / <n>k measured"`, which close-check prints as `LEARN:` (never guessed).
3. Clean up only what this run created: step worktrees, temp files, processes it started. Goal worktree: branch pushed and tree clean → `git worktree remove` (branch stays); else keep it and say where. Never stop the user's servers or containers.
4. Run `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/close-check.py <store>/<slug>`. It lists what's missing (criteria evidence, step times, Trello line, metrics line, patterns update) and prints a prefilled metrics line: paste into `lessons.md`, fill the `?` fields. Status `done` only when it prints OK.
5. Tell the user briefly: done, branch, PR status, overview location.
