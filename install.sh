#!/usr/bin/env bash
# mama installer for macOS and Linux. Paste into a terminal:
#
#   curl -fsSL https://raw.githubusercontent.com/ringku1/claude-mama/main/install.sh | bash
#
# It installs what's missing (git, Python 3.8+), downloads mama to ~/.claude/skills/mama
# ($CLAUDE_CONFIG_DIR/skills/mama when that is set),
# and registers its hooks with Claude Code. Run the same line again to update.
# Remove:  curl -fsSL https://raw.githubusercontent.com/ringku1/claude-mama/main/install.sh | bash -s -- --uninstall
set -euo pipefail

REPO="${MAMA_REPO:-https://github.com/ringku1/claude-mama.git}"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/mama"
export GIT_TERMINAL_PROMPT=0  # a bad URL fails instead of asking for a password

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
  if [ -n "$(git -C "$DEST" status --porcelain 2>/dev/null)" ]; then
    fail "files in $DEST were changed locally, so it wasn't updated. Run  git -C \"$DEST\" stash  (or remove the folder), then paste the command again."
  fi
  git -C "$DEST" fetch -q 2>/dev/null \
    || fail "couldn't reach $(git -C "$DEST" remote get-url origin 2>/dev/null || echo "$REPO") — check your internet connection and paste the command again."
  git -C "$DEST" merge -q --ff-only '@{upstream}' >/dev/null 2>&1 \
    || fail "$DEST has local commits (or is off its branch), so it wasn't updated. Remove the folder (or reset it), then paste the command again."
else
  if [ -e "$DEST" ] || [ -L "$DEST" ]; then
    old="$DEST.old-$(date +%Y%m%d%H%M%S)"
    mv "$DEST" "$old"
    say "moved the previous $DEST to $old"
  fi
  say "downloading"
  if ! err=$(git clone -q "$REPO" "$DEST" 2>&1); then
    rm -rf "$DEST"
    case "$err" in
      *"not found"*|*"does not exist"*|*"Authentication"*) fail "couldn't download $REPO — it doesn't exist or isn't public." ;;
      *) fail "couldn't download $REPO — check your internet connection and paste the command again." ;;
    esac
  fi
fi

if ! out=$("$PY" "$DEST/install.py" 2>&1); then
  fail "registering the hooks failed: $(printf '%s\n' "$out" | tail -n 1 | sed 's/^mama: //')"
fi
say "ready. Restart Claude Code, open your project, and type:  /mama <what you want done>"
