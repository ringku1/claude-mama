# mama — a goal-based work loop for Claude Code

[![test](https://github.com/ringku1/claude-mama/actions/workflows/test.yml/badge.svg)](https://github.com/ringku1/claude-mama/actions/workflows/test.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`mama` is a [Claude Code](https://code.claude.com) skill that runs a piece of work to completion. You give it a goal. It researches the code, asks you one batch of questions, plans, and then loops build → verify → fix with parallel agents until every done-criterion has evidence.

Everything is tracked in plain files, so a goal survives compaction, crashes and new sessions. You follow along in one short, plain-language `overview.md`.

```
/mama add price filters to the course catalog
/mama https://github.com/<org>/<repo>/issues/42
/mama quick fix the typo on the pricing page
```

## What it does

- **Research before questions.** Parallel read-only agents map every part of the code the work touches, and every case it must handle (roles, states, limits, errors, existing data), before anything is asked.
- **Questions once, with recommendations.** One batch, multiple choice, citing what research found. It learns your answers over time (`~/.claude/mama/patterns.md`).
- **Plans wide, runs in parallel.** Steps own separate files, so as many as possible run at once. A quick first step writes any shared interface. The estimate is the critical path (the longest chain of dependent steps), not the sum.
- **Evidence, not claims.** A step is done when its verify command passes, and a goal closes only when a close check passes.
- **Measured cost.** Real token spend is read from the session transcripts. It stops and asks at 70% of the budget.
- **Stays in its lane.**
  - Each goal gets its own git worktree and branch.
  - Delivery ends at `git push`; a PR is opened only with your OK.
  - It never touches your running servers or shared databases.
  - Commits carry no AI attribution lines.

## Requirements

- Claude Code (CLI or IDE extension) on **Linux, macOS or Windows**.
- Python 3.8+ and `git`. On Windows, Claude Code's Bash tool also needs [Git for Windows](https://git-scm.com/download/win) (Git Bash).
- Work happens inside a git repository.

It does not run in claude.ai chat or in Claude Code on the web: it needs your user-level skills and its hooks.

## Install

```bash
git clone https://github.com/ringku1/claude-mama.git
cd claude-mama
python3 install.py        # Windows: py install.py
```

`install.py` does two things:
- links the folder to `~/.claude/skills/mama`. That's a symlink on Linux and macOS, and a directory junction on Windows, which needs no admin rights.
- adds three hooks (PreCompact, SessionStart on compact, Stop) to `~/.claude/settings.json`. It writes them with the absolute path of the Python you ran it with, so they don't depend on a shell or on `python3` being on PATH. It keeps your other settings and saves the old file as `settings.json.bak`.

Restart Claude Code afterwards. To update, run `git pull`. Re-run the installer only if you moved the folder or your Python. To remove the hooks, run `python3 install.py --remove`.

## Commands

| Command | What it does |
| --- | --- |
| `/mama <goal>` | Start a goal. Input can be text, a file, a Trello card or a GitHub issue/PR. |
| `/mama quick <task>` | A small task (≈ under 30 min): fewer questions, a 3-line overview. |
| `/mama status` | Progress, running steps, estimated finish, blockers. |
| `/mama ask [slug] <question>` | Ask about a goal's work ("why soft delete?", "how was X tested?"). |
| `/mama test [slug] [what]` | A manual test guide for you, plus an automated re-check. |
| `/mama fix [slug]` | Start a fix goal from what another goal found. |
| `/mama change [slug] <what>` | Change the plan of a running or finished goal. |
| `/mama pause` · `abort` · `list` · `resume <slug>` | Goal control. |

## Where things live

- **The skill:** `SKILL.md` (the flow), `rules/` (read when the flow points to them), `scripts/` (state writers and checks), `hooks/`, `templates/`.
- **Per repo:** goals live in `<repo>/.claude/mama/<slug>/`, as `overview.md`, `plan.md`, `log.md` and, after `/mama test`, `tests.md`. The store also holds `profile.md` (repo facts) and `lessons.md` (what past goals taught). mama adds `.claude/mama/` and `.claude/worktrees/` to `.git/info/exclude`, so none of it is committed.
- **Per user:**
  - `~/.claude/mama/patterns.md`: how you like to work. Plain language, and you can edit it.
  - `~/.claude/mama/activity.log`: which session worked on which goal, used to measure spend.

## Defaults you may want to change

- **Subagent model:** every subagent runs as `model: opus`, `effort: medium` (`rules/agents.md`).
- **Agent limits:** at most 8 building agents (fewer if CPU or memory is short) and 8 read-only agents (`scripts/resources.py`).
- **Budgets:** S ≤ 300k tokens, M ≤ 1M, L takes a number you set. The size references in `rules/planning.md` come from real runs on one monorepo; your numbers will differ and are learned in `lessons.md`.

## Tests

```bash
python3 tests/test_mama.py
```

The tests run every script and hook in a throwaway home folder and never touch your real `~/.claude`. CI runs them on Linux (Python 3.8 and current), macOS and Windows on every push.

## Contributing

Issues and pull requests are welcome. Keep changes small, run `python3 tests/test_mama.py`, and add a test for any script or hook behaviour you change. The skill's text (`SKILL.md`, `rules/`) is read by the model on every run, so keep it short and current — say what to do, not its history.

## License

[MIT](LICENSE)
