import unittest

from cart import total


class TotalTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total([1.5, 2.25]), 3.75)


if __name__ == "__main__":
    unittest.main()
