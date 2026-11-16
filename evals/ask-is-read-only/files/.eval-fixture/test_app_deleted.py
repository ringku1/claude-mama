import unittest

import app


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.conn = app.connect(":memory:")
        app.migrate(self.conn)

    def test_profile(self):
        user_id = app.add_user(self.conn, "Ada", "ada@example.com")
        profile = app.get_profile(self.conn, user_id)
        self.assertEqual(app.render_profile(profile), "Ada <ada@example.com>")

    def test_missing_user(self):
        self.assertIsNone(app.get_profile(self.conn, 99))

    def test_deleted_user_is_hidden(self):
        user_id = app.add_user(self.conn, "Ada", "ada@example.com")
        app.delete_user(self.conn, user_id)
        app.delete_user(self.conn, user_id)
        self.assertIsNone(app.get_profile(self.conn, user_id))
        row = self.conn.execute("SELECT deleted_at FROM user WHERE id = ?", (user_id,)).fetchone()
        self.assertIsNotNone(row["deleted_at"])


if __name__ == "__main__":
    unittest.main()
