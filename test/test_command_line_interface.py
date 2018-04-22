"""Test some features of the command line interface of khard.

This also contains some "end to end" tests.  That means some very high level
calls to the main function and a check against the output.  These might later
be converted to proper "unit" tests.
"""
# TODO We are still missing high level tests for the add-email and merge
# subcommands.  They depend heavily on user interaction and are hard to test in
# their current form.

import io
import pathlib
import shutil
import tempfile
import unittest
import unittest.mock as mock

from ruamel.yaml import YAML

from khard import khard

from .helpers import expectedFailureForVersion


def mock_stdout():
    stdout = io.StringIO()
    context_manager = mock.patch('sys.stdout', stdout)
    context_manager.getvalue = stdout.getvalue
    return context_manager


@mock.patch('sys.argv', ['TESTSUITE'])
class HelpOption(unittest.TestCase):

    def _test(self, args, expect):
        """Test the command line args and compare the prefix of the output."""
        with self.assertRaises(SystemExit):
            with mock_stdout() as stdout:
                khard.main(args)
        text = stdout.getvalue()
        self.assertTrue(text.startswith(expect))

    def test_global_help(self):
        self._test(['-h'], 'usage: TESTSUITE [-h]')

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    @mock.patch('khard.config.find_executable', lambda x: x)
    def test_subcommand_help(self):
        self._test(['list', '-h'], 'usage: TESTSUITE list [-h]')

    def test_global_help_with_subcommand(self):
        self._test(['-h', 'list'], 'usage: TESTSUITE [-h]')


@mock.patch('khard.config.find_executable', lambda x: x)
@mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
class ListingCommands(unittest.TestCase):
    """Tests for subcommands that simply list stuff."""

    def test_simple_ls_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['list'])
        text = [l.strip() for l in stdout.getvalue().splitlines()]
        expected = [
            "Address book: foo",
            "Index    Name              Phone                "
            "E-Mail                    UID",
            "1        second contact    voice: 0123456789    "
            "home: user@example.com    testuid1",
            "2        text birthday                          "
            "                          testuid3",
            "3        third contact                          "
            "                          testuid2"]
        self.assertListEqual(text, expected)

    @mock.patch.dict('os.environ', LC_ALL='C')
    def test_simple_bdays_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['birthdays'])
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Birthday",
                  "text birthday     circa 1800",
                  "second contact    01/20/18"]
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
        expect = ["test/fixture/foo.abook/contact1.vcf",
                  "test/fixture/foo.abook/text-bday.vcf",
                  "test/fixture/foo.abook/contact2.vcf"]
        self.assertListEqual(text, expect)

    def test_simple_abooks_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['addressbooks'])
        text = stdout.getvalue().strip()
        expect = "foo"
        self.assertEqual(text, expect)

    def test_simple_details_without_options(self):
        with mock_stdout() as stdout:
            khard.main(['details', 'uid1'])
        text = stdout.getvalue()
        # Currently the FN field is not shown with "details".
        self.assertIn('Address book: foo', text)
        self.assertIn('UID: testuid1', text)


@mock.patch('khard.config.find_executable', lambda x: x)
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
        shutil.copy('test/fixture/foo.abook/contact1.vcf', str(self.contact))
        config = path / 'conf'
        with config.open('w') as fh:
            fh.write(
                """[general]
                editor = editor
                merge_editor = meditor
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

    def test_simple_move(self):
        # just hide stdout
        with mock.patch('sys.stdout'):
            khard.main(['move', '-a', 'abook1', '-A', 'abook2', 'testuid1'])
        # The contact is moved to a filename based on the uid.
        target = self.abook2 / 'testuid1.vcf'
        # We currently only assert that the target file exists, nothing about
        # its contents.
        self.assertFalse(self.contact.exists())
        self.assertTrue(target.exists())

    def test_simple_copy(self):
        # just hide stdout
        with mock.patch('sys.stdout'):
            khard.main(['copy', '-a', 'abook1', '-A', 'abook2', 'testuid1'])
        # The contact is copied to a filename based on a new uid.
        results = list(self.abook2.glob('*.vcf'))
        self.assertTrue(self.contact.exists())
        self.assertEqual(len(results), 1)

    def test_simple_remove_with_force_option(self):
        # just hide stdout
        with mock.patch('sys.stdout'):
            # Without the --force this asks for confirmation.
            khard.main(['remove', '--force', '-a', 'abook1', 'testuid1'])
        results = list(self.abook2.glob('*.vcf'))
        self.assertFalse(self.contact.exists())
        self.assertEqual(len(results), 0)

    def test_new_contact_with_simple_user_input(self):
        old = len(list(self.abook1.glob('*.vcf')))
        # Mock user input on stdin (yaml format).
        with mock.patch('sys.stdin.isatty', return_value=False):
            with mock.patch('sys.stdin.read',
                            return_value='First name: foo\nLast name: bar'):
                # just hide stdout
                with mock.patch('sys.stdout'):
                    khard.main(['new', '-a', 'abook1'])
        new = len(list(self.abook1.glob('*.vcf')))
        self.assertEqual(new, old + 1)


@mock.patch('khard.config.find_executable', lambda x: x)
class MiscCommands(unittest.TestCase):
    """Tests for other subcommands."""

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_simple_export_without_options(self):
        with mock_stdout() as stdout:
            khard.main(["export", "uid1"])
        # This implicitly tests if the output is valid yaml.
        yaml = YAML(typ="base").load(stdout.getvalue())
        # Just test some keys.
        self.assertIn('Address', yaml)
        self.assertIn('Birthday', yaml)
        self.assertIn('Email', yaml)
        self.assertIn('First name', yaml)
        self.assertIn('Last name', yaml)
        self.assertIn('Nickname', yaml)

    @expectedFailureForVersion(3, 5)
    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_simple_edit_without_modification(self):
        with mock.patch('subprocess.Popen') as popen:
            # just hide stdout
            with mock.patch('sys.stdout'):
                khard.main(["modify", "uid1"])
        # The editor is called with a temp file so how to we check this more
        # precisely?
        popen.assert_called_once()

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_edit_source_file_without_modifications(self):
        with mock.patch('subprocess.Popen') as popen:
            # just hide stdout
            with mock.patch('sys.stdout'):
                khard.main(["source", "uid1"])
        popen.assert_called_once_with(['editor',
                                       'test/fixture/foo.abook/contact1.vcf'])


if __name__ == "__main__":
    unittest.main()
