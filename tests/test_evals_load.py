#!/usr/bin/env python3
"""Every eval case loads the way `claude plugin eval` (2.1.328) loads it, and passes the schema the
CLI enforces: case.yaml, prompt.md frontmatter and graders/*.md frontmatter. Runs nothing.
Run: cd tests && python3 -W ignore -m unittest test_evals_load

Stdlib only, so the YAML reader below covers just the subset the cases use: `key: value` maps
nested by indentation, `|` / `>` block scalars, flow lists `[a, b]`, flow maps `{a: b}`, quoted
strings, ints, floats and booleans. Anything else is an error, so a case can't drift past it.
"""
import os
import re
import shutil
import tempfile
import unittest

EVALS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evals")

TOP = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome"}
EXE = {"model", "max_turns", "timeout_seconds", "allowed_tools", "disallowed_tools",
       "artifact_publish", "growthbook_overrides", "append_system_prompt", "env"}
FOCUS = {"trace", "last_message", "files", "mock_calls"}
GRADER_KEYS = {
    "regex": ({"type", "name", "pattern"}, {"target", "flags", "match", "weight", "arm"}),
    "tool_order": ({"type", "name", "before", "after"}, {"weight", "arm"}),
    "tool_used": ({"type", "name", "tool"}, {"input_match", "min", "max", "weight", "arm"}),
    "file_exists": ({"type", "name", "path"}, {"exists", "weight", "arm"}),
    "llm": ({"type", "name", "criteria"}, {"focus", "weight", "arm"}),
    "baseline": ({"type", "name", "baseline_file", "criteria"}, {"weight", "arm"}),
}
FM = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)


class YamlError(ValueError):
    pass


# --- a minimal YAML reader -------------------------------------------------------------------

def _split_flow(s):
    """Split a flow collection's inside on top-level commas."""
    parts, depth, cur, quote = [], 0, "", None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch in "[{":
            depth += 1
            cur += ch
        elif ch in "]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if quote or depth:
        raise YamlError(f"unbalanced flow value: {s!r}")
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts]


def _scalar(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        return [_scalar(p) for p in _split_flow(s[1:-1])]
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for p in _split_flow(s[1:-1]):
            k, sep, v = p.partition(":")
            if not sep:
                raise YamlError(f"flow map entry without a colon: {p!r}")
            out[_scalar(k)] = _scalar(v)
        return out
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    if s[:1] in "[{\"'|>&*!%@`":
        raise YamlError(f"unsupported value: {s!r}")
    if s in ("", "~", "null"):
        return None
    if s in ("true", "false"):
        return s == "true"
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return re.sub(r"\s+#.*$", "", s)


def load_yaml(text):
    lines = [ln.rstrip("\r\n") for ln in text.split("\n")]

    def indent(ln):
        return len(ln) - len(ln.lstrip(" "))

    def skip(i):
        while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
            i += 1
        return i

    def block(i, ind):
        """A mapping whose keys sit at column ind, from line i; returns (dict, next line)."""
        out = {}
        i = skip(i)
        while i < len(lines):
            ln = lines[i]
            if "\t" in ln[:indent(ln) + 1]:
                raise YamlError(f"tab indent on line {i + 1}")
            if indent(ln) < ind:
                break
            if indent(ln) > ind:
                raise YamlError(f"unexpected indent on line {i + 1}: {ln!r}")
            m = re.match(r"([A-Za-z_][\w-]*):(?:\s+(.*)|\s*)$", ln.strip())
            if not m:
                raise YamlError(f"not a `key: value` line {i + 1}: {ln!r}")
            key, val = m.group(1), (m.group(2) or "").strip()
            if key in out:
                raise YamlError(f"duplicate key {key!r} on line {i + 1}")
            i += 1
            if val in ("|", ">", "|-", ">-"):
                body = []
                j = i
                while j < len(lines) and (not lines[j].strip() or indent(lines[j]) > ind):
                    body.append(lines[j])
                    j += 1
                while body and not body[-1].strip():
                    body.pop()
                if not body:
                    raise YamlError(f"empty block scalar for {key!r}")
                cut = min(indent(b) for b in body if b.strip())
                rows = [b[cut:] for b in body]
                out[key] = ("\n" if val[0] == "|" else " ").join(rows) + ("" if val.endswith("-") else "\n")
                i = j
            elif val == "":
                j = skip(i)
                if j < len(lines) and indent(lines[j]) > ind:
                    if lines[j].lstrip().startswith("- "):
                        raise YamlError(f"block lists are not supported (line {j + 1}); use [a, b]")
                    out[key], i = block(j, indent(lines[j]))
                else:
                    out[key] = None
            else:
                out[key] = _scalar(val)
            i = skip(i)
        return out, i

    data, i = block(0, 0)
    if skip(i) < len(lines):
        raise YamlError(f"unparsed text from line {i + 1}")
    return data


# --- the CLI's loader and schema (ported from validate_evals.py) -----------------------------

def front(text):
    m = FM.match(text)
    if not m:
        return {}, text, False
    return (load_yaml(m.group(1)) or {}), text[m.end():], True


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def focus_ok(f):
    if isinstance(f, str):
        return f in FOCUS
    return (isinstance(f, dict) and set(f) == {"source", "path"} and f["source"] == "file"
            and isinstance(f["path"], str))


def check_case(d):
    """Errors for case dir d (empty when it loads clean)."""
    errs = []
    case = {}
    cy = os.path.join(d, "case.yaml")
    if os.path.exists(cy):
        case = load_yaml(read(cy)) or {}
    case.setdefault("schema_version", "1.1")
    case.setdefault("name", os.path.basename(d))
    exe = dict(case.get("execution") or {})
    pm = os.path.join(d, "prompt.md")
    if os.path.exists(pm):
        fm, body, _ = front(read(pm))
        for k, v in fm.items():
            if k in TOP:
                case[k] = v
            elif k in EXE:
                exe[k] = v
            else:
                errs.append(f"prompt.md: unknown frontmatter key {k}")
        if body.strip():
            exe["prompt"] = body.strip()
    graders = list(case.get("graders") or [])
    gd = os.path.join(d, "graders")
    for f in sorted(os.listdir(gd)) if os.path.isdir(gd) else []:
        if not f.endswith(".md"):
            continue
        fm, body, had = front(read(os.path.join(gd, f)))
        if not had:
            continue
        g = dict(fm)
        g.setdefault("name", f[:-3])
        key = {"llm": "criteria", "baseline": "criteria", "regex": "pattern"}.get(g.get("type"))
        if key and key not in g and body.strip():
            g[key] = body.strip()
        graders.append(g)
    for k in case:
        if k not in TOP | {"context", "execution", "graders"}:
            errs.append(f"(root): unrecognized key {k}")
    if int(str(case["schema_version"]).split(".")[0]) > 1:
        errs.append("schema_version too new")
    ctx = case.get("context") or {}
    for k in ctx:
        if k not in {"scaffold_script", "history_file", "add_dirs"}:
            errs.append(f"context: unrecognized key {k}")
    if ctx.get("scaffold_script") and not os.path.exists(os.path.join(d, ctx["scaffold_script"])):
        errs.append("context.scaffold_script missing")
    mt = exe.get("max_turns", 10)
    if not (isinstance(mt, int) and not isinstance(mt, bool) and 0 < mt <= 200):
        errs.append("execution.max_turns")
    ts = exe.get("timeout_seconds", 300)
    if not (isinstance(ts, int) and not isinstance(ts, bool) and 0 < ts <= 3600):
        errs.append("execution.timeout_seconds")
    if not isinstance(exe.get("allowed_tools", []), list):
        errs.append("execution.allowed_tools")
    if not isinstance(case.get("tags", []), list):
        errs.append("tags")
    if not (exe.get("prompt") or "").strip():
        errs.append("execution.prompt is required")
    if not graders:
        errs.append("graders: at least 1")
    names = set()
    for i, g in enumerate(graders):
        t = g.get("type")
        if t not in GRADER_KEYS:
            errs.append(f"graders.{i}.type: Invalid input")
            continue
        req, opt = GRADER_KEYS[t]
        for k in sorted(req - set(g)):
            errs.append(f"graders.{i}.{k}: required")
        for k in sorted(set(g) - req - opt):
            errs.append(f"graders.{i}: unrecognized key {k}")
        if "focus" in g and not focus_ok(g["focus"]):
            errs.append(f"graders.{i}.focus: Invalid input")
        if "target" in g and not focus_ok(g["target"]):
            errs.append(f"graders.{i}.target: Invalid input")
        w = g.get("weight", 1)
        if not (isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0):
            errs.append(f"graders.{i}.weight")
        if g.get("arm") not in (None, "with-only", "both"):
            errs.append(f"graders.{i}.arm")
        if g.get("name") in names:
            errs.append(f'duplicate grader name "{g.get("name")}"')
        names.add(g.get("name"))
    return errs


def case_dirs(root=EVALS):
    return sorted(dp for dp, _, fn in os.walk(root)
                  if ("case.yaml" in fn or "prompt.md" in fn) and "results" not in dp.split(os.sep))


# --- tests -----------------------------------------------------------------------------------

class EvalCasesLoad(unittest.TestCase):
    def test_there_are_cases(self):
        self.assertTrue(case_dirs(), f"no eval cases under {EVALS}")


def _case_test(d):
    def test(self):
        try:
            errs = check_case(d)
        except YamlError as e:
            errs = [f"YAML: {e}"]
        self.assertEqual(errs, [], f"{os.path.basename(d)}: invalid case:\n  " + "\n  ".join(errs))
    return test


for _d in case_dirs():
    setattr(EvalCasesLoad, "test_" + re.sub(r"\W", "_", os.path.basename(_d)), _case_test(_d))


class ValidatorCatchesBadCases(unittest.TestCase):
    """The checker itself: a case with a mistake the CLI rejects must fail here too."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = os.path.join(self.tmp, "bad-case")
        os.makedirs(os.path.join(self.d, "graders"))
        self.write("case.yaml", 'schema_version: "1.1"\nname: bad-case\nexpected_outcome: |\n  It works.\n')
        self.write("prompt.md", "---\ntags: [x]\nmax_turns: 5\n---\n\n/mama status\n")

    def write(self, rel, text):
        with open(os.path.join(self.d, rel), "w", encoding="utf-8") as f:
            f.write(text)

    def test_good_case_passes(self):
        self.write("graders/01-ok.md", "---\ntype: llm\nfocus: trace\nweight: 1\n---\n\nIt works.\n")
        self.assertEqual(check_case(self.d), [])

    def test_focus_outcome_is_rejected(self):
        self.write("graders/01-bad.md", "---\ntype: llm\nfocus: outcome\nweight: 1\n---\n\nIt works.\n")
        self.assertIn("graders.0.focus: Invalid input", check_case(self.d))

    def test_file_focus_needs_source_and_path(self):
        self.write("graders/01-bad.md", "---\ntype: llm\nfocus: {path: doc.html}\n---\n\nIt works.\n")
        self.assertIn("graders.0.focus: Invalid input", check_case(self.d))

    def test_unknown_keys_and_missing_prompt(self):
        self.write("prompt.md", "---\nturns: 5\n---\n")
        self.write("graders/01-bad.md", "---\ntype: llm\nscore: 2\n---\n\nIt works.\n")
        errs = check_case(self.d)
        for e in ("prompt.md: unknown frontmatter key turns", "execution.prompt is required",
                  "graders.0: unrecognized key score"):
            self.assertIn(e, errs)

    def test_no_graders(self):
        self.assertIn("graders: at least 1", check_case(self.d))

    def test_unsupported_yaml_is_an_error(self):
        self.write("case.yaml", "name: bad-case\ntags:\n  - a\n")
        with self.assertRaises(YamlError):
            check_case(self.d)


class YamlSubset(unittest.TestCase):
    def test_reads_the_subset(self):
        self.assertEqual(load_yaml(
            'schema_version: "1.1"\nexpected_outcome: |\n  a\n  b\ncontext:\n  scaffold_script: x.sh\n'
            "tags: [a, b]\nfocus: {source: file, path: d/doc.html}\nmax_turns: 20\nw: 0.5\n"),
            {"schema_version": "1.1", "expected_outcome": "a\nb\n", "context": {"scaffold_script": "x.sh"},
             "tags": ["a", "b"], "focus": {"source": "file", "path": "d/doc.html"}, "max_turns": 20, "w": 0.5})


if __name__ == "__main__":
    unittest.main()
