---
type: llm
focus: trace
weight: 1
---

After S1 and S2 were done, the run invoked /code-review on the goal's changes (a Skill call) and logged the round through scripts/log.py as one `E hunt 1: <n> found, <r> real, <x> fixed …` line that names /code-review; the run does not push before that line is logged, and if the round found a real bug, a fix step and another round followed.
