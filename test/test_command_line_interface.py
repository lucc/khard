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
            "Index    Name               Phone                E-Mail                    UID",
            "1        minimal contact",
            "2        second contact     voice: 0123456789    home: user@example.com    t"]
        self.assertListEqual(text, expected)

    def test_simple_bdays_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['birthdays'])
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Birthday",
                  "second contact    01/20/2018"]
        self.assertListEqual(text, expect)

    def test_simple_email_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['email'])
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Type    E-Mail",
                  "second contact    home    user@example.com"]
        self.assertListEqual(text, expect)

    def test_simple_phone_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['phone'])
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Type     Phone",
                  "second contact    voice    0123456789"]
        self.assertListEqual(text, expect)


if __name__ == "__main__":
    unittest.main()
