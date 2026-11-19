"""scripts/py starts Python once per call, and passes args and the exit code through."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import S

BASH = shutil.which("bash")


@unittest.skipIf(os.name == "nt" or not BASH, "a POSIX shell stub stands in for python3")
class OneStart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.count = os.path.join(self.tmp, "count")
        stub = os.path.join(self.tmp, "python3")
        with open(stub, "w") as f:
            f.write(f'#!/bin/sh\necho x >> "{self.count}"\nexec "{sys.executable}" "$@"\n')
        os.chmod(stub, 0o755)
        self.script = os.path.join(self.tmp, "t.py")
        with open(self.script, "w") as f:
            f.write("import sys\nprint(__name__, sys.argv)\nsys.exit(5)\n")

    def run_py(self, *args):
        env = dict(os.environ, PATH=self.tmp + os.pathsep + os.environ.get("PATH", ""))
        return subprocess.run([BASH, os.path.join(S, "py"), *args], capture_output=True, text=True, env=env)

    def starts(self):
        with open(self.count) as f:
            return len(f.read().split())

    def test_starts_python_once(self):
        self.run_py(self.script)
        self.assertEqual(self.starts(), 1)

    def test_runs_script_as_main_with_args_and_exit_code(self):
        r = self.run_py(self.script, "a b", "c")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertIn(f"__main__ {[self.script, 'a b', 'c']!r}", r.stdout)

    def test_script_imports_its_siblings(self):
        r = self.run_py(os.path.join(S, "activity.py"), "no-such-session")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.starts(), 1)


if __name__ == "__main__":
    unittest.main()
