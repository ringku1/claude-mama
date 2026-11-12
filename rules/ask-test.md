# Asking about and testing a goal's work

Read for `/mama ask` and `/mama test`.

## Asking about the work

`/mama ask [<slug>] <question>`, e.g. "why did you pick a soft delete?", "which files changed?", "how was the upload limit tested?". Works on open and closed goals, from any session.

- **Which goal:** the slug given; else this session's goal; else the most recently updated goal in the store — name it in the first line of the answer ("About storage-page:"). Unsure between several → list them and ask.
- **Sources, cheapest first:** `overview.md` → `plan.md` (criteria evidence, step verify and notes) → `log.md` (`grep '^D'` decisions, `^F` findings, `^Q` questions) → the code: the goal's worktree if it still exists, else `git -C <main checkout> log/diff <base>...<branch>` (the branch outlives the worktree) → `tests.md` → `lessons.md`. Read the code only when the files don't answer it.
- **Answer** in a few plain lines, citing where it comes from (a decision and its reason, a commit, a `file:line`, a test). Say plainly what the record doesn't show — never fill gaps with a guess.
- **Read-only:** no edits to the goal's files or code (a log line after close would stretch its measured time). If the answer shows something is wrong or missing, say so and offer `/mama change <slug> …` (open goal) or a new goal (closed one) — don't act until the user picks.

## Testing the work

`/mama test [<slug>] [<what>]`, e.g. "test the storage page upload", "test empty folders", or just `test` for the whole goal. Goal choice as in `ask`.

1. **Scope:** the criteria and steps that match `<what>` (all criteria if none given). Read their verify, evidence, the decisions behind them, and the code they touched.
2. **Manual test guide for the user** — they test in their own running app; never start, stop, reseed or migrate it. Per scenario: where (URL / screen / command, which branch must be running), any setup data, the exact steps, the expected result in plain words. Cover the happy path, edges and errors the code actually handles (empty, limits, permissions), and say what is out of scope. Tell them which branch to run if theirs isn't it.
3. **Our own check, in parallel:** rerun the automated tests that prove those criteria (narrow, not the full suite), in the goal's worktree — or, if it's gone, a temporary one `.claude/worktrees/mama-<slug>-test` on the branch, removed after. Shared services under `scripts/lock.py <store>/.heavy.lock`. Report pass/fail with the command.
4. **Record** in `<slug>/tests.md` (not log.md — a closed goal's log stays closed): date, scope, scenarios given, automated result, and later what the user reports.
5. **The user reports back** ("upload of 0-byte file fails"): reproduce or read the code to confirm, add it to `tests.md`, then offer the fix via `/mama change <slug>` — on a closed goal that reopens it (`rules/changes.md` step 0) so the fix gets steps, commits, log and a new close. Don't fix before they pick.
