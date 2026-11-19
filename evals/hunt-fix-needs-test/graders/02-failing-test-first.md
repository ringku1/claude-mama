---
type: llm
focus: trace
weight: 1
---

Before price.py was changed, a test reproducing the bug (e.g. parse_price("$1,200") == 1200 or parse_price("$1,200.50") == 1200.5) was added in .claude/worktrees/mama-parse-prices and run, and the trace shows that run failing; after the fix the same test passes along with the existing test_price tests.
