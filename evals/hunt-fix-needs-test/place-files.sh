#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
g() { git -c user.name=eval -c user.email=eval@example.com "$@"; }
# main with one commit; tracking folders and eval helpers stay out of git, as mama sets it up.
git init -q -b main
printf '.claude/mama/\n.claude/worktrees/\n.eval-fixture/\n.eval-baseline/\n' >> .git/info/exclude
g add -A
g commit -qm "feat: cart total"
# The goal's worktree on feat/parse-prices, with step 1 (parse_price, carrying the bug) committed.
wt="$PWD/.claude/worktrees/mama-parse-prices"
g worktree add -q -b feat/parse-prices "$wt"
cp .eval-fixture/price.py .eval-fixture/test_price.py "$wt/"
g -C "$wt" add -A
g -C "$wt" commit -qm "feat: parse prices as shown on the site"
sha=$(git -C "$wt" rev-parse --short HEAD)
sed -i "s|__WORKTREE__|$wt|; s|__S1SHA__|$sha|g" .claude/mama/parse-prices/plan.md
sed -i "s|__S1SHA__|$sha|g" .claude/mama/parse-prices/log.md
# A pristine copy so graders can compare the goal files with the start.
mkdir -p .eval-baseline
cp -R .claude/mama/parse-prices .eval-baseline/
