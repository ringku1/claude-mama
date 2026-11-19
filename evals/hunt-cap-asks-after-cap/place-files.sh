#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
g() { git -c user.name=eval -c user.email=eval@example.com "$@"; }
# main with one commit; tracking folders and eval helpers stay out of git, as mama sets it up.
git init -q -b main
printf '.claude/mama/\n.claude/worktrees/\n.eval-fixture/\n.eval-baseline/\n' >> .git/info/exclude
g add -A
g commit -qm "feat: cart total"
# The goal's worktree on feat/parse-prices: step 1 (parse_price), then hunt 1's fix, which
# drops the sign of refunds — the bug hunt 2 reported.
wt="$PWD/.claude/worktrees/mama-parse-prices"
g worktree add -q -b feat/parse-prices "$wt"
cp .eval-fixture/price_s1.py "$wt/price.py"
cp .eval-fixture/test_price_s1.py "$wt/test_price.py"
g -C "$wt" add -A
g -C "$wt" commit -qm "feat: parse prices as shown on the site"
s1=$(git -C "$wt" rev-parse --short HEAD)
cp .eval-fixture/price_fix.py "$wt/price.py"
cp .eval-fixture/test_price_fix.py "$wt/test_price.py"
g -C "$wt" commit -qam "fix: parse prices with a thousands separator"
fix=$(git -C "$wt" rev-parse --short HEAD)
for f in plan.md log.md; do
  sed -i "s|__WORKTREE__|$wt|; s|__S1SHA__|$s1|g; s|__FIXSHA__|$fix|g" ".claude/mama/parse-prices/$f"
done
# A pristine copy so graders can compare the goal files with the start.
mkdir -p .eval-baseline
cp -R .claude/mama/parse-prices .eval-baseline/
