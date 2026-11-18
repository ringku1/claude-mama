# Goals on disk: isolation, guards, learning

Read at intake (any goal, quick included) and at re-entry. `/mama status`, `ask`, `test`, `doc` and `list` don't need it.

## Several goals at once

The user may run several goals in parallel sessions. Each goal is isolated:
- **Its own tracking folder** `<store>/<slug>/`; a session only ever writes its own goal's files. Remember your slug — it's in every re-entry.
- **Its own worktree** for build/fix/mixed goals (and research goals that commit a deliverable): `<main checkout>/.claude/worktrees/mama-<slug>/` on the goal's branch, recorded in the plan header. All code work, commands and agents for the goal happen there — prefix shell commands with `cd <worktree> &&` and use absolute paths for file tools. Research-only goals work read-only in the main checkout. Never switch branches in the main checkout; it belongs to the user.
- **Shared, so coordinated**:
  - Shared files (`profile.md`, `lessons.md`, `info/exclude`, `patterns.md`): create only if absent (`set -C`), add exclude lines only if missing, and append/edit under `scripts/lock.py <store>/.shared.lock` (`~/.claude/mama/.patterns.lock` for patterns).
  - Verifies that touch shared services (database, Redis), every full gate, and heavy runs (build, e2e) go under `scripts/lock.py <store>/.heavy.lock <cmd>` (wrap shell syntax in `bash -c '…'`) so goals don't collide.
  - The agent limit (`scripts/resources.py <ready> <store> <own slug>`) subtracts other goals' running steps.
  - `git fetch` and `git push` run as `git -C <main checkout> ...` — refs are shared with the worktree, and it works for any remote URL.

**Same branch, two goals:** a branch can be checked out only once, so a goal that targets a branch another open goal works on shares that goal's worktree and runs after it, never in parallel with it. Say in both overviews that one push carries both goals' commits, and never push one goal's commits while the other has uncommitted work in the tree.

## Which session owns a goal

Every write through `log.py` / `plan-set.py` / `new-goal.py` records which session worked on which goal (`~/.claude/mama/activity.log`, from `CLAUDE_CODE_SESSION_ID`). That record — not guessing — tells the hooks which goal is this session's (a goal no record ties to this session is never claimed) and tells `spend.py` whose tokens count: it counts the sessions recorded there, plus a transcript scan only for goals started before `activity.log` existed. Writes need `CLAUDE_CODE_SESSION_ID` (Claude Code sets it); without it the scripts warn and record nothing. Writing goal files any other way leaves the goal unowned and unmeasured.

Waiting for the user is measured, so estimates calibrate on active time: `plan-set --header status=waiting` logs `E waiting` and the switch back logs `E resume` on their own; questions are `Q` lines and their answers `D … tag: user`.

## Guards (scripts and hooks enforce these — don't work around them)

- `plan-set.py`:
  - stamps step start/end itself, warns on a step started before its deps, and refuses a typed end time before the start (a step that crossed midnight: `end=now`);
  - refuses `status=approved|running` without a mode;
  - refuses a full goal's first approval until research, the expectations checklist and the playback are logged (`E research …`, `E expectations …`, `E playback …`) — and, for a build, fix or mixed goal, the database decision (`E db …`) before the playback — and without the size (`budget=…` in the same call); a quick goal's until its one-line playback is;
  - refuses `status=done` until `close-check.py` passes;
  - keeps `budget` as `~<n>k / S|M|L <n>k|M` (e.g. `L 800k`, `L 1.5M`) and refuses a raise past 2× the `approved:` size without a `D budget … (tag: user)`;
  - allows `pr` only as `ask-at-end | auto | none | declined | <url>`;
  - fills the template's blank rows on `S+`/`C+`, parks ideas with `P+`, keeps the overview's Status line in sync, prints the estimate (critical path, sum, steps at once, likely time and tokens), and reminds you of the Trello start comment.
- `close-check.py` checks criteria evidence, step times, placeholders, Trello, metrics, patterns, profile (or `E profile none`), and, for code goals, a last bug-hunt round with 0 real bugs, every round naming `/code-review` (high on a full goal), and a push after the last hunt. It refuses this goal's commits (on the branch since `started:`, also when base == branch) with attribution lines or loop internals (mama, plan.md, or step/criterion references like "step S3" / "criterion C2" — bare IDs aren't refused). The overview is checked (close and every turn) for this goal's own step/log IDs, file:line refs (URLs and host:port don't count) and length over one screen.
- The Stop hook measures the goal's real token spend into the plan header at every turn end (`scripts/spend.py`), and blocks, listing every problem, when your goal:
  - is `running` at ≥70% of its budget (autonomous mode: raise it yourself within 2× of the `approved:` size and go on — `rules/loop.md` → Budget);
  - has a bug hunt that isn't converging (a round with no fewer real bugs than the one before; ask: simplify / fix again / deliver with known issues);
  - says `running` without a final `E dispatch …` or `E wait …` line;
  - is a quick goal past 300k tokens or 30 active minutes with no `D … quick …` answer (offer a full goal);
  - reached a milestone (a ★ step done, a step blocked, status, PR or scope changed) after `overview.md` was last written;
  - has a user decision with no learning after it (not in quick mode);
  - says `done` while the close check fails.

  It blocks when a problem appears or the list changes, never twice for an identical list. Fix what it lists, don't argue with it. Hook failures never block; they go to `~/.claude/mama/hook-errors.log`.

## Learning the user

`patterns.md` makes each goal fit the user better than the last.
- **Use** (intake, questions, planning): a learned pattern sets the recommended option, settles a question whose answer it already knows (say so in one line: "Using your usual: X"), and shapes the plan and overview. The base branch is still always asked. The user's explicit instructions and repo rules beat any pattern.
- **Learn immediately** when the user corrects your work or plan, overrides a recommendation, or states a preference: add or update a line. Don't wait for close — that's when it's fresh.
- **Learn at close**: their choices this goal (options, mode, PR), goal size, estimate vs actual.
- **Write it with** `scripts/learn.py seen|contra|stated|goal "<pattern>"` — it locks, counts, dates and promotes; never hand-edit. After any user decision: learn.py, or log `E learn none`.
- **Format**: one line per pattern — `<pattern> — <n>/<m> — last <date>`. Learned at ≥3 consistent observations, else it stays under "Watching". A preference the user states outright is learned at once — write `stated` instead of a count. A contradiction lowers the count; two contradictions in a row move a learned line back to Watching; one contradicted down to 0 is deleted.
- **Never** record secrets, client data, or repo facts (those belong in `profile.md` / `lessons.md`).
