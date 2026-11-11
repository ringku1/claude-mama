#!/usr/bin/env bash
# mama installer for macOS and Linux. Paste into a terminal:
#
#   curl -fsSL https://raw.githubusercontent.com/ringku1/claude-mama/main/install.sh | bash
#
# It installs what's missing (git, Python 3.8+), downloads mama to ~/.claude/skills/mama,
# and registers its hooks with Claude Code. Run the same line again to update.
# Remove:  curl -fsSL https://raw.githubusercontent.com/ringku1/claude-mama/main/install.sh | bash -s -- --uninstall
set -euo pipefail

REPO="${MAMA_REPO:-https://github.com/ringku1/claude-mama.git}"
DEST="$HOME/.claude/skills/mama"

say() { printf '%s\n' "mama: $*"; }
fail() { printf '%s\n' "mama: $*" >&2; exit 1; }

find_python() {
  PY=""
  for p in python3 python; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
      PY=$(command -v "$p"); return 0
    fi
  done
  return 1
}
has_git() { command -v git >/dev/null 2>&1 && git --version >/dev/null 2>&1; }

install_missing() {
  say "installing $* (you may be asked for your password)"
  local sudo=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && sudo="sudo"
  if [ "$(uname)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      brew install "$@"
    else
      xcode-select --install >/dev/null 2>&1 || true
      fail "Apple's installer for git and Python just opened. Finish it, then paste the same command again."
    fi
  elif command -v apt-get >/dev/null 2>&1; then $sudo apt-get update -qq && $sudo apt-get install -y -qq python3 git
  elif command -v dnf >/dev/null 2>&1; then $sudo dnf install -y -q python3 git
  elif command -v yum >/dev/null 2>&1; then $sudo yum install -y -q python3 git
  elif command -v pacman >/dev/null 2>&1; then $sudo pacman -Sy --noconfirm --needed python git
  elif command -v zypper >/dev/null 2>&1; then $sudo zypper --non-interactive install python3 git
  elif command -v apk >/dev/null 2>&1; then $sudo apk add --quiet python3 git
  else
    fail "please install git and Python 3.8+ with your package manager, then paste the same command again."
  fi
}

if [ "${1:-}" = "--uninstall" ]; then
  if [ -e "$DEST" ] || [ -L "$DEST" ]; then
    find_python && "$PY" "$DEST/install.py" --remove >/dev/null || true
    rm -rf "$DEST"
  fi
  say "removed. Your goal notes in each project (.claude/mama) and ~/.claude/mama are kept."
  exit 0
fi

missing=()
has_git || missing+=(git)
find_python || missing+=(python3)
if [ ${#missing[@]} -gt 0 ]; then
  install_missing "${missing[@]}"
  hash -r
  has_git || fail "git still isn't available — install it, then paste the same command again."
  find_python || fail "Python 3.8+ still isn't available — install it, then paste the same command again."
fi

mkdir -p "$(dirname "$DEST")"
if [ -d "$DEST/.git" ]; then
  say "updating"
  git -C "$DEST" pull --ff-only -q || fail "couldn't update $DEST (local changes?). Remove it and paste the command again."
else
  if [ -e "$DEST" ] || [ -L "$DEST" ]; then
    old="$DEST.old-$(date +%Y%m%d%H%M%S)"
    mv "$DEST" "$old"
    say "moved the previous $DEST to $old"
  fi
  say "downloading"
  git clone -q "$REPO" "$DEST"
fi

"$PY" "$DEST/install.py" >/dev/null
say "ready. Restart Claude Code, open your project, and type:  /mama <what you want done>"
