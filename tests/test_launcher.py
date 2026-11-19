"""scripts/py probes each candidate Python, then execs the first that works, passing args,
stdin and the exit code through."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import S

BASH = shutil.which("bash")


@unittest.skipIf(os.name == "nt" or not BASH, "POSIX shell stubs stand in for python3 and python")
class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.stub("python3", f'exec "{sys.executable}" "$@"')
        self.stub("python", f'exec "{sys.executable}" "$@"')

    def stub(self, name, body):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(f"#!/bin/sh\n{body}\n")
        os.chmod(path, 0o755)

    def script(self, body):
        path = os.path.join(self.tmp, "t.py")
        with open(path, "w") as f:
            f.write(body)
        return path

    def run_py(self, *args, **kw):
        env = dict(os.environ, PATH=self.tmp + os.pathsep + os.environ.get("PATH", ""))
        return subprocess.run([BASH, os.path.join(S, "py"), *args], capture_output=True, text=True,
                              env=env, **kw)

    def test_runs_script_as_main_with_args_and_exit_code(self):
        t = self.script("import sys\nprint(__name__, sys.argv)\nsys.exit(5)\n")
        r = self.run_py(t, "a b", "c")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertIn(f"__main__ {[t, 'a b', 'c']!r}", r.stdout)

    def test_falls_back_when_first_candidate_is_broken(self):
        # a pyenv shim with no version selected: on PATH, but exits 127 with an error
        self.stub("python3", 'echo "pyenv: python3: command not found" >&2; exit 127')
        self.stub("python", f'echo via-python >&2; exec "{sys.executable}" "$@"')
        t = self.script("print('ran')\n")
        r = self.run_py(t)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "ran\n")
        self.assertIn("via-python", r.stderr)
        self.assertNotIn("pyenv", r.stderr)

    def test_script_exiting_119_runs_once(self):
        ran = os.path.join(self.tmp, "ran")
        t = self.script(f"import sys\nopen({ran!r}, 'a').write('x\\n')\nsys.exit(119)\n")
        r = self.run_py(t)
        self.assertEqual(r.returncode, 119, r.stderr)
        with open(ran) as f:
            self.assertEqual(f.read(), "x\n")

    def test_launcher_is_replaced_by_python(self):
        # with exec, Python's parent is whoever started the launcher, not a lingering bash
        t = self.script("import os\nprint(os.getppid())\n")
        r = self.run_py(t)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(int(r.stdout), os.getpid())

    def test_stdin_passes_through(self):
        t = self.script("import json, sys\nprint(json.dumps(json.load(sys.stdin)))\n")
        payload = {"session_id": "s1", "tool": "Bash"}
        r = self.run_py(t, input=json.dumps(payload))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), payload)

    def test_script_imports_its_siblings(self):
        r = self.run_py(os.path.join(S, "activity.py"), "no-such-session")
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
