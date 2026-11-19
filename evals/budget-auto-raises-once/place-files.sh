#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
g() { git -c user.name=eval -c user.email=eval@example.com "$@"; }
# main with one commit; tracking folders and eval helpers stay out of git, as mama sets it up.
git init -q -b main
printf '.claude/mama/\n.claude/worktrees/\n.eval-fixture/\n.eval-baseline/\n' >> .git/info/exclude
g add -A
g commit -qm "feat: normalize text"
# The goal's worktree on feat/text-stats, with step 1 (word_count) committed.
wt="$PWD/.claude/worktrees/mama-text-stats"
g worktree add -q -b feat/text-stats "$wt"
cp .eval-fixture/stats_s1.py "$wt/stats.py"
cp .eval-fixture/test_stats_s1.py "$wt/test_stats.py"
g -C "$wt" add -A
g -C "$wt" commit -qm "feat: count words"
sha=$(git -C "$wt" rev-parse --short HEAD)
for f in plan.md log.md; do
  sed -i "s|__WORKTREE__|$wt|; s|__S1SHA__|$sha|g" ".claude/mama/text-stats/$f"
done
# A pristine copy so graders can compare the goal files with the start.
mkdir -p .eval-baseline
cp -R .claude/mama/text-stats .eval-baseline/
