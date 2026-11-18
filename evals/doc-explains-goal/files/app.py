import pathlib
import sqlite3
import sys

MIGRATIONS = pathlib.Path(__file__).parent / "migrations"


def connect(path="app.db"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn):
    """Apply every migration in migrations/ once, in file-name order."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migration (name TEXT PRIMARY KEY)")
    applied = {row["name"] for row in conn.execute("SELECT name FROM schema_migration")}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name not in applied:
            conn.executescript(path.read_text())
            conn.execute("INSERT INTO schema_migration (name) VALUES (?)", (path.name,))
    conn.commit()


def add_user(conn, name, email):
    cur = conn.execute("INSERT INTO user (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    return cur.lastrowid


def get_profile(conn, user_id):
    row = conn.execute("SELECT id, name, email FROM user WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def render_profile(profile):
    return f"{profile['name']} <{profile['email']}>"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    conn = connect()
    migrate(conn)
    profile = get_profile(conn, int(argv[0]))
    print(render_profile(profile) if profile else "No such user")


if __name__ == "__main__":
    main()
