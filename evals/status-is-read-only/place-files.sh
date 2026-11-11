#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
g() { git -c user.name=eval -c user.email=eval@example.com "$@"; }
# main with one commit; tracking folders and eval helpers stay out of git, as mama sets it up.
git init -q -b main
printf '.claude/mama/\n.claude/worktrees/\n.eval-fixture/\n.eval-baseline/\n' >> .git/info/exclude
g add -A
g commit -qm "feat: greet cli"
# The goal's worktree on feat/verbose-flag, with step 1 (the --verbose option) committed.
wt="$PWD/.claude/worktrees/mama-add-verbose-flag"
g worktree add -q -b feat/verbose-flag "$wt"
cp .eval-fixture/cli_s1.py "$wt/cli.py"
g -C "$wt" commit -qam "feat: add --verbose option"
sha=$(git -C "$wt" rev-parse --short HEAD)
sed -i "s|__WORKTREE__|$wt|; s|__S1SHA__|$sha|" .claude/mama/add-verbose-flag/plan.md
# A pristine copy so graders can prove whether the goal files changed.
mkdir -p .eval-baseline
cp -R .claude/mama/add-verbose-flag .eval-baseline/
