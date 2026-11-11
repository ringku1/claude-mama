#!/usr/bin/env python3
"""Install mama for Claude Code on Linux, macOS or Windows.

  python3 install.py            install / update   (Windows: py install.py)
  python3 install.py --remove   remove the hooks; the skill folder and your goal files stay

Claude's folder is $CLAUDE_CONFIG_DIR when set, else ~/.claude (%USERPROFILE%\\.claude on Windows).

1. Puts the skill at <claude folder>/skills/mama:
   a symlink to this folder (a directory junction on Windows), or nothing if it's already there.
2. Registers its three hooks (PreCompact, SessionStart on compact, Stop) in <claude folder>/settings.json
   in exec form — this Python's absolute path plus the hook script's — so no shell, `~` or
   `python3`-vs-`python` differences matter. Other settings are kept; the first time, the original is saved
   as settings.json.bak (never overwritten later). An unreadable settings.json is left untouched.
   Safe to re-run.

mama can instead be installed as a Claude Code plugin (claude plugin install mama@claude-mama), which brings
the same skill and hooks. Only one route may be active: when settings.json enables a mama plugin, this
script removes any hooks it registered earlier, links nothing, and exits 1 saying which route to keep.
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
CLAUDE = os.path.abspath(  # one separator style (mklink reads "/x" as a switch)
    os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join("~", ".claude")))
DEST = os.path.join(CLAUDE, "skills", "mama")
SETTINGS = os.path.join(CLAUDE, "settings.json")
EVENTS = {"PreCompact": ("precompact", None), "SessionStart": ("sessionstart", "compact"), "Stop": ("stop", None)}


def plugin_enabled():
    """(enabledPlugins key of an enabled mama plugin, whether settings.json still has our hooks), or (None, False)."""
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            settings = json.load(f)
        enabled = settings.get("enabledPlugins")
        plugin = next((k for k, v in enabled.items() if k.split("@")[0] == "mama" and v is True), None)
        return plugin, bool(plugin) and is_mama(settings.get("hooks", {}))
    except (OSError, ValueError, AttributeError):
        return None, False


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
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                settings = json.load(f)
        except (OSError, ValueError) as e:
            sys.exit(f"mama: can't read {SETTINGS} ({e}) — fix or move it, then run this again. Nothing was changed.")
        if not isinstance(settings, dict) or not isinstance(settings.get("hooks", {}), dict):
            sys.exit(f"mama: {SETTINGS} is not a JSON object with an object \"hooks\" — fix it, then run this again. Nothing was changed.")
        if not os.path.exists(SETTINGS + ".bak"):  # keep the user's original, not a copy of our last edit
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
    plugin, ours = (None, False) if remove else plugin_enabled()
    if plugin:
        if ours:  # a one-liner install from before the plugin would run every hook twice
            try:
                update_hooks(remove=True)
            except OSError as e:
                sys.exit(f"mama: {e}")
            sys.stdout.flush()
        sys.exit(f"mama: the {plugin} plugin is enabled and already brings the skill and hooks, so none were added here"
                 f"{' (the ones added earlier were removed)' if ours else ''}. "
                 f"Use one route: keep the plugin and delete {DEST}, or run  claude plugin uninstall {plugin}  and run this again.")
    try:
        if not remove:
            link_skill()
        update_hooks(remove)
    except OSError as e:
        sys.exit(f"mama: {e}")
    if not remove:
        print("done — restart Claude Code, then type /mama <your goal> in a git repo.")
        if os.name == "nt":
            print("Windows: Claude Code's Bash tool needs Git for Windows (Git Bash).")


if __name__ == "__main__":
    main()
