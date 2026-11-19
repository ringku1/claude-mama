#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
g() { git -c user.name=eval -c user.email=eval@example.com "$@"; }
# main with one commit; tracking folders, eval helpers and the local remote stay out of git.
git init -q -b main
printf '.claude/mama/\n.claude/worktrees/\n.eval-fixture/\n.eval-baseline/\n.eval-remote.git/\n' >> .git/info/exclude
g add -A
g commit -qm "feat: shout helper"
# A local bare origin so the run can push; origin/main exists.
git init -q --bare -b main .eval-remote.git
git remote add origin "$PWD/.eval-remote.git"
git push -q origin main
git fetch -q origin
# The approved goal's worktree on feat/text-helpers, no commits on it yet.
wt="$PWD/.claude/worktrees/mama-add-text-helpers"
g worktree add -q --no-track -b feat/text-helpers "$wt" origin/main
sed -i "s|__WORKTREE__|$wt|" .claude/mama/add-text-helpers/plan.md
# A pristine copy so graders can compare the goal files with the start.
mkdir -p .eval-baseline
cp -R .claude/mama/add-text-helpers .eval-baseline/
