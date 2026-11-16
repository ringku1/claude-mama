#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
g() { git -c user.name=eval -c user.email=eval@example.com "$@"; }
# main with one commit; tracking folders and eval helpers stay out of git, as mama sets it up.
git init -q -b main
printf '.claude/mama/\n.claude/worktrees/\n.eval-fixture/\n.eval-baseline/\n' >> .git/info/exclude
g add -A
g commit -qm "feat: user profiles"
# The closed goal's worktree on feat/delete-user, kept (no remote to push to), with its one commit.
wt="$PWD/.claude/worktrees/mama-delete-user"
g worktree add -q -b feat/delete-user "$wt"
cp .eval-fixture/002_user_deleted_at.sql "$wt/migrations/"
cp .eval-fixture/app_deleted.py "$wt/app.py"
cp .eval-fixture/test_app_deleted.py "$wt/test_app.py"
g -C "$wt" add -A
g -C "$wt" commit -qm "feat: let admins delete a user, restorable"
sha=$(git -C "$wt" rev-parse --short HEAD)
sed -i "s|__WORKTREE__|$wt|; s|__SHA__|$sha|g" .claude/mama/delete-user/plan.md
sed -i "s|__SHA__|$sha|g" .claude/mama/delete-user/log.md
# A pristine copy so graders can prove whether the goal files changed.
mkdir -p .eval-baseline
cp -R .claude/mama/delete-user .eval-baseline/
