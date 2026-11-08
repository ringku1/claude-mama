<!-- log.md — machine file, strictly APPEND-ONLY: every entry is one new line at the end. Never edit earlier lines.
Read with tail / grep by prefix, never in full. Delete this comment.

Line prefixes (ID + clock time from `date +%H:%M`):
  Q<n>  HH:MM question | <text> | options: a / b / c | recommended: a
  D<n>  HH:MM decision | <question or Q-ref> | <choice> | why: ... | evidence: <file:line | cmd | source> | tag: verified|inferred|assumed|user
  D<n>  HH:MM supersedes D<m> | <new choice> | why: ...
  F<n>  HH:MM finding | <claim> | <file:line | source>
  E<n>  HH:MM <type> <step?> <text>

Event types: start, research, ask, answer, plan, approve, checkpoint, dispatch, pass, fail, fix, block, unblock,
commit <hash>, merge-base, conflict, push, pr <url>, trello, change, park, pause, resume, compaction, done.
Change example: E9 11:02 change goal: added sorting → +S7,S8; S4 obsolete; D3 revisit
Decisions in force: grep '^D' and drop any superseded.
-->

E1 HH:MM start <goal type> from <input source>
