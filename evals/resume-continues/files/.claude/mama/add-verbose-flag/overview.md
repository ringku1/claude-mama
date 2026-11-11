# Add a --verbose flag to the CLI

**Status:** Paused · 1 of 3 parts done

## Goal

Add a `--verbose` option to the command-line tool so it prints a debug line when asked, without changing normal output.

**Started from:** your message

## Done means

- [ ] With --verbose, a debug line goes to stderr; without it, output is unchanged

## Timeline

| When  | What                                        |
| ----- | ------------------------------------------- |
| 16:37 | Started; looked at the CLI code             |
| 16:37 | Plan approved                               |
| 16:37 | The option is accepted; paused at your ask  |

## Where we are

The CLI accepts --verbose. Next: print the debug line, then add a test.

## Key decisions

- Debug output goes to stderr, so piped output stays clean.

## Branch & PR

Branch `feat/verbose-flag` from `main` · PR: not requested
