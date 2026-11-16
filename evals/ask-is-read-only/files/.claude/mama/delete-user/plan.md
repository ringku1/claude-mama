goal: delete-user | type: build | status: done | mode: checkpointed
progress: 2/2 (100%) | blocked: 0 | budget: ~140k / S | approved: S
base: main | branch: feat/delete-user | worktree: __WORKTREE__ | pr: none | deliverable commit: n/a | trello: none
started: 2026-11-10 10:02

## Criteria

| id  | criterion | proven by | evidence |
| --- | --------- | --------- | -------- |
| C1 | a deleted user's profile shows "No such user"; the row stays and can be restored | S1,S2 | python -m unittest test_app: 3 passed |

## Steps

| id  | kind  | title | deps | owns | verify | status | att | est | start | end | notes |
| --- | ----- | ----- | ---- | ---- | ------ | ------ | --- | --- | ----- | --- | ----- |
| S1 | build | soft-delete a user and hide them from profiles | — | migrations/002_user_deleted_at.sql, app.py | python -m unittest test_app | done | 0 | 15m | 10:20 | 10:31 | D1 · commit __SHA__ |
| S2 | build | test that a deleted user is hidden and kept | S1 | test_app.py | python -m unittest test_app | done | 0 | 10m | 10:31 | 10:38 | commit __SHA__ |

## Parked

- a restore command for support (the column already allows it)
