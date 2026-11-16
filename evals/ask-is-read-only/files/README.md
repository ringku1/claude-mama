# people

A tiny app that stores users in SQLite and prints a user's profile.

## Usage

    python app.py 1

## Database

Schema changes are new numbered files in `migrations/` (`NNN_snake_case.sql`), applied in order by `migrate()`. Never edit a migration that has been applied. Table names are singular.

## Tests

    python -m unittest test_app
