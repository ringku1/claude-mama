import unittest

from textkit import normalize


class NormalizeTest(unittest.TestCase):
    def test_collapses_spaces(self):
        self.assertEqual(normalize("  a   b \n c "), "a b c")


if __name__ == "__main__":
    unittest.main()
