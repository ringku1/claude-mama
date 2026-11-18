---
type: llm
focus: outcome
weight: 1
---

doc.html describes the user.deleted_at column: its type is TEXT, it can be empty (NULL), existing rows stay NULL, it is added by the migration 002_user_deleted_at.sql, and it was chosen over removing the row because support must be able to restore a user deleted by mistake.
