#!/usr/bin/env python3
"""ci-wait.py: waits for the CI runs on a pushed commit and logs green / red / pending / none.
A fake `gh` on PATH plays GitHub. Run: python3 tests/test_ci_wait.py
"""
import json
import os
import stat
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import S, Base  # noqa: E402

FAKE_GH = """#!{py}
import json, os, sys
calls = os.environ["FAKE_GH_STATE"]
answers = json.load(open(calls))
n = len(answers["seen"])
answers["seen"].append(sys.argv[1:])
json.dump(answers, open(calls, "w"))
replies = answers["replies"]
reply = replies[min(n, len(replies) - 1)]
if isinstance(reply, str):
    sys.stderr.write(reply + "\\n")
    sys.exit(1)
print(json.dumps(reply))
"""


def run(name, status="completed", conclusion="success", at="2026-11-20T10:00:00Z"):
    return {"databaseId": 1, "workflowName": name, "status": status, "conclusion": conclusion,
            "url": f"https://gh/{name}", "createdAt": at}


@unittest.skipIf(os.name == "nt", "the fake gh is a shebang script")
class CIWait(Base):
    def wait(self, replies, *extra, gh=True):
        env = self.fake_env(replies, gh)
        r = subprocess.run([sys.executable, os.path.join(S, "ci-wait.py"), self.repo, "abc1234def", *extra],
                           capture_output=True, text=True, env=env)
        self.seen = json.load(open(env["FAKE_GH_STATE"]))["seen"]
        return r.returncode, r.stdout.strip()

    def fake_env(self, replies, gh=True):
        bin_ = os.path.join(self.tmp, "bin" if gh else "bin-empty")
        os.makedirs(bin_, exist_ok=True)
        state = os.path.join(self.tmp, "gh.json")
        with open(state, "w") as f:
            json.dump({"replies": replies, "seen": []}, f)
        if gh:
            path = os.path.join(bin_, "gh")
            with open(path, "w") as f:
                f.write(FAKE_GH.format(py=sys.executable))
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        env = self.env()
        env.update(PATH=bin_ + os.pathsep + env.get("PATH", "") if gh else bin_,  # no gh: nothing else on PATH
                   FAKE_GH_STATE=state, MAMA_CI_POLL="0", MAMA_CI_APPEAR="0")
        return env

    def test_waits_until_every_run_finishes_then_green(self):
        code, out = self.wait([[run("test", "in_progress", None)], [run("test"), run("lint", "queued", None)],
                               [run("test"), run("lint", conclusion="skipped")]])
        self.assertEqual((code, out), (0, "ci abc1234de: green — 2 runs"))
        self.assertEqual(len(self.seen), 3)
        self.assertIn("--commit", self.seen[0])

    def test_a_short_hash_is_asked_for_in_full(self):
        subprocess.run(["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "x"], check=True)
        full = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        r = subprocess.run([sys.executable, os.path.join(S, "ci-wait.py"), self.repo, full[:7]],
                           capture_output=True, text=True, env=self.fake_env([[run("test")]]))
        self.assertEqual(r.stdout.strip(), f"ci {full[:7]}: green — 1 run")
        seen = json.load(open(os.path.join(self.tmp, "gh.json")))["seen"]
        self.assertEqual(seen[0][seen[0].index("--commit") + 1], full)

    def test_red_names_each_failed_workflow(self):
        code, out = self.wait([[run("test", conclusion="failure"), run("lint"), run("e2e", conclusion="cancelled")]])
        self.assertEqual(code, 1)
        self.assertEqual(out, "ci abc1234de: red — test (failure) https://gh/test; e2e (cancelled) https://gh/e2e")

    def test_a_rerun_replaces_the_older_result(self):
        code, out = self.wait([[run("test", conclusion="failure", at="2026-11-20T10:00:00Z"),
                                run("test", at="2026-11-20T10:05:00Z")]])
        self.assertEqual((code, out), (0, "ci abc1234de: green — 1 run"))

    def test_none_when_no_run_starts_or_gh_cant_answer(self):
        self.assertEqual(self.wait([[]]), (0, "ci none: no CI run started for abc1234de within 0s"))
        self.assertEqual(self.wait(["To get started with GitHub CLI, please run:  gh auth login"]),
                         (0, "ci none: gh: To get started with GitHub CLI, please run:  gh auth login"))
        self.assertEqual(self.wait([[]], gh=False), (0, "ci none: gh not installed"))

    def test_pending_after_the_timeout(self):
        code, out = self.wait([[run("test", "in_progress", None)]], "--timeout", "0")
        self.assertEqual(code, 3)
        self.assertEqual(out, "ci abc1234de: pending — 1 of 1 runs still running after 0m")

    def test_log_writes_the_line_close_check_reads(self):
        g = self.new_goal()
        log = os.path.join(g, "log.md")
        self.wait([[run("test")]], "--log", log)
        self.assertRegex(self.read(log).splitlines()[-1], r"^E\d+ \d\d:\d\d ci abc1234de: green — 1 run$")


if __name__ == "__main__":
    unittest.main()
