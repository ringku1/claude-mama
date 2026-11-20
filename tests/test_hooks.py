#!/usr/bin/env python3
"""mama-hook.py: whose goal a session is on, event lines, Stop nags. Run: python3 tests/test_hooks.py"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import HOOK, NOW, S, SKILL, Base, utc  # noqa: E402,F401


class HookBase(Base):
    def transcript(self, sid):
        return os.path.join(self.home, ".claude", "projects", "p", f"{sid}.jsonl")

    def hook(self, mode, sid="sess-a", cwd=None, env_sid=None, path=None, raw=None, hook=HOOK, **extra):
        inp = raw if raw is not None else json.dumps(
            {"cwd": cwd or self.repo, "session_id": sid, "trigger": "auto", "transcript_path": self.transcript(sid)})
        env = self.env(env_sid)
        env.update(extra)
        if path:
            env["PATH"] = path + os.pathsep + env.get("PATH", "")
        r = subprocess.run([sys.executable, hook, mode], input=inp, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def running_goal(self, slug="demo", sid="sess-a", store=None):
        if store:
            g = self.run_s("new-goal.py", store, slug, "build", "test", sid=sid).splitlines()[0]
        else:
            g = self.new_goal(slug, sid=sid)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "research none: test", sid=sid)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "expectations: 9 settled, 0 asked", sid=sid)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "db: none — test", sid=sid)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "playback: confirmed", sid=sid)
        self.run_s("plan-set.py", self.plan(g), "S+", "title=a", "verify=v", sid=sid)
        self.run_s("plan-set.py", self.plan(g), "--header", "status=running", "mode=autonomous", "budget=M", sid=sid)
        os.utime(os.path.join(g, "overview.md"))  # overview fresh
        return g

    def write_transcript(self, sid, goal, extra=0):
        """A transcript whose session ran log.py on goal (a write, as spend.written_slugs reads it)."""
        os.makedirs(os.path.dirname(self.transcript(sid)), exist_ok=True)
        call = {"type": "assistant", "timestamp": utc(NOW), "message": {"id": "m0", "content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": f"python3 log.py {os.path.join(goal, 'log.md')} E go"}}]}}
        with open(self.transcript(sid), "w", encoding="utf-8") as f:
            f.write(json.dumps(call) + "\n")
            filler = json.dumps({"type": "user", "timestamp": utc(NOW), "message": {"content": "x" * 400}})
            for _ in range(extra):
                f.write(filler + "\n")

    def activity(self):
        try:
            return self.read(os.path.join(self.home, ".claude", "mama", "activity.log"))
        except OSError:
            return ""

    def skill_with_close_check(self, main_body):
        """A copy of the hook and scripts whose close-check.py, run as a script, does main_body
        (imported as a module it is the real one). Returns the copied hook's path."""
        root = os.path.join(self.tmp, "skill")
        shutil.copytree(os.path.join(SKILL, "hooks"), os.path.join(root, "hooks"))
        sc = os.path.join(root, "scripts")
        shutil.copytree(S, sc, ignore=shutil.ignore_patterns("__pycache__"))
        os.replace(os.path.join(sc, "close-check.py"), os.path.join(sc, "close_check_real.py"))
        with open(os.path.join(sc, "close-check.py"), "w", encoding="utf-8") as f:
            f.write("import os, sys, time\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
                    "from close_check_real import *  # noqa\n"
                    f"if __name__ == '__main__':\n    {main_body}\n")
        return os.path.join(root, "hooks", "mama-hook.py")

    def stub_spend(self, hook, body):
        """In the copied skill of hook, wrap spend.measure: body runs with plan, transcript, deadline and
        returns the total (it sets measure.partial itself; the real measure is _real_measure)."""
        sp = os.path.join(os.path.dirname(os.path.dirname(hook)), "scripts", "spend.py")
        with open(sp, "a", encoding="utf-8") as f:
            f.write("\n_real_measure = measure\n\n\ndef measure(plan, transcript=None, deadline=None):\n"
                    "    measure.partial = False\n" + "".join(f"    {l}\n" for l in body.splitlines()))

    def done_goal_with_another_problem(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "D", "pick x | tag: user")  # not learned: a problem
        s = self.read(self.plan(g)).replace("status: running", "status: done")
        open(self.plan(g), "w", encoding="utf-8").write(s)
        os.utime(os.path.join(g, "overview.md"))
        return g


class WhoseGoal(HookBase):
    def test_never_claims_another_sessions_goal(self):
        g = self.running_goal(sid="sess-a")
        self.write_transcript("sess-b", g)  # sess-b wrote to it too, per its transcript, but never recorded
        before = self.read(os.path.join(g, "log.md"))
        self.assertEqual(self.hook("precompact", sid="sess-b", env_sid="sess-b"), "")
        self.assertEqual(self.read(os.path.join(g, "log.md")), before)  # no `E compaction` in a's goal
        self.assertNotIn("This session's goal", self.hook("sessionstart", sid="sess-b"))
        self.assertEqual(self.hook("stop", sid="sess-b"), "")
        self.assertIn("This session's goal is 'demo'", self.hook("sessionstart", sid="sess-a"))

    def test_own_goal_in_another_store(self):
        other = os.path.join(self.tmp, "other-repo")
        subprocess.run(["git", "init", "-q", other], check=True)
        g = self.running_goal(slug="far", store=os.path.join(other, ".claude", "mama"))
        self.running_goal(slug="near", sid="sess-x")  # someone else's, in the cwd's store
        ctx = json.loads(self.hook("sessionstart"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("This session's goal is 'far'", ctx)
        self.assertIn("- near", ctx)
        self.assertIn("still marked running", json.loads(self.hook("stop"))["reason"])
        self.assertIn("keep: the slug 'far'", self.hook("precompact"))
        self.assertRegex(self.read(os.path.join(g, "log.md")), r"E\d+ \d\d:\d\d compaction \(auto\)\n")

    def test_most_recent_open_goal_is_this_sessions(self):
        self.running_goal(slug="first")
        self.running_goal(slug="second")
        ctx = json.loads(self.hook("sessionstart"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("This session's goal is 'second'", ctx)
        self.assertIn("also touched open goal(s): first", ctx)

    def test_unrecorded_goal_is_never_claimed(self):
        g = self.running_goal(slug="old", sid=None)  # no session recorded writes to it
        self.write_transcript("sess-b", g)  # even if the transcript mentions it
        ctx = json.loads(self.hook("sessionstart", sid="sess-b"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("None of them is recorded as this session's", ctx)
        self.hook("precompact", sid="sess-b", env_sid="sess-b")
        self.assertNotIn("compaction", self.read(os.path.join(g, "log.md")))
        self.assertNotIn("sess-b", self.activity())

    def test_old_git_without_path_format(self):
        if os.name == "nt":
            self.skipTest("shell shim")
        real = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
        self.running_goal(sid=None)  # found only via the cwd's store, so main_checkout must work
        self.write_transcript("sess-b", os.path.join(self.store, "demo"))
        shims = {  # git < 2.31: rejects --path-format, or (rev-parse) echoes it back unparsed
            "fail": 'for a in "$@"; do case "$a" in --path-format=*) echo "unknown" >&2; exit 129;; esac; done',
            "echo": 'n=$#; for a in "$@"; do case "$a" in --path-format=*) echo "$a";; *) set -- "$@" "$a";; esac; done; shift $n',
        }
        for name, body in shims.items():
            d = os.path.join(self.tmp, f"git-{name}")
            os.makedirs(d)
            with open(os.path.join(d, "git"), "w") as f:
                f.write(f'#!/bin/sh\n{body}\nexec {real} "$@"\n')
            os.chmod(os.path.join(d, "git"), 0o755)
            out = self.hook("sessionstart", sid="sess-b", cwd=os.path.join(self.repo, ".claude"), path=d)
            self.assertIn("\\n- demo ", out, name)  # the cwd's store was found


    def test_expected_git_failures_stay_out_of_the_error_log(self):
        self.running_goal()
        errors = os.path.join(self.home, ".claude", "mama", "hook-errors.log")
        no_git = os.path.join(self.tmp, "no-git")  # git not on PATH: FileNotFoundError
        os.makedirs(no_git)
        self.hook("sessionstart", PATH=no_git)
        self.hook("sessionstart", cwd=self.tmp)  # not a repo
        self.assertFalse(os.path.exists(errors) and "sessionstart" in self.read(errors))


class Stop(HookBase):
    def test_same_problems_block_once_changed_block_again(self):
        g = self.running_goal()
        self.assertIn("still marked running", json.loads(self.hook("stop"))["reason"])
        self.assertEqual(self.hook("stop"), "")  # nothing changed: no second block
        self.run_s("log.py", os.path.join(g, "log.md"), "D", "pick x | tag: user")
        reason = json.loads(self.hook("stop"))["reason"]  # the list changed
        self.assertIn("nothing was learned", reason)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "learn none")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.assertEqual(self.hook("stop"), "")
        self.assertFalse(os.path.exists(os.path.join(g, ".last-block")))
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "agent back")
        self.assertIn("still marked running", json.loads(self.hook("stop"))["reason"])  # came back: blocks again

    def test_deadline_cut_run_never_re_blocks_or_forgets_the_full_list(self):
        # a cut run (past DEADLINE) skips optional checks, so its list is partial: it blocks only for a problem the
        # last block didn't name and never replaces .last-block, so cut and full runs don't alternate blocks
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "D", "pick x | tag: user")  # not learned: an optional check
        full = json.loads(self.hook("stop"))["reason"]
        self.assertIn("nothing was learned", full)
        cut = os.path.join(self.tmp, "cut-hook.py")
        open(cut, "w", encoding="utf-8").write(self.read(HOOK).replace("HOOK_BUDGET = 6.0", "HOOK_BUDGET = -1.0", 1)
                                               .replace("os.path.abspath(__file__)", repr(HOOK), 1))
        self.assertEqual(self.hook("stop", hook=cut), "")  # partial list, nothing new
        self.assertEqual(self.read(os.path.join(g, ".last-block")), full)
        self.assertEqual(self.hook("stop"), "")  # full run: unchanged since the block
        os.remove(os.path.join(g, ".last-block"))
        self.assertIn("still marked running", json.loads(self.hook("stop", hook=cut))["reason"])  # new to it: blocks
        self.assertIn("still marked running", self.read(os.path.join(g, ".last-block")))  # remembered (union)
        self.assertEqual(self.hook("stop", hook=cut), "")  # every Stop cut: the same problem doesn't block each turn
        self.assertIn("nothing was learned", json.loads(self.hook("stop"))["reason"])
        self.assertEqual(self.hook("stop"), "")  # the full list blocks once
        self.assertEqual(self.hook("stop", hook=cut), "")

    def partial_close_check_stays_quiet(self, body):
        # close-check that didn't finish, or whose spend measure was cut, gave a partial list: a block whose
        # problems the last block already named stays quiet
        hook = self.skill_with_close_check(body)
        g = self.done_goal_with_another_problem()
        reason = json.loads(self.hook("stop", hook=hook))["reason"]
        self.assertNotIn("PARTIAL", reason)
        with open(os.path.join(g, ".last-block"), "w", encoding="utf-8") as f:
            f.write(reason + "\n- an older problem")
        self.assertEqual(self.hook("stop", hook=hook), "")

    def test_close_check_with_a_cut_measure_counts_as_a_cut_run(self):
        self.partial_close_check_stays_quiet("print('MISSING: x'); print('PARTIAL: spend measure cut'); sys.exit(1)")

    def test_unfinished_close_check_counts_as_a_cut_run(self):
        self.partial_close_check_stays_quiet("sys.exit(1)")

    def test_unwritable_last_block_still_blocks_and_exits_cleanly(self):
        g = self.running_goal()
        os.makedirs(os.path.join(g, ".last-block"))  # can't be read or replaced
        self.assertIn("still marked running", json.loads(self.hook("stop"))["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "mama", "hook-errors.log")))

    def test_quick_goal_has_no_learn_nag(self):
        g = self.run_s("new-goal.py", self.store, "q", "fix", "t", "--quick").splitlines()[0]
        self.run_s("log.py", os.path.join(g, "log.md"), "D", "pick x | tag: user")
        self.run_s("plan-set.py", self.plan(g), "--header", "status=waiting")
        os.utime(os.path.join(g, "overview.md"))
        out = self.hook("stop")
        self.assertNotIn("nothing was learned", out)

    def test_budget_written_under_plan_lock(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        os.makedirs(os.path.dirname(self.transcript("sess-a")), exist_ok=True)
        with open(self.transcript("sess-a"), "w") as f:
            now = datetime.datetime.now()  # not NOW: the goal started after this module loaded
            f.write(json.dumps({"type": "assistant", "timestamp": utc(now), "message": {
                "id": "m1", "usage": {"input_tokens": 40000, "output_tokens": 2000}, "content": []}}) + "\n")
        self.hook("stop")
        self.assertRegex(self.read(self.plan(g)), r"budget: ~42k /")
        self.assertTrue(os.path.exists(os.path.join(g, ".plan.lock")))

    def test_errors_exit_0_and_are_logged(self):
        self.assertEqual(self.hook("stop", raw="[1, 2]"), "")
        errs = self.read(os.path.join(self.home, ".claude", "mama", "hook-errors.log")).splitlines()
        self.assertEqual(len(errs), 1)
        self.assertRegex(errs[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d stop AttributeError: ")

    def test_fast_on_a_big_transcript(self):
        g = self.running_goal()
        self.write_transcript("sess-a", g, extra=60000)  # ~30 MB
        t = time.time()
        for mode in ("stop", "sessionstart", "precompact"):
            self.hook(mode)
        self.assertLess((time.time() - t) / 3, 3)

    def test_close_check_timeout_still_blocks(self):
        hook = self.skill_with_close_check("time.sleep(30)")
        g = self.done_goal_with_another_problem()
        t = time.time()
        reason = json.loads(self.hook("stop", hook=hook))["reason"]
        self.assertLess(time.time() - t, 8)  # under the hook's own 10s timeout
        self.assertIn(f"close check didn't finish — run scripts/close-check.py {os.path.realpath(g)}", reason)
        self.assertIn("nothing was learned", reason)

    def test_close_check_crash_still_blocks(self):
        hook = self.skill_with_close_check("raise RuntimeError('boom')")
        g = self.done_goal_with_another_problem()
        reason = json.loads(self.hook("stop", hook=hook))["reason"]
        self.assertIn(f"close check didn't finish — run scripts/close-check.py {os.path.realpath(g)}", reason)
        self.assertIn("nothing was learned", reason)

    def test_stop_and_precompact_run_no_git(self):
        if os.name == "nt":
            self.skipTest("shell shim")
        self.running_goal()
        d = os.path.join(self.tmp, "git-spy")
        os.makedirs(d)
        calls = os.path.join(self.tmp, "git-calls")
        with open(os.path.join(d, "git"), "w") as f:
            f.write(f'#!/bin/sh\necho "$@" >> {calls}\nexit 1\n')
        os.chmod(os.path.join(d, "git"), 0o755)
        self.assertIn("still marked running", json.loads(self.hook("stop", path=d))["reason"])
        self.assertIn("keep: the slug 'demo'", self.hook("precompact", path=d))
        self.assertFalse(os.path.exists(calls), "git ran in stop/precompact")
        self.hook("sessionstart", path=d)
        self.assertTrue(os.path.exists(calls))  # sessionstart still finds the store through git


class OnceOnly(HookBase):
    """The one-liner's skills/mama also loads as plugin mama@skills-dir, and a marketplace install may sit beside
    the one-liner: a plugin-launched copy (MAMA_VIA set) steps aside only when settings.json holds, for the same
    event, install.py's exact exec form with an existing interpreter and mama-hook.py. Anything else runs the plugin."""

    def settings(self, text, base=None):
        d = base or os.path.join(self.home, ".claude")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "settings.json"), "w", encoding="utf-8") as f:
            f.write(text)

    def skills_dir(self, base=None):
        return os.path.join(base or os.path.join(self.home, ".claude"), "skills", "mama")

    def one_liner(self, script=None, base=None, event="PreCompact", command=None):
        """settings.json as install.py writes it (exec form: command = the interpreter), running script
        (default: a real file under skills/mama) under event."""
        if script is None:
            script = os.path.join(self.skills_dir(base), "hooks", "mama-hook.py")
            os.makedirs(os.path.dirname(script), exist_ok=True)
            open(script, "w").close()
        return json.dumps({"hooks": {event: [{"hooks": [
            {"type": "command", "command": command or sys.executable, "args": [script, event.lower()]}]}]}})

    def test_steps_aside_only_for_the_same_event(self):
        # a one-liner that registers only Stop leaves the plugin's PreCompact and SessionStart to the plugin
        self.running_goal()
        self.settings(self.one_liner(event="Stop"))
        self.assertIn("keep: the slug 'demo'", self.hook("precompact", MAMA_VIA=self.market()))
        errors = os.path.join(self.home, ".claude", "mama", "hook-errors.log")
        self.assertEqual(self.hook("stop", raw="[1, 2]", MAMA_VIA=self.market()), "")
        self.assertFalse(os.path.exists(errors))  # Stop stepped aside before reading stdin
        self.hook("sessionstart", raw="[1, 2]", MAMA_VIA=self.market())
        self.assertTrue(os.path.exists(errors))  # SessionStart ran (and logged the bad stdin)
        self.settings(self.one_liner(event="SessionStart"))
        os.remove(errors)
        self.hook("sessionstart", raw="[1, 2]", MAMA_VIA=self.market())
        self.assertFalse(os.path.exists(errors))

    def test_exec_form_needs_its_interpreter_file(self):
        # brew upgraded python: the one-liner's script is there but its interpreter is gone, so it can't run.
        # A bare name or a WindowsApps stub isn't the interpreter install.py writes either: the plugin runs
        self.running_goal()
        stub = os.path.join(self.tmp, "AppData", "Local", "Microsoft", "WindowsApps", "python3.exe")
        os.makedirs(os.path.dirname(stub))
        open(stub, "w").close()
        for interp in (os.path.join(self.tmp, "old-python", "bin", "python3.8"), "no-such-python-mama",
                       os.path.basename(sys.executable), stub):
            self.settings(self.one_liner(command=interp))
            out = self.hook("precompact", MAMA_VIA=self.market(), path=os.path.dirname(sys.executable))
            self.assertIn("keep: the slug 'demo'", out, interp)
        self.settings(self.one_liner())
        self.assertEqual(self.hook("precompact", MAMA_VIA=self.market()), "")

    def test_microsoft_store_python_is_a_real_interpreter(self):
        # only the bare stub (parent folder WindowsApps) is refused; the Store's own python.exe is a real file
        self.running_goal()
        store = os.path.join(self.tmp, "AppData", "Local", "Microsoft", "WindowsApps",
                             "PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0", "python.exe")
        os.makedirs(os.path.dirname(store))
        open(store, "w").close()
        self.settings(self.one_liner(command=store))
        self.assertEqual(self.hook("precompact", MAMA_VIA=self.market()), "")

    def test_script_name_must_be_exactly_mama_hook_py(self):
        self.running_goal()
        for name in ("not-mama-hook.py", "xmama-hook.py", "mama-hook.pyc"):
            script = os.path.join(self.tmp, "n", name)
            os.makedirs(os.path.dirname(script), exist_ok=True)
            open(script, "w").close()
            self.settings(self.one_liner(script))
            self.assertIn("keep: the slug 'demo'", self.hook("precompact", MAMA_VIA=self.market()), name)

    def test_only_install_pys_exact_args_step_aside(self):
        # args must be exactly [<mama-hook.py>, <this mode>]: no expansion (exec form runs no shell), no extras
        self.running_goal()
        script = os.path.join(self.skills_dir(), "hooks", "mama-hook.py")
        self.one_liner()  # creates it

        def entry(args):
            return json.dumps({"hooks": {"PreCompact": [{"hooks": [
                {"type": "command", "command": sys.executable, "args": args}]}]}})

        rel = "/.claude/skills/mama/hooks/mama-hook.py"
        for args in ([script, "stop"], [script, "PreCompact"], [script], [script, "precompact", "x"],
                     ["$HOME" + rel, "precompact"], ["~" + rel, "precompact"], [script + " ", "precompact"],
                     "{} precompact".format(script), [os.path.dirname(script), "precompact"]):
            self.settings(entry(args))
            self.assertIn("keep: the slug 'demo'", self.hook("precompact", MAMA_VIA=self.market()), args)
        self.settings(entry([script, "precompact"]))
        self.assertEqual(self.hook("precompact", MAMA_VIA=self.market()), "")

    def test_command_strings_never_step_aside(self):
        # a command string (shell form, hand-written or an older install) is never parsed: the plugin runs, and
        # a double run is the accepted worst case
        self.running_goal()
        script = os.path.join(self.skills_dir(), "hooks", "mama-hook.py")
        self.one_liner()
        rel = "/.claude/skills/mama/hooks/mama-hook.py"
        py = sys.executable
        for c in (f'"{py}" "{script}" precompact', f"'{py}' '{script}' precompact", f"{py} {script} precompact",
                  f"{py} ~{rel} precompact", f'{py} "$HOME{rel}" precompact', f"exec {py} {script} precompact",
                  f"time {py} {script} precompact", f"X=1 {py} {script} precompact", f"cd /\n{py} {script} precompact",
                  f"{py} {script.replace('/', chr(92))} precompact", f"{py} {script} precompact; true"):
            self.settings(json.dumps({"hooks": {"PreCompact": [{"hooks": [{"type": "command", "command": c}]}]}}))
            self.assertIn("keep: the slug 'demo'", self.hook("precompact", MAMA_VIA=self.market()), c)

    def market(self):
        return os.path.join(self.home, ".claude", "plugins", "cache", "mama", "mama", "1.0.0")

    def test_plugin_copy_steps_aside_for_settings_hooks(self):
        g = self.running_goal()
        log = os.path.join(g, "log.md")
        self.settings(self.one_liner())
        before = self.read(log)
        self.assertEqual(self.hook("precompact", MAMA_VIA=self.skills_dir()), "")
        self.assertEqual(self.read(log), before)  # no work: no `E compaction` line
        self.settings(self.one_liner(event="Stop"))
        self.assertEqual(self.hook("stop", raw="[1, 2]", MAMA_VIA=self.skills_dir() + os.sep), "")  # before reading stdin
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "mama", "hook-errors.log")))
        self.assertIn("keep: the slug 'demo'", self.hook("precompact"))  # the settings.json hook itself runs

    def test_marketplace_install_steps_aside_for_a_live_one_liner(self):
        self.running_goal()
        self.settings(self.one_liner())
        for via in (self.market(), "plugin"):
            self.assertEqual(self.hook("precompact", MAMA_VIA=via), "", via)
        self.assertIn("keep: the slug 'demo'", self.hook("precompact", MAMA_VIA=""))  # not plugin-launched

    def test_stale_settings_entry_never_silences_the_plugin(self):
        self.running_goal()
        gone = os.path.join(self.tmp, "gone", "skills", "mama", "hooks", "mama-hook.py")
        self.settings(self.one_liner(gone))
        for via in (self.market(), self.skills_dir(), ""):
            self.assertIn("keep: the slug 'demo'", self.hook("precompact", MAMA_VIA=via), via)

    def test_plugin_copy_runs_without_settings_hooks(self):
        self.running_goal()
        for text in (None, '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}',
                     '{"hooks": ', '[1]', '{"hooks": {"Stop": 3}}'):
            if text is not None:
                self.settings(text)
            self.assertIn("keep: the slug 'demo'", self.hook("precompact", MAMA_VIA=self.skills_dir()), text)

    def test_reads_claude_config_dir_settings(self):
        self.running_goal()
        cfg = os.path.join(self.tmp, "cfg")
        self.settings(self.one_liner(base=cfg), base=cfg)
        self.assertEqual(self.hook("precompact", MAMA_VIA=self.skills_dir(cfg), CLAUDE_CONFIG_DIR=cfg), "")
        none = os.path.join(self.tmp, "none")  # ~/.claude's settings.json is not the config folder's then
        self.settings(self.one_liner())
        self.assertIn("keep: the slug 'demo'",
                      self.hook("precompact", MAMA_VIA=self.skills_dir(none), CLAUDE_CONFIG_DIR=none))

    def test_step_aside_check_is_inside_the_error_guard(self):
        import ast
        tree = ast.parse(self.read(HOOK))
        [main] = [n for n in tree.body if isinstance(n, ast.If) and "__main__" in ast.dump(n.test)]
        outside = [n for n in main.body if not isinstance(n, ast.Try)]
        self.assertNotIn("step_aside", "".join(ast.dump(n) for n in outside))
        self.assertIn("step_aside", "".join(ast.dump(n) for n in main.body if isinstance(n, ast.Try)))


class Lean(HookBase):
    def spend(self, g, tokens):
        """Append one API message of `tokens` to the session's transcript."""
        os.makedirs(os.path.dirname(self.transcript("sess-a")), exist_ok=True)
        self.n = getattr(self, "n", 0) + 1
        with open(self.transcript("sess-a"), "a") as f:
            f.write(json.dumps({"type": "assistant", "timestamp": utc(datetime.datetime.now()), "message": {
                "id": f"m{self.n}", "usage": {"input_tokens": tokens, "output_tokens": 0}, "content": []}}) + "\n")

    def test_dispatch_line_counts_as_waiting(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "dispatch S1 S2")
        self.assertEqual(self.hook("stop"), "")

    def test_budget_at_70_autonomous_raises_itself(self):
        g = self.running_goal()  # autonomous, M = 1M
        self.run_s("plan-set.py", self.plan(g), "--header", "auto-raise=1x")  # the hook never raises it
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.spend(g, 800000)
        reason = json.loads(self.hook("stop"))["reason"]
        self.assertIn("Budget at 80%", reason)
        self.assertIn("within 2× the approved M", reason)
        self.assertIn("tag: auto", reason)

    def test_budget_at_70_checkpointed_asks(self):
        g = self.running_goal()
        self.run_s("plan-set.py", self.plan(g), "--header", "mode=checkpointed", "auto-raise=1x")
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        os.utime(os.path.join(g, "overview.md"))
        self.spend(g, 800000)
        reason = json.loads(self.hook("stop"))["reason"]
        self.assertIn("ask the user: continue / cut scope / stop", reason)
        self.assertNotIn("tag: auto", reason)

    def test_quick_goal_that_grew_offers_a_full_goal(self):
        g = self.run_s("new-goal.py", self.store, "q", "fix", "t", "--quick").splitlines()[0]
        log = os.path.join(g, "log.md")
        self.run_s("log.py", log, "E", "db: none — test")
        self.run_s("log.py", log, "E", "playback: confirmed")
        self.run_s("plan-set.py", self.plan(g), "S+", "title=a", "verify=v")
        self.run_s("plan-set.py", self.plan(g), "--header", "status=running")
        self.run_s("log.py", log, "E", "wait agent")
        os.utime(os.path.join(g, "overview.md"))
        self.spend(g, 100000)
        self.assertEqual(self.hook("stop"), "")  # still small
        self.spend(g, 250000)
        self.assertIn("outgrown quick mode", json.loads(self.hook("stop"))["reason"])
        self.run_s("log.py", log, "D", "keep it quick (tag: user)")
        self.run_s("log.py", log, "E", "wait agent")
        self.assertEqual(self.hook("stop"), "")  # answered

    def set_head(self, g, old, new):
        s = self.read(self.plan(g))
        self.assertIn(old, s)
        open(self.plan(g), "w", encoding="utf-8").write(s.replace(old, new, 1))

    def test_hunt_cap_full_asks_after_round_2(self):
        g = self.running_goal()  # no tier: header: an old goal counts as full (cap 2)
        log = os.path.join(g, "log.md")
        self.run_s("log.py", log, "E", "hunt 1: 9 found, 6 real, 0 fixed yet, 2 minor — /code-review high")
        self.run_s("log.py", log, "E", "hunt 1: 9 found, 6 real, 6 fixed, 2 minor — /code-review high")
        self.run_s("log.py", log, "E", "wait hunt 2")
        self.assertEqual(self.hook("stop"), "")  # under the cap: the next round comes anyway
        self.run_s("log.py", log, "E", "hunt 2: 3 found, 1 real, 0 fixed yet — /code-review low + expectations check")
        self.run_s("log.py", log, "E", "wait fixes")
        reason = json.loads(self.hook("stop"))["reason"]
        self.assertIn("deliver with known issues / one more low round", reason)
        self.assertNotIn("converging", reason)
        self.run_s("log.py", log, "D", "hunt: extra round — one more low pass (tag: user)")
        self.run_s("log.py", log, "E", "learn none")
        self.run_s("log.py", log, "E", "wait hunt 3")
        self.assertEqual(self.hook("stop"), "")  # answered
        self.run_s("log.py", log, "E", "hunt 3: 2 found, 1 real, 0 fixed yet — /code-review low + expectations check")
        self.run_s("log.py", log, "E", "wait fixes")
        self.assertIn("one more low round", json.loads(self.hook("stop"))["reason"])  # the extra round found more
        self.run_s("log.py", log, "D", "ship it: deliver with known issues listed (tag: user)")  # the old wording
        self.run_s("log.py", log, "E", "learn none")
        self.run_s("log.py", log, "E", "wait fixes")
        self.assertEqual(self.hook("stop"), "")

    def test_hunt_cap_is_one_round_for_standard_and_quick(self):
        g = self.running_goal()
        log = os.path.join(g, "log.md")
        self.run_s("plan-set.py", self.plan(g), "--header", "tier=standard")
        self.run_s("log.py", log, "E", "hunt 1: 4 found, 0 real, 0 fixed, 2 minor, 2 trade-off — /code-review high")
        self.run_s("log.py", log, "E", "wait agent")
        self.assertEqual(self.hook("stop"), "")  # trade-offs aren't real bugs
        self.run_s("log.py", log, "E", "hunt 1: 4 found, 1 real, 0 fixed, 2 minor, 1 trade-off — /code-review high")
        self.run_s("log.py", log, "E", "wait agent")
        self.assertIn("one more low round", json.loads(self.hook("stop"))["reason"])
        q = self.running_goal("q")
        self.set_head(q, "mode: autonomous | tier: —", "mode: quick | tier: —")  # quick mode, no tier: quick
        qlog = os.path.join(q, "log.md")
        self.run_s("log.py", qlog, "E", "hunt 1: 2 found, 1 real, 0 fixed — /code-review low")
        self.run_s("log.py", qlog, "E", "wait agent")
        self.assertIn("one more low round", json.loads(self.hook("stop"))["reason"])

    def auto_raise_goal(self, mode="autonomous"):
        g = self.running_goal()  # M = 1M, approved M
        if mode != "autonomous":
            self.run_s("plan-set.py", self.plan(g), "--header", f"mode={mode}")
        self.assertIn("approved: M | auto-raise: 1.5x", self.read(self.plan(g)))  # set at approval
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        os.utime(os.path.join(g, "overview.md"))
        return g

    def test_budget_auto_raises_once_then_asks(self):
        for mode in ("checkpointed", "autonomous"):
            with self.subTest(mode=mode):
                self.setUp()
                g = self.auto_raise_goal(mode)
                self.spend(g, 800000)
                self.assertEqual(self.hook("stop"), "")  # raised itself: no block
                self.assertRegex(self.read(self.plan(g)), r"budget: ~800k / L 1\.5M \|")
                self.assertRegex(self.read(os.path.join(g, "log.md")),
                                 r"\nD\d+ \d\d:\d\d budget auto-raised to L 1\.5M \(tag: auto\)\n")
                self.spend(g, 300000)  # 1.1M of 1.5M: 73% of the raised ceiling
                self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent 2")
                reason = json.loads(self.hook("stop"))["reason"]
                self.assertIn("Budget at 73%", reason)
                self.assertEqual(self.read(os.path.join(g, "log.md")).count("auto-raised"), 1)

    def test_spend_past_the_raised_ceiling_still_asks(self):
        g = self.auto_raise_goal()
        self.spend(g, 1200000)  # 1.2M: past 70% of the 1.5M it raises to
        reason = json.loads(self.hook("stop"))["reason"]
        self.assertIn("Budget at 80%", reason)
        self.assertRegex(self.read(self.plan(g)), r"budget: ~1200k / L 1\.5M \|")

    def capped_goal(self):
        g = self.running_goal()
        log = os.path.join(g, "log.md")
        self.run_s("plan-set.py", self.plan(g), "--header", "tier=standard")
        self.run_s("log.py", log, "E", "hunt 1: 2 found, 1 real, 0 fixed yet — /code-review high")
        return g, log

    def test_hunt_decision_needs_the_users_tag(self):
        for line in ("hunt: deliver with known issues (tag: auto)", "hunt: extra round", "ship: deliver with known issues"):
            with self.subTest(line=line):
                self.setUp()
                g, log = self.capped_goal()
                self.run_s("log.py", log, "D", line)
                self.run_s("log.py", log, "E", "wait agent")
                self.assertIn("one more low round", json.loads(self.hook("stop"))["reason"])

    def test_hunt_cap_quiet_while_the_question_is_pending(self):
        g, log = self.capped_goal()
        self.run_s("plan-set.py", self.plan(g), "--header", "status=waiting")
        os.utime(os.path.join(g, "overview.md"))
        self.assertNotIn("one more low round", self.hook("stop"))

    def marker_overview(self, g, mtime):
        ov = os.path.join(g, "overview.md")
        with open(ov, "w", encoding="utf-8") as f:
            f.write("# Demo\n\n<!-- mama:auto:start -->\n**Status:** Working · 0 of 1 parts done\n"
                    "<!-- mama:auto:end -->\n\n## Goal\n\nBuild the thing.\n")
        os.utime(ov, (mtime, mtime))

    def test_overview_stale_only_for_scope_waiting_or_close(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        t = time.time()
        self.marker_overview(g, t - 100)
        self.assertEqual(self.hook("stop"), "")
        mark = os.path.join(g, ".milestone")
        open(mark, "a").close()
        os.utime(mark, (t + 10, t + 10))  # a ★ step done: no prose refresh due
        self.assertEqual(self.hook("stop"), "")
        self.run_s("plan-set.py", self.plan(g), "S+", "title=b", "verify=v")  # scope changed
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent 2")
        self.assertIn("since overview.md was written", json.loads(self.hook("stop"))["reason"])
        os.utime(os.path.join(g, "overview.md"))  # refreshed
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent 3")
        self.assertEqual(self.hook("stop"), "")
        self.marker_overview(g, time.time() - 100)
        self.run_s("plan-set.py", self.plan(g), "--header", "status=waiting")
        self.assertIn("since overview.md was written", json.loads(self.hook("stop"))["reason"])

    def test_overview_without_markers_keeps_every_milestone(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        ov = os.path.join(g, "overview.md")
        with open(ov, "w", encoding="utf-8") as f:
            f.write("# Demo\n\n**Status:** Working · 0 of 1 parts done\n\n## Goal\n\nBuild the thing.\n")  # an old goal's
        mark = os.path.join(g, ".milestone")
        os.utime(mark, (time.time() + 10, time.time() + 10))
        self.assertIn("since overview.md was written", json.loads(self.hook("stop"))["reason"])

    def test_heartbeat_on_every_stop_of_an_open_goal(self):
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.spend(g, 42000)
        self.hook("stop")
        self.assertRegex(self.read(os.path.join(g, ".heartbeat")), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\S* 42k\n?$")

    def test_closed_goal_measured_once_then_cache_deleted(self):
        g = self.running_goal()
        cache = os.path.join(g, ".spend-cache.json")
        self.spend(g, 5000)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.hook("stop")
        self.assertTrue(os.path.exists(cache))
        s = self.read(self.plan(g)).replace("status: running", "status: aborted")
        open(self.plan(g), "w", encoding="utf-8").write(s)
        self.spend(g, 4000)
        self.hook("stop")
        self.assertRegex(self.read(self.plan(g)), r"budget: ~9k /")  # final spend written
        self.assertFalse(os.path.exists(cache))
        self.spend(g, 20000)
        self.hook("stop")
        self.assertRegex(self.read(self.plan(g)), r"budget: ~9k /")  # closed and no cache: not measured again
        self.assertFalse(os.path.exists(cache))

    def test_earlier_closed_goal_cache_deleted_after_moving_on(self):
        g = self.running_goal()
        cache = os.path.join(g, ".spend-cache.json")
        self.spend(g, 5000)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.hook("stop")
        self.assertTrue(os.path.exists(cache))
        s = self.read(self.plan(g)).replace("status: running", "status: aborted")
        open(self.plan(g), "w", encoding="utf-8").write(s)
        nxt = self.running_goal("next")  # closed and the next goal started before any turn ended
        self.run_s("log.py", os.path.join(nxt, "log.md"), "E", "wait agent")
        self.hook("stop")
        self.assertFalse(os.path.exists(cache))
        self.assertRegex(self.read(self.plan(g)), r"budget: ~5k /")  # final spend kept

    def test_done_goal_cache_stays_deleted_after_the_close_check(self):
        g = self.running_goal()
        cache = os.path.join(g, ".spend-cache.json")
        self.spend(g, 5000)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.hook("stop")  # running: measured, cache kept
        self.assertTrue(os.path.exists(cache))
        s = self.read(self.plan(g)).replace("status: running", "status: done")
        open(self.plan(g), "w", encoding="utf-8").write(s)
        self.spend(g, 2000)
        self.hook("stop")  # measures, deletes the cache, then runs close-check (which rebuilt it before)
        self.assertRegex(self.read(self.plan(g)), r"budget: ~7k /")
        self.assertFalse(os.path.exists(cache))
        r = subprocess.run([sys.executable, os.path.join(S, "close-check.py"), g], capture_output=True, text=True, env=self.env())
        self.assertFalse(os.path.exists(cache), r.stdout)

    def test_closed_goal_cut_by_the_deadline_keeps_its_cache(self):
        # measure() stops at its deadline (measure.partial); deleting the cache then would lose the rest of the
        # spend, so the next Stop finishes reading it and only then deletes the cache
        g = self.running_goal()
        cache = os.path.join(g, ".spend-cache.json")
        self.spend(g, 1000)
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.hook("stop")
        s = self.read(self.plan(g)).replace("status: running", "status: aborted")
        open(self.plan(g), "w", encoding="utf-8").write(s)
        for _ in range(6):
            self.spend(g, 1000)
        hook = self.skill_with_close_check("sys.exit(0)")
        src = self.read(hook)
        self.assertIn("HOOK_BUDGET = 6.0", src)
        open(hook, "w", encoding="utf-8").write(src.replace("HOOK_BUDGET = 6.0", "HOOK_BUDGET = -1.0", 1))  # always past
        self.hook("stop", hook=hook)
        self.assertTrue(os.path.exists(cache))  # out of time: kept for the next Stop
        for _ in range(10):
            if not os.path.exists(cache):
                break
            self.hook("stop")  # a Stop with time finishes it
        self.assertFalse(os.path.exists(cache))
        self.assertRegex(self.read(self.plan(g)), r"budget: ~7k /")

    def test_close_check_from_the_hook_gets_a_spend_deadline(self):
        hook = self.skill_with_close_check("print('deadline', os.environ.get('MAMA_SPEND_DEADLINE')); sys.exit(1)")
        self.done_goal_with_another_problem()
        t = time.time()
        reason = json.loads(self.hook("stop", hook=hook))["reason"]
        m = re.search(r"deadline ([\d.]+)", reason)
        self.assertTrue(m, reason)
        self.assertLess(float(m.group(1)), t + 5)  # inside the hook's close-check budget
        self.assertGreater(float(m.group(1)), t)


class HookDeadline(HookBase):
    """Claude Code kills the Stop hook at 10s: every measure shares one deadline, a cut measure is not
    the spend, and the close check of a done goal is not starved by the hook's own measure."""

    def closed_with_cache(self, slug):
        g = self.running_goal(slug)
        s = self.read(self.plan(g)).replace("status: running", "status: aborted")
        open(self.plan(g), "w", encoding="utf-8").write(s)
        open(os.path.join(g, ".spend-cache.json"), "w").write("{}")
        return g

    def test_every_measure_shares_one_deadline_inside_the_kill(self):
        hook = self.skill_with_close_check("sys.exit(0)")
        rec = os.path.join(self.tmp, "deadlines")
        # each measure runs until its deadline (as a huge transcript would), and is cut there
        self.stub_spend(hook, f"open({rec!r}, 'a').write(repr(deadline) + chr(10))\n"
                              "time.sleep(max(0.0, (deadline or time.time() + DEADLINE) - time.time()))\n"
                              "measure.partial = True\nreturn 1000")
        self.closed_with_cache("old1")
        self.closed_with_cache("old2")
        self.running_goal("cur")
        t = time.time()
        out = self.hook("stop", hook=hook)
        self.assertLess(time.time() - t, 9)  # under Claude Code's 10s kill
        self.assertIn("still marked running", json.loads(out)["reason"])
        ds = [float(l) for l in self.read(rec).split()] if os.path.exists(rec) else []
        self.assertTrue(ds and len(set(ds)) == 1, ds)  # one deadline for all (the rest skipped once it passed)
        self.assertLess(ds[0], t + 8.5)

    def test_clock_starts_before_any_import(self):
        import ast
        body = ast.parse(self.read(HOOK)).body
        if isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
            body = body[1:]  # the docstring
        self.assertEqual(ast.dump(body[0]), ast.dump(ast.parse("import time").body[0]))
        first = ast.unparse(body[1]) if hasattr(ast, "unparse") else ""
        if first:
            self.assertRegex(first, r"^\w+ = time\.time\(\)")
        budget = re.search(r"^HOOK_BUDGET = ([\d.]+)", self.read(HOOK), re.M)
        # up to ~2.5s before T0 (bash, the launcher's probe, Python start on cold Windows) + the budget
        # must leave at least 1.5s of Claude Code's 10s for work past the deadline
        self.assertTrue(budget, budget)
        self.assertEqual(float(budget.group(1)), 6.0)
        self.assertLessEqual(2.5 + float(budget.group(1)) + 1.5, 10)

    def test_deadline_is_budget_from_the_hook_start(self):
        hook = self.skill_with_close_check("sys.exit(0)")
        rec = os.path.join(self.tmp, "deadlines")
        self.stub_spend(hook, f"open({rec!r}, 'a').write(repr(deadline) + chr(10))\nreturn None")
        self.running_goal()
        t = time.time()
        self.hook("stop", hook=hook)
        ds = [float(l) for l in self.read(rec).split()]
        self.assertTrue(ds, ds)
        self.assertLess(ds[0], t + 6.5)  # 6s from the file's first statement, process start included

    def test_failed_spend_measure_is_a_problem_and_logged(self):
        hook = self.skill_with_close_check("sys.exit(0)")
        self.stub_spend(hook, "raise RuntimeError('disk  gone')")
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        reason = json.loads(self.hook("stop", hook=hook))["reason"]
        self.assertIn("spend not measured: RuntimeError: disk gone — see ~/.claude/mama/hook-errors.log", reason)
        self.assertIn("RuntimeError: disk gone", self.read(os.path.join(self.home, ".claude", "mama", "hook-errors.log")))
        self.assertRegex(self.read(os.path.join(g, ".heartbeat")), r"^\S+ -\n?$")

    def test_cut_measure_still_writes_a_heartbeat(self):
        hook = self.skill_with_close_check("sys.exit(0)")
        self.stub_spend(hook, "measure.partial = True\nreturn 900000")
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.hook("stop", hook=hook)
        self.assertRegex(self.read(os.path.join(g, ".heartbeat")), r"^\S+ -\n?$")

    def test_optional_check_errors_are_logged(self):
        hook = self.skill_with_close_check("sys.exit(0)")
        with open(os.path.join(os.path.dirname(os.path.dirname(hook)), "scripts", "close-check.py"), "a",
                  encoding="utf-8") as f:
            f.write("\n\ndef hunt_rounds(*a, **k):\n    raise ValueError('hunt boom')\n")
        g = self.running_goal()
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        self.assertEqual(self.hook("stop", hook=hook), "")
        self.assertIn("ValueError: hunt boom", self.read(os.path.join(self.home, ".claude", "mama", "hook-errors.log")))

    def test_partial_spend_is_not_written_or_judged(self):
        hook = self.skill_with_close_check("sys.exit(0)")
        self.stub_spend(hook, "measure.partial = True\nreturn 900000")
        g = self.running_goal()  # autonomous, M = 1M
        self.run_s("log.py", os.path.join(g, "log.md"), "E", "wait agent")
        before = re.search(r"budget: [^|\n]*", self.read(self.plan(g))).group(0)
        self.assertEqual(self.hook("stop", hook=hook), "")  # 90% of a cut read: not judged
        self.assertIn(before, self.read(self.plan(g)))
        self.assertNotIn("~900k", self.read(self.plan(g)))

    def test_closed_goal_measure_skipped_under_min_work(self):
        # less than MIN_WORK left: stop() skips a closed goal's measure (the cache stays for a later Stop);
        # with time left it measures, and a cut measure keeps the cache too
        hook = self.skill_with_close_check("sys.exit(0)")
        rec = os.path.join(self.tmp, "calls")
        self.stub_spend(hook, f"open({rec!r}, 'a').write('x')\nmeasure.partial = True\nreturn 1000")
        g = self.closed_with_cache("old")
        cache = os.path.join(g, ".spend-cache.json")
        short = os.path.join(os.path.dirname(hook), "short-hook.py")
        open(short, "w", encoding="utf-8").write(self.read(hook).replace("HOOK_BUDGET = 6.0", "HOOK_BUDGET = -1.0", 1))
        self.hook("stop", hook=short)
        self.assertFalse(os.path.exists(rec))  # not measured
        self.assertTrue(os.path.exists(cache))
        self.hook("stop", hook=hook)
        self.assertEqual(self.read(rec), "x")  # measured, cut: cache kept
        self.assertTrue(os.path.exists(cache))

    def test_done_goal_close_check_not_starved_by_the_measure(self):
        hook = self.skill_with_close_check("sys.exit(0)")
        self.stub_spend(hook, "time.sleep(max(0.0, (deadline or time.time() + DEADLINE) - time.time()))\n"
                              "measure.partial = True\nreturn 1000")
        g = self.done_goal_with_another_problem()
        open(os.path.join(g, ".spend-cache.json"), "w").write("{}")  # its final measure still to do
        t = time.time()
        reason = json.loads(self.hook("stop", hook=hook))["reason"]
        self.assertLess(time.time() - t, 9)
        self.assertIn("nothing was learned", reason)
        self.assertNotIn("close check didn't finish", reason)

    def test_no_optional_check_past_the_deadline(self):
        # the spend read uses the whole budget; the close checklist's helpers the optional checks load are slow:
        # past DEADLINE they are skipped and the block goes out with what was gathered
        hook = self.skill_with_close_check("sys.exit(0)")
        rec = os.path.join(self.tmp, "slow-calls")
        with open(os.path.join(os.path.dirname(os.path.dirname(hook)), "scripts", "close-check.py"), "a",
                  encoding="utf-8") as f:
            for fn in ("overview_problems", "hunt_rounds", "actual_minutes", "waiting_minutes"):
                f.write(f"\n\ndef {fn}(*a, **k):\n    open({rec!r}, 'a').write('{fn} ')\n"
                        "    time.sleep(3)\n    return [] if '{fn}' != 'actual_minutes' else None\n".replace("{fn}", fn))
        self.stub_spend(hook, "time.sleep(max(0.0, (deadline or time.time() + DEADLINE) - time.time()))\n"
                              "measure.partial = True\nreturn 1000")
        g = self.running_goal()
        s = self.read(self.plan(g)).replace("mode: autonomous", "mode: quick")
        open(self.plan(g), "w", encoding="utf-8").write(s)
        t = time.time()
        reason = json.loads(self.hook("stop", hook=hook))["reason"]
        self.assertLess(time.time() - t, 6.0 + 0.5 + 0.5)  # DEADLINE + 0.5s, plus Python's start before T0
        self.assertIn("still marked running", reason)
        self.assertFalse(os.path.exists(rec), self.read(rec) if os.path.exists(rec) else "")


if __name__ == "__main__":
    unittest.main()
