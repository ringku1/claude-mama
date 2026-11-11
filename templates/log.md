<!-- log.md — machine file, strictly APPEND-ONLY: every entry is one new line at the end. Never edit earlier lines.
Read with tail / grep by prefix, never in full. Delete this comment.

Write every line with scripts/log.py (it adds the ID and real time). Line shapes:
  Q<n>  HH:MM question | <text> | options: a / b / c | recommended: a
  D<n>  HH:MM decision | <question or Q-ref> | <choice> | why: ... | evidence: <file:line | cmd | source> | tag: verified|inferred|assumed|user
  D<n>  HH:MM supersedes D<m> | <new choice> | why: ...
  F<n>  HH:MM finding | <claim> | <file:line | source>      (a case to handle: F<n> HH:MM case: <branch> — <handled how | unknown>)
  E<n>  HH:MM <type> <step?> <text>

Event types: start, research: <n> findings, <m> cases, <k> open (or research none: <why>), ask, answer, plan, approve, checkpoint, dispatch, pass, fail, fix, block, unblock,
wait <what> (ending the turn on background work), learn <what|none>, commit <hash>, merge-base, conflict, push, pr <url>, trello, change, park, pause, resume, compaction (the PreCompact hook logs it), done.
Change example: E9 11:02 change goal: added sorting → +S7,S8; S4 obsolete; D3 revisit
Decisions in force: grep '^D' and drop any superseded.
-->

E1 HH:MM start <goal type> from <input source>
