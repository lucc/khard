"""Test some features of the command line interface of khard.

This also contains some "end to end" tests.  That means some very high level
calls to the main function and a check against the output.  These might later
be converted to proper "unit" tests.
"""

import io
import unittest
import unittest.mock as mock

from khard import khard


def mock_stdout():
    stdout = io.StringIO()
    context_manager = mock.patch('sys.stdout', stdout)
    context_manager.getvalue = stdout.getvalue
    return context_manager


@mock.patch('sys.argv', ['TESTSUITE'])
class HelpOption(unittest.TestCase):

    def test_global_help(self):
        with self.assertRaises(SystemExit):
            with mock_stdout() as stdout:
                khard.main(['-h'])
        text = stdout.getvalue().splitlines()
        self.assertTrue(text[0].startswith('usage: TESTSUITE [-h]'))

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_subcommand_help(self):
        with self.assertRaises(SystemExit):
            with mock_stdout() as stdout:
                khard.main(['list', '-h'])
        text = stdout.getvalue().splitlines()
        self.assertTrue(text[0].startswith('usage: TESTSUITE list [-h]'))

    def test_global_help_with_subcommand(self):
        with self.assertRaises(SystemExit):
            with mock_stdout() as stdout:
                khard.main(['-h', 'list'])
        text = stdout.getvalue().splitlines()
        self.assertTrue(text[0].startswith('usage: TESTSUITE [-h]'))


@mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
class ListingCommands(unittest.TestCase):

    def test_simple_ls_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['list'])
        text = [l.strip() for l in stdout.getvalue().splitlines()]
        expected = [
            "Address book: foo",
            "Index    Name                                  Phone    E-Mail    UID",
            "1        one contact with minimal Vcard",
            "2        second contact with a simple Vcard                       1"]
        self.assertListEqual(text, expected)


if __name__ == "__main__":
    unittest.main()
