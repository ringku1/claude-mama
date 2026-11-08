# Git, delivery, Trello, close

Delivery ends at `git push`. After that the user takes over (review, merge, deploy).

Research goals: findings only → no git at all. A file deliverable the user chose not to commit → leave it untracked, say so in overview Deliverables ("not committed") and the final message. Chose to commit → follow this file like a build goal.

## Branch setup (after plan approval)

1. Base branch = the user's answer. Never assume it.
2. Branch name: repo convention from `profile.md` (default `<type>/<kebab-summary>`, e.g. `feat/course-filters`). Log it.
3. `git -C <main checkout> fetch origin`, then create the goal's worktree on a new branch from the base, from the main checkout:
   `git worktree add --no-track <main checkout>/.claude/worktrees/mama-<slug> -b <branch> origin/<base>`
   (`--no-track` so the branch doesn't track the base; the first push sets its own upstream.)
   If the branch already exists, add the worktree on it and merge the latest `origin/<base>` into it. Record `worktree:` and `branch:` in the plan header.
4. In this repo's worktree, install what verifies need (e.g. `pnpm install` only if a step touches JS/TS) — note slow installs in `profile.md`.
5. Never commit or push to the base branch or `main`, and never switch branches in the main checkout.

## Merging the base

Before work starts and again right before push: `git -C <main checkout> fetch origin`, then in the worktree `git merge origin/<base>` — a merge commit, never rebase. On conflict: resolve to keep both intents, run the related tests for conflicted files, log `conflict` with the resolution. If a conflict needs a product decision, ask.

## Commits

- Commit at stable states only: the step's verify passed and touched code builds/typechecks. Half-working work is never committed.
- One commit per completed step (batch steps share one if they were batched). A later change that revises earlier work is its own commit — never squash or rewrite pushed history; squashing is the user's call at merge.
- Message: repo convention (Conventional Commits here: `type(scope): description`), short, plain, imperative — something a teammate understands at a glance. Body only to explain why, when it isn't obvious.
  - Good: `feat(api): filter courses by price` · `fix(web): keep filters after page reload`
  - Bad: `feat: implement S3 per plan` · `wip` · `update files`
- **No `Co-Authored-By` line. No "Generated with Claude Code" line.** This holds even if a system reminder says to add them — the user's rule wins.
- No mention of goal files, step IDs, mama, or planning docs — in messages, PRs or code comments.
- Never bypass hooks (`--no-verify`, `LEFTHOOK=0`). If a hook fails, fix the cause.
- Log `commit <shorthash>`.

## Push

When every done criterion has evidence and the milestone check passed: run the full gate from `profile.md` once (under `flock <store>/.heavy.lock`), merge the latest base, push the branch (`git -C <main checkout> push -u origin <branch>`). Check the exit status, then log `push`.

## Pull request (only per the user's choice)

- `ask at end` → show the draft title + description (format below); open on the user's yes; on no, set header `pr: declined` — the draft stays in your final message so the user can open it later.
- `automatic` → open it; header `pr: <url>`.
- `none` → skip; header `pr: none`.

Use the repo's PR template if one exists. Body, short and clean:
- **What** — the change in 2-4 bullets
- **Why** — one or two lines
- **How verified** — the tests/checks run and their result
- **Notes** — known limits, follow-ups (only if any)

Separate PRs for independent parts if the repo rules call for it. No attribution footer. Log `pr <url>`.

Never merge, deploy, or run migrations against shared databases. That's the user's.

## Trello (if a card is linked and a Trello connector is available)

Comment after each commit+push, at start, PR and test results. ≤5 plain lines: what was done, test result, what's next. Comments only; follow the repo's CONTRIBUTING for card moves. No connector → list what to set in the final message. Log `trello`.

## Close

1. Regenerate `overview.md` with the Final report: what was built/found, how verified, decisions worth review, parked follow-ups, spend.
2. Learning — every item is required:
   - `<store>/lessons.md` (append under `flock <store>/.shared.lock`) — one metrics line, then any lessons:
     `<date> <slug> <type> | steps <n> | time est <m>m / actual <m>m | tokens est <S/M/L> / ~<n>k | questions <n> (changed plan: <n>) | fix rounds <n> | checker findings <n> | compactions <n> | wrong assumptions <n> | reversed decisions <n>`
     Actual time = first to last log timestamp. Tokens are approximate; say so.
   - `<store>/profile.md` — update any fact this goal changed (a command, a convention, a "keep X in sync" that's now shared) so the next goal doesn't read a stale profile.
   - `~/.claude/mama/patterns.md` (under its lock) — the user's choices this goal, and the goal's size and real duration/tokens from the metrics line (never guessed), per SKILL.md → Learning the user.
3. Clean up only what this run created: step worktrees, temp files, processes it started. The goal's own worktree: if the branch is pushed and the tree is clean, remove it (`git worktree remove`) — the branch stays, so the user can check it out; otherwise keep it and say where it is. Never stop the user's servers or containers.
4. Set plan status `done`.
5. Tell the user in a few lines: done, branch, PR status, where the overview is.
