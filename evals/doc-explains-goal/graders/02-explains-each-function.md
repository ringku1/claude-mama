---
type: llm
focus: outcome
weight: 1
---

doc.html names delete_user and get_profile and says in plain words what each does: delete_user sets deleted_at on a user who isn't already deleted (so deleting twice changes nothing), and get_profile skips users whose deleted_at is set, which is why a deleted user's profile shows "No such user".
