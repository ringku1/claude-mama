# Let admins delete a user

**Status:** Done · 2 of 2 parts done

## Goal

Let an admin delete a user so they no longer appear anywhere, while keeping the record so support can bring them back.

**Started from:** your message

## Done means

- [x] A deleted user's profile shows "No such user", and their record is kept — the app's tests for deleting and hiding a user pass

## Timeline

| When  | What                                  |
| ----- | ------------------------------------- |
| 10:02 | Started; looked at the users table    |
| 10:12 | You chose to keep deleted users' data |
| 10:18 | Plan approved                         |
| 10:38 | Deleting works and is tested          |
| 10:46 | Done                                  |

## Where we are

Finished. Deleting a user hides them and keeps their record.

## Key decisions

- Deleted users are hidden, not erased, so support can restore one deleted by mistake.
- Deleting a user twice does nothing the second time.

## Branch & PR

Branch `feat/delete-user` from `main` · PR: not requested

## Final report

Admins can delete a user: the profile then shows "No such user" and the record stays, marked with the time it was deleted. Checked by the app's tests, all passing, and one review round that found nothing. A restore command for support is parked for later.
