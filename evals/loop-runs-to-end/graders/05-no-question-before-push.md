---
type: llm
focus: trace
weight: 1
---

The run asked the user nothing until the branch was pushed: no AskUserQuestion call, no question in a reply and no status set to waiting before `git push` to origin succeeded (and `E pushed …` was logged); the run's first question is the PR one at the end, showing a draft PR title and body, since pr is ask-at-end.
