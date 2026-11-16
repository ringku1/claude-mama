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


if __name__ == "__main__":
    unittest.main()
