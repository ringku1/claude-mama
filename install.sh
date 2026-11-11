#!/usr/bin/env bash
# Install mama for Claude Code: puts the skill at ~/.claude/skills/mama and registers its
# three hooks (PreCompact, SessionStart on compact, Stop) in ~/.claude/settings.json.
# Safe to re-run: existing mama hooks are replaced, everything else in settings.json is kept,
# and the previous settings.json is saved as settings.json.bak.
#   ./install.sh            install / update
#   ./install.sh --remove   remove the hooks (the skill folder and your goal files stay)
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd -P)
dest="$HOME/.claude/skills/mama"
settings="$HOME/.claude/settings.json"

command -v python3 >/dev/null || { echo "mama needs python3 (3.8+)"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' || { echo "mama needs python3 3.8+"; exit 1; }
command -v git >/dev/null || { echo "mama needs git"; exit 1; }

if [ "${1:-}" != "--remove" ]; then
  mkdir -p "$HOME/.claude/skills"
  if [ "$(cd "$dest" 2>/dev/null && pwd -P)" != "$here" ]; then
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      echo "$dest already exists and is not this folder — move it away first."; exit 1
    fi
    ln -s "$here" "$dest"
    echo "linked $dest -> $here"
  fi
fi

python3 - "$settings" "${1:-}" <<'EOF'
import json, os, shutil, sys
path, mode = sys.argv[1], sys.argv[2]
cmd = "python3 ~/.claude/skills/mama/hooks/mama-hook.py "
want = {
    "PreCompact": {"hooks": [{"type": "command", "command": cmd + "precompact", "timeout": 10}]},
    "SessionStart": {"matcher": "compact", "hooks": [{"type": "command", "command": cmd + "sessionstart", "timeout": 10}]},
    "Stop": {"hooks": [{"type": "command", "command": cmd + "stop", "timeout": 10}]},
}
s = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    shutil.copy2(path, path + ".bak")
hooks = s.setdefault("hooks", {})
for event, entry in want.items():
    kept = [e for e in hooks.get(event, []) if "mama-hook.py" not in json.dumps(e)]
    hooks[event] = kept if mode == "--remove" else kept + [entry]
    if not hooks[event]:
        del hooks[event]
if not hooks:
    del s["hooks"]
os.makedirs(os.path.dirname(path), exist_ok=True)
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
print(("removed" if mode == "--remove" else "registered") + " mama hooks in " + path)
EOF

[ "${1:-}" = "--remove" ] || echo "done — restart Claude Code, then type /mama <your goal> in a git repo."
