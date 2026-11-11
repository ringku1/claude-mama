#!/usr/bin/env python3
"""Run a command while holding a lock file — `flock` for every OS (macOS and Windows have none).

Usage: lock.py <lockfile> <command> [args...]
  lock.py <store>/.heavy.lock pnpm test
  lock.py <store>/.heavy.lock bash -c 'cd api && go test ./...'     # shell syntax: wrap it
Waits until no other lock.py holds <lockfile>, runs the command, exits with its exit code.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    path, cmd = sys.argv[1], sys.argv[2:]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a+") as f, fileio.locked(f):
        try:
            code = subprocess.call(cmd)
        except FileNotFoundError:
            sys.exit(f"lock.py: command not found: {cmd[0]}")
    sys.exit(code)


if __name__ == "__main__":
    main()
