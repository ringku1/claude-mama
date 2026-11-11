#!/usr/bin/env python3
"""Install mama for Claude Code on Linux, macOS or Windows.

  python3 install.py            install / update   (Windows: py install.py)
  python3 install.py --remove   remove the hooks; the skill folder and your goal files stay

1. Puts the skill at ~/.claude/skills/mama (%USERPROFILE%\\.claude\\skills\\mama on Windows):
   a symlink to this folder (a directory junction on Windows), or nothing if it's already there.
2. Registers its three hooks (PreCompact, SessionStart on compact, Stop) in ~/.claude/settings.json
   in exec form — this Python's absolute path plus the hook script's — so no shell, `~` or
   `python3`-vs-`python` differences matter. Other settings are kept; the old file is saved
   as settings.json.bak. Safe to re-run.
"""
import json
import os
import shutil
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):  # print "—" safely on a cp1252 Windows console
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.realpath(__file__))
CLAUDE = os.path.normpath(os.path.join(os.path.expanduser("~"), ".claude"))  # one separator style (mklink reads "/x" as a switch)
DEST = os.path.join(CLAUDE, "skills", "mama")
SETTINGS = os.path.join(CLAUDE, "settings.json")
EVENTS = {"PreCompact": ("precompact", None), "SessionStart": ("sessionstart", "compact"), "Stop": ("stop", None)}


def link_skill():
    if os.path.realpath(DEST) == HERE:
        return
    if os.path.lexists(DEST):
        sys.exit(f"{DEST} already exists and is not this folder — move it away first.")
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    if os.name == "nt":  # a junction needs no admin rights or developer mode
        r = subprocess.run(["cmd", "/c", "mklink", "/J", DEST, HERE], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"could not link {DEST}: {r.stdout}{r.stderr}")
    else:
        os.symlink(HERE, DEST)
    print(f"linked {DEST} -> {HERE}")


def is_mama(entry):
    return "mama-hook.py" in json.dumps(entry)


def update_hooks(remove):
    settings = {}
    if os.path.exists(SETTINGS):
        with open(SETTINGS, encoding="utf-8") as f:
            settings = json.load(f)
        shutil.copy2(SETTINGS, SETTINGS + ".bak")
    hooks = settings.setdefault("hooks", {})
    hook = os.path.join(DEST, "hooks", "mama-hook.py")
    for event, (mode, matcher) in EVENTS.items():
        kept = [e for e in hooks.get(event, []) if not is_mama(e)]
        if not remove:
            entry = {"hooks": [{"type": "command", "command": sys.executable, "args": [hook, mode], "timeout": 10}]}
            if matcher:
                entry = {"matcher": matcher, **entry}
            kept.append(entry)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    if not hooks:
        settings.pop("hooks")
    os.makedirs(CLAUDE, exist_ok=True)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    os.replace(tmp, SETTINGS)
    print(("removed" if remove else "registered") + f" mama hooks in {SETTINGS}")


def main():
    if sys.version_info < (3, 8):
        sys.exit("mama needs Python 3.8+")
    if not shutil.which("git"):
        sys.exit("mama needs git on PATH")
    remove = "--remove" in sys.argv[1:]
    if not remove:
        link_skill()
    update_hooks(remove)
    if not remove:
        print("done — restart Claude Code, then type /mama <your goal> in a git repo.")
        if os.name == "nt":
            print("Windows: Claude Code's Bash tool needs Git for Windows (Git Bash).")


if __name__ == "__main__":
    main()
