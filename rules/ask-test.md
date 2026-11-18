# Asking about and testing a goal's work

## Asking about the work

`/mama ask [<slug>] <question>` works on open and closed goals, from any session.

- **Which goal:** the slug given, else this session's goal, else the store's most recently updated goal, named in the first line ("About storage-page:"). Unsure between several → list them and ask.
- **Sources, cheapest first:** `overview.md` → `plan.md` (criteria evidence, step verify and notes) → `log.md` (`grep '^D'` decisions, `^F` findings, `^Q` questions) → code (the worktree, else `git -C <main checkout> log/diff <base>...<branch>`; the branch outlives the worktree) → `tests.md` → `lessons.md`. Read code only when the files don't answer.
- **Answer** in a few plain lines, citing the source (decision and reason, commit, `file:line`, test). Say what the record doesn't show; never guess.
- **Read-only:** never edit the goal's files or code (a log line after close stretches its measured time). If something is wrong or missing, say so and offer `/mama change <slug> …` (open goal) or a new goal (closed); act only once the user picks.

## Testing the work

`/mama test [<slug>] [<what>]` (bare `test`: the whole goal). Goal choice as in `ask`.

1. **Scope:** criteria and steps matching `<what>` (none given: all criteria). Read their verify, evidence, decisions and touched code.
2. **Manual test guide:** the user tests in their own running app; never start, stop, reseed or migrate it. Per scenario: where (URL / screen / command, branch that must run), setup data, exact steps, expected result in plain words. Cover the happy path, edges and errors the code handles (empty, limits, permissions); name what is out of scope.
3. **Our check, in parallel:** rerun the narrow tests proving those criteria (not the full suite) in the goal's worktree, or if gone a temporary `.claude/worktrees/mama-<slug>-test` on the branch, removed after. Shared services under `scripts/lock.py <store>/.heavy.lock`. Report pass/fail with the command.
4. **Record** in `<slug>/tests.md`, not log.md (a closed goal's log stays closed): date, scope, scenarios, automated result, later the user's report.
5. **User reports a problem:** confirm it (reproduce or read the code), add it to `tests.md`, offer the fix via `/mama change <slug>`; on a closed goal this reopens it (`rules/changes.md` step 0). Don't fix before they pick.
