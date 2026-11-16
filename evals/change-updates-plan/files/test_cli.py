import contextlib
import io
import unittest

import cli


class GreetTest(unittest.TestCase):
    def test_name(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(["--name", "Ada"])
        self.assertEqual(out.getvalue(), "Hello, Ada!\n")


if __name__ == "__main__":
    unittest.main()
