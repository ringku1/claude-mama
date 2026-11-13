# mama — finish real work with Claude Code

[![test](https://github.com/ringku1/claude-mama/actions/workflows/test.yml/badge.svg)](https://github.com/ringku1/claude-mama/actions/workflows/test.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

You tell mama what you want done. It studies your code, asks you a few clear questions, makes a plan you approve, and then works until the job is finished and tested. You follow along in one short, plain-language page.

Works on **macOS, Linux and Windows**.

## Quick start

**1. Install** — pick **one** of the two ways below, not both.

**A. One line** (recommended). It also sets up git and Python if they're missing.

macOS or Linux (Terminal):

```bash
curl -fsSL https://raw.githubusercontent.com/ringku1/claude-mama/main/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/ringku1/claude-mama/main/install.ps1 | iex
```

**B. As a Claude Code plugin.** You still type `/mama`; the command menu lists it as `/mama:mama`, the long form to use only if another `/mama` exists. You need git and Python 3.8+ already; on Windows, also [Git for Windows](https://gitforwindows.org).

```bash
claude plugin marketplace add ringku1/claude-mama
claude plugin install mama@claude-mama
```

To switch from one way to the other, remove the first one before installing the second (see "Update or remove").

**2. Restart Claude Code.**

**3. Open your project in Claude Code and type** `/mama` followed by what you want:

```
/mama add a price filter to the course list
/mama the login button does nothing — see https://github.com/you/app/issues/42
/mama quick fix the typo on the pricing page
```

That's it. mama asks you questions, shows you its plan before it starts, and tells you when it's done.

Don't have Claude Code yet? Get it at [code.claude.com](https://code.claude.com).

## Everyday use

| Type | To |
| --- | --- |
| `/mama <what you want>` | start a piece of work |
| `/mama quick <small task>` | do a small task with fewer questions |
| `/mama status` | see progress and when it will finish |
| `/mama ask <question>` | ask about the work ("why did you choose X?") |
| `/mama test` | get steps to try it yourself, plus an automatic re-check |
| `/mama fix` | fix what a test or review found |
| `/mama change <what>` | change the plan |
| `/mama pause` · `/mama resume` · `/mama list` | pause, continue, or see all work |

Your progress page is `.claude/mama/<name>/overview.md` inside your project.

## Update or remove

Your notes in each project are kept either way.

| | One line | Plugin |
| --- | --- | --- |
| **Update** | paste the same install line again | `claude plugin marketplace update claude-mama`, then `claude plugin update mama@claude-mama`, then restart Claude Code (new releases raise the version in `.claude-plugin/plugin.json`) |
| **Remove** | macOS / Linux: `curl -fsSL https://raw.githubusercontent.com/ringku1/claude-mama/main/install.sh \| bash -s -- --uninstall`<br>Windows: `$env:MAMA_UNINSTALL=1; irm https://raw.githubusercontent.com/ringku1/claude-mama/main/install.ps1 \| iex` | `claude plugin uninstall mama@claude-mama` |

## If something goes wrong

| You see | Do this |
| --- | --- |
| `/mama` isn't recognised | Restart Claude Code. Still missing? Paste the install line again. |
| macOS: "Command Line Tools" window opened | Click Install, wait for it to finish, then paste the install line again. |
| Windows: "not available — open a new PowerShell window" | Close PowerShell, open a new one, paste the install line again. |
| Linux: asks for your password | It's installing git or Python for you; type your password. |
| mama stopped working after Python moved or was upgraded | Paste the install line again. |
| "the mama@claude-mama plugin is enabled" | You have both ways installed. Keep one: uninstall the plugin, or remove the one-line install. |
| A problem with mama's checks at the end of a turn | Look in `~/.claude/mama/hook-errors.log`; the hooks write their errors there and never block you. |

---

## Details

### What the installer does

1. Installs anything missing:
   - **git** and **Python 3.8+**: Homebrew or Apple's Command Line Tools on macOS, your package manager on Linux (apt, dnf, yum, pacman, zypper or apk), `winget` on Windows.
   - **Windows only:** Git for Windows, which also gives Claude Code the Bash tool it needs there.
2. Downloads mama to `~/.claude/skills/mama` (`%USERPROFILE%\.claude\skills\mama` on Windows; `$CLAUDE_CONFIG_DIR/skills/mama` when that is set). If something else is already there, it's moved aside, not deleted.
3. Registers three Claude Code hooks in `~/.claude/settings.json` (or `$CLAUDE_CONFIG_DIR/settings.json`). It keeps your other settings; the first install saves your original file as `settings.json.bak`. The hooks call Python by its full path, so they work in any shell.

It stops with nothing changed if `settings.json` isn't valid JSON, and refuses to add hooks when the mama plugin is enabled. When an update fails, the message says why (local changes, no connection, and so on).

### How it works

- **Research first.** Parallel read-only agents map the code the work touches, and every case it must handle, before asking anything.
- **Questions that pin down what you expect.** Multiple choice, each with a recommended answer, covering a fixed checklist: the outcome, who uses it, edge cases, look and wording, data, speed, what must not change, and how it's tested. Then it shows you "here's exactly what you'll get" as concrete examples to confirm or correct before planning. It remembers your preferences (`~/.claude/mama/patterns.md`).
- **A wide plan, run in parallel.** Steps own separate files, so many run at once. Time estimates come from the longest chain of dependent steps.
- **Evidence, not claims.** A step is done when its check passes. After building, it hunts for bugs (a code review plus a check of every promised example and edge case), fixes what it can reproduce, and hunts again until a round comes back clean, all before anything is pushed. The work closes only when a final check passes.
- **Measured cost and time.** It reads real token spend. At 70% of the budget it asks you, or, when running on its own, raises the budget up to 2× for work you already approved and tells you. Time estimates are scaled by how long your past goals really took.
- **Safe by default.**
  - Each piece of work gets its own git branch and worktree.
  - It stops at `git push` and opens a pull request only if you say so.
  - It never touches your running servers or shared databases, and adds no AI credit lines to commits.

### Where things live

- **In each project:** `.claude/mama/` holds an `overview.md` (for you), plus `plan.md` and `log.md` (for mama) per piece of work, and `profile.md` and `lessons.md` for the project. mama keeps these out of git automatically.
- **Your machine:** `~/.claude/mama/patterns.md`, how you like to work (you can edit it; the version before mama's last change is kept as `patterns.md.bak`), and `activity.log`, which records which session wrote to which piece of work. It decides which work the hooks treat as a session's own, and cost counts the sessions recorded there (plus a transcript scan only for work started before `activity.log` existed).
- **The skill:** `SKILL.md` (the flow), `rules/`, `scripts/`, `hooks/`, `templates/`.

### Settings you may want to change

- **Subagent model:** `model: opus`, `effort: medium`, set in `rules/agents.md`.
- **Agents at once:** up to 8 that build (fewer if CPU or memory is short) and 8 read-only, set in `scripts/resources.py`.
- **Budgets:** S up to 300k tokens, M up to 1M, L a number with a unit you set (`L 800k`, `L 1.5M`). The references in `rules/planning.md` come from real runs on one project; yours are learned in `lessons.md`.

### Not supported

claude.ai chat and Claude Code on the web: mama needs your personal skills folder and its hooks, which those don't load.

### Development

Run all the tests with `python3 tests/test_mama.py`. They run every script and hook in a throwaway home folder and never touch your real `~/.claude`. CI runs them on Linux (Python 3.8 and current), macOS and Windows, and also tests the one-line installers there.

Issues and pull requests are welcome. Keep changes small and add a test for any script or hook change. `SKILL.md` and `rules/` are read by the model on every run, so keep them short and current.

## License

[MIT](LICENSE)
