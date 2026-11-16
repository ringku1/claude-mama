#!/usr/bin/env bash
set -eu
cp -R "$(dirname "$0")/files/." .
# A tiny git repo on main with one commit, as a user's checkout would be.
git init -q -b main
git -c user.name=eval -c user.email=eval@example.com add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "feat: greet cli"
