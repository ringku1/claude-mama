---
type: llm
focus: trace
weight: 1
---

The refund bug was fixed in a step of kind fix added through the scripts (plan-set.py or step.py, never by editing plan.md): a test for parse_price("-$5.00") == -5.0 was added in .claude/worktrees/mama-parse-prices and the trace shows it failing before price.py changed and passing after, with the step notes carrying `failing-first: <test>`.
