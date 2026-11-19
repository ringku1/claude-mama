import unittest

from price import parse_price


class ParsePriceTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_price("$5.99"), 5.99)

    def test_spaces(self):
        self.assertEqual(parse_price(" $3.50 "), 3.5)


if __name__ == "__main__":
    unittest.main()
