"""Test some features of the command line interface of khard.

This also contains some "end to end" tests.  That means some very high level
calls to the main function and a check against the output.  These might later
be converted to proper "unit" tests.
"""

import io
import pathlib
import shutil
import tempfile
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
    """Tests for subcommands that simply list stuff."""

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

    def test_simple_file_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['filename'])
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["test/fixture/foo.abook/minimal.vcf",
                  "test/fixture/foo.abook/minimal2.vcf"]
        self.assertListEqual(text, expect)

    def test_simple_abooks_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['addressbooks'])
        text = stdout.getvalue().strip()
        expect = "foo"
        self.assertEqual(text, expect)


class FileSystemCommands(unittest.TestCase):
    """Tests for subcommands that interact with different address books."""

    def setUp(self):
        "Create a temporary directory with two address books and a configfile."
        self._tmp = tempfile.TemporaryDirectory()
        path = pathlib.Path(self._tmp.name)
        self.abook1 = path / 'abook1'
        self.abook2 = path / 'abook2'
        self.abook1.mkdir()
        self.abook2.mkdir()
        self.contact = self.abook1 / 'contact.vcf'
        shutil.copy('test/fixture/foo.abook/minimal2.vcf', self.contact)
        config = path / 'conf'
        config.write_text(
            """[general]
            editor = /bin/sh
            merge_editor = /bin/sh
            [addressbooks]
            [[abook1]]
            path = {}
            [[abook2]]
            path = {}
            """.format(self.abook1, self.abook2))
        self._patch = mock.patch.dict('os.environ', KHARD_CONFIG=str(config))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_simple_mv_without_options(self):
        khard.main(['move', '-a', 'abook1', '-A', 'abook2', 'testuid1'])
        # The contact is moved to a filename based on the uid.
        target = self.abook2 / 'testuid1.vcf'
        # We currently only assert that the target file exists, nothing about
        # its contents.
        self.assertFalse(self.contact.exists())
        self.assertTrue(target.exists())

    def test_simple_cp_without_options(self):
        khard.main(['copy', '-a', 'abook1', '-A', 'abook2', 'testuid1'])
        # The contact is copied to a filename based on a new uid.
        results = list(self.abook2.glob('*.vcf'))
        self.assertTrue(self.contact.exists())
        self.assertEqual(len(results), 1)

    def test_simple_remove_with_force_option(self):
        # Without the --force this asks for confirmation.
        khard.main(['remove', '--force', '-a', 'abook1', 'testuid1'])
        results = list(self.abook2.glob('*.vcf'))
        self.assertFalse(self.contact.exists())
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
