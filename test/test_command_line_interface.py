"""Test some features of the command line interface of khard."""

import io
import unittest
import unittest.mock as mock

from khard import khard


@mock.patch('sys.argv', ['TESTSUITE'])
class HelpOption(unittest.TestCase):

    def test_global_help(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                khard.main(['-h'])
        text = stdout.getvalue().splitlines()
        self.assertTrue(text[0].startswith('usage: TESTSUITE [-h]'))

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_subcommand_help(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                khard.main(['list', '-h'])
        text = stdout.getvalue().splitlines()
        self.assertTrue(text[0].startswith('usage: TESTSUITE list [-h]'))

    def test_global_help_with_subcommand(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                khard.main(['-h', 'list'])
        text = stdout.getvalue().splitlines()
        self.assertTrue(text[0].startswith('usage: TESTSUITE [-h]'))


if __name__ == "__main__":
    unittest.main()
