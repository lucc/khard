"""Test some features of the command line interface of khard.

This also contains some "end to end" tests.  That means some very high level
calls to the main function and a check against the output.  These might later
be converted to proper "unit" tests.
"""
# pylint: disable=missing-docstring

# TODO We are still missing high level tests for the merge subcommand.  It
# depends heavily on user interaction and is hard to test in its current form.

import io
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

from ruamel.yaml import YAML

from khard import cli
from khard import config
from khard.helpers.interactive import Editor
from khard import khard

from .helpers import TmpConfig, mock_stream


def run_main(*args):
    """Run the khard.main() method with mocked stdout"""
    with mock_stream() as stdout:
        khard.main(args)
    return stdout


@mock.patch('sys.argv', ['TESTSUITE'])
class HelpOption(unittest.TestCase):

    def _test(self, args, expect):
        """Test the command line args and compare the prefix of the output."""
        with mock_stream() as stdout:
            with self.assertRaises(SystemExit):
                cli.parse_args(args)
        text = stdout.getvalue()
        self.assertRegex(text, expect)

    def test_global_help(self):
        self._test(['-h'], r'^usage: TESTSUITE \[-h\]')

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_subcommand_help(self):
        self._test(['list', '-h'], r'^usage: TESTSUITE list \[-h\]')

    def test_global_help_with_subcommand(self):
        self._test(['-h', 'list'], r'^usage: TESTSUITE \[-h\]')


@mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
class ListingCommands(unittest.TestCase):
    """Tests for subcommands that simply list stuff."""


    def test_simple_ls_without_options(self):
        stdout = run_main("list")
        text = [l.strip() for l in stdout.getvalue().splitlines()]
        expected = [
            "Address book: foo",
            "Index    Name              Phone                "
            "Email                     Uid",
            "1        second contact    voice: 0123456789    "
            "home: user@example.com    testuid1",
            "2        text birthday                          "
            "                          testuid3",
            "3        third contact                          "
            "                          testuid2"]
        self.assertListEqual(text, expected)

    def test_ls_fields_like_email(self):
        stdout = run_main('ls', '-p', '-F', 'emails.home.0,name')
        text = stdout.getvalue().splitlines()
        expected = [
            "user@example.com\tsecond contact",
            "\ttext birthday",
            "\tthird contact",
        ]
        self.assertListEqual(text, expected)

    @mock.patch.dict('os.environ', LC_ALL='C')
    def test_simple_bdays_without_options(self):
        stdout = run_main('birthdays')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Birthday",
                  "text birthday     circa 1800",
                  "second contact    01/20/18"]
        self.assertListEqual(text, expect)

    def test_parsable_bdays(self):
        stdout = run_main('birthdays', '--parsable')
        text = stdout.getvalue().splitlines()
        expect = ["circa 1800\ttext birthday", "2018.01.20\tsecond contact"]
        self.assertListEqual(text, expect)

    def test_simple_email_without_options(self):
        stdout = run_main('email')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Type    E-Mail",
                  "second contact    home    user@example.com"]
        self.assertListEqual(text, expect)

    def test_simple_phone_without_options(self):
        stdout = run_main('phone')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Type     Phone",
                  "second contact    voice    0123456789"]
        self.assertListEqual(text, expect)

    def test_simple_file_without_options(self):
        stdout = run_main('filename')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["test/fixture/test.abook/contact1.vcf",
                  "test/fixture/test.abook/text-bday.vcf",
                  "test/fixture/test.abook/contact2.vcf"]
        self.assertListEqual(text, expect)

    def test_simple_abooks_without_options(self):
        stdout = run_main('addressbooks')
        text = stdout.getvalue().strip()
        expect = "foo"
        self.assertEqual(text, expect)

    def test_simple_details_without_options(self):
        stdout = run_main('details', 'uid1')
        text = stdout.getvalue()
        # Currently the FN field is not shown with "details".
        self.assertIn('Address book: foo', text)
        self.assertIn('UID: testuid1', text)

    def test_order_of_search_term_does_not_matter(self):
        stdout1 = run_main('list', 'second', 'contact')
        stdout2 = run_main('list', 'contact', 'second')
        text1 = [l.strip() for l in stdout1.getvalue().splitlines()]
        text2 = [l.strip() for l in stdout2.getvalue().splitlines()]
        expected = [
            "Address book: foo",
            "Index    Name              Phone                "
            "Email                     Uid",
            "1        second contact    voice: 0123456789    "
            "home: user@example.com    testuid1"]
        self.assertListEqual(text1, expected)
        self.assertListEqual(text2, expected)

    def test_case_of_search_terms_does_not_matter(self):
        stdout1 = run_main('list', 'second', 'contact')
        stdout2 = run_main('list', 'SECOND', 'CONTACT')
        text1 = [l.strip() for l in stdout1.getvalue().splitlines()]
        text2 = [l.strip() for l in stdout2.getvalue().splitlines()]
        expected = [
            "Address book: foo",
            "Index    Name              Phone                "
            "Email                     Uid",
            "1        second contact    voice: 0123456789    "
            "home: user@example.com    testuid1"]
        self.assertListEqual(text1, expected)
        self.assertListEqual(text2, expected)

    def test_regex_special_chars_are_not_special(self):
        with mock_stream() as stdout:
            with self.assertRaises(SystemExit):
                khard.main(['list', 'uid.'])
        self.assertEqual(stdout.getvalue(), "Found no contacts\n")

    def test_display_post_address(self):
        with TmpConfig(["post.vcf"]):
            stdout = run_main('postaddress')
        text = [line.rstrip() for line in stdout.getvalue().splitlines()]
        expected = [
            'Name                 Type    Post address',
            'With post address    home    Main Street 1',
            '                             PostBox Ext',
            '                             00000 The City',
            '                             SomeState, HomeCountry']

        self.assertListEqual(expected, text)

    def test_email_lists_only_contacts_with_emails(self):
        with TmpConfig(["contact1.vcf", "contact2.vcf"]):
            stdout = run_main("email")
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Type    E-Mail",
                  "second contact    home    user@example.com"]
        self.assertListEqual(expect, text)

    def test_phone_lists_only_contacts_with_phone_nubers(self):
        with TmpConfig(["contact1.vcf", "contact2.vcf"]):
            stdout = run_main("phone")
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["Name              Type     Phone",
                  "second contact    voice    0123456789"]
        self.assertListEqual(expect, text)

    def test_postaddr_lists_only_contacts_with_post_addresses(self):
        with TmpConfig(["contact1.vcf", "post.vcf"]):
            stdout = run_main("postaddress")
        text = [line.rstrip() for line in stdout.getvalue().splitlines()]
        expect = ['Name                 Type    Post address',
                  'With post address    home    Main Street 1',
                  '                             PostBox Ext',
                  '                             00000 The City',
                  '                             SomeState, HomeCountry']
        self.assertListEqual(expect, text)

    def test_mixed_kinds(self):
        with TmpConfig(["org.vcf", "individual.vcf"]):
            stdout = run_main("list", "organisations:acme")
        text = [line.rstrip() for line in stdout.getvalue().splitlines()]
        expected = [
            "Address book: tmp",
            "Index    Name              Phone    Email    Kind            Uid",
            "1        ACME Inc.                           organisation    4",
            "2        Wile E. Coyote                      individual      1"]
        self.assertListEqual(expected, text)

    def test_non_individual_kind(self):
        with TmpConfig(["org.vcf"]):
            stdout = run_main("list")
        text = [line.rstrip() for line in stdout.getvalue().splitlines()]
        expected = [
            "Address book: tmp",
            "Index    Name         Phone    Email    Kind            Uid",
            "1        ACME Inc.                      organisation    4"]
        self.assertListEqual(expected, text)


class ListingCommands2(unittest.TestCase):

    def test_list_bug_195(self):
        with TmpConfig(['tel-value-uri.vcf']):
            stdout = run_main('list')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = [
            "Address book: tmp",
            "Index    Name       Phone             Email    Uid",
            "1        bug 195    cell: 67545678             b"]
        self.assertListEqual(text, expect)

    def test_list_bug_243_part_1(self):
        """Search for a category with the ls command"""
        with TmpConfig(['category.vcf']):
            stdout = run_main('list', 'bar')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = [
            "Address book: tmp",
            "Index    Name                     Phone    "
            "Email                        Uid",
            "1        contact with category             "
            "internet: foo@example.org    c",
        ]
        self.assertListEqual(text, expect)

    def test_list_bug_243_part_2(self):
        """Search for a category with the email command"""
        with TmpConfig(['category.vcf']):
            stdout = run_main('email', 'bar')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = [
            "Name                     Type        E-Mail",
            "contact with category    internet    foo@example.org",
        ]
        self.assertListEqual(text, expect)

    def test_list_bug_251(self):
        "Find contacts by nickname even if a match by name exists"
        with TmpConfig(["test/fixture/nick.abook/nickname.vcf",
                        "test/fixture/vcards/no-nickname.vcf"]):
            stdout = run_main('list', 'mike')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ['Address book: tmp',
                  'Index    Name             Phone    Email                   '
                  'Uid',
                  '1        Michael Smith             pref: ms@example.org    '
                  'issue251part1',
                  '2        Mike Jones                pref: mj@example.org    '
                  'issue251part2']
        self.assertListEqual(text, expect)

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/nick.conf')
    def test_email_bug_251(self):
        stdout = run_main('email', '--parsable', 'mike')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["searching for 'mike' ...",
                  "ms@example.org\tMichael Smith\tpref"]
        self.assertListEqual(text, expect)

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/nick.conf')
    def test_email_bug_251_part2(self):
        stdout = run_main('email', '--parsable', 'joe')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["searching for 'joe' ...",
                  "jcitizen@foo.com\tJoe Citizen\tpref"]
        self.assertListEqual(text, expect)

    def test_email_bug_251_part_3(self):
        "Find contacts by nickname even if a match by name exists"
        with TmpConfig(["test/fixture/nick.abook/nickname.vcf",
                        "test/fixture/vcards/no-nickname.vcf"]):
            stdout = run_main('email', '--parsable', 'mike')
        text = [line.strip() for line in stdout.getvalue().splitlines()]
        expect = ["searching for 'mike' ...",
                  'ms@example.org\tMichael Smith\tpref',
                  'mj@example.org\tMike Jones\tpref']
        self.assertListEqual(text, expect)


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
        shutil.copy('test/fixture/vcards/contact1.vcf', str(self.contact))
        config = path / 'conf'
        with config.open('w') as fh:
            fh.write("""[addressbooks]
                        [[abook1]]
                        path = {}
                        [[abook2]]
                        path = {}""".format(self.abook1, self.abook2))
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
                    # hide warning about missing version in vcard
                    with self.assertLogs(level='WARNING'):
                        khard.main(['new', '-a', 'abook1'])
        new = len(list(self.abook1.glob('*.vcf')))
        self.assertEqual(new, old + 1)


class MiscCommands(unittest.TestCase):
    """Tests for other subcommands."""

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_simple_show_with_yaml_format(self):
        stdout = run_main("show", "--format=yaml", "uid1")
        # This implicitly tests if the output is valid yaml.
        yaml = YAML(typ="base").load(stdout.getvalue())
        # Just test some keys.
        self.assertIn('Address', yaml)
        self.assertIn('Birthday', yaml)
        self.assertIn('Email', yaml)
        self.assertIn('First name', yaml)
        self.assertIn('Last name', yaml)
        self.assertIn('Nickname', yaml)

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
    def test_simple_edit_without_modification(self):
        editor = mock.Mock()
        editor.edit_templates = mock.Mock(return_value=None)
        editor.write_temp_file = Editor.write_temp_file
        with mock.patch('khard.khard.interactive.Editor',
                        mock.Mock(return_value=editor)):
            run_main("edit", "uid1")
        # The editor is called with a temp file so how to we check this more
        # precisely?
        editor.edit_templates.assert_called_once()

    @mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf',
                     EDITOR='editor')
    def test_edit_source_file_without_modifications(self):
        with mock.patch('subprocess.Popen') as popen:
            run_main("edit", "--format=vcard", "uid1")
        popen.assert_called_once_with(['editor',
                                       'test/fixture/test.abook/contact1.vcf'])


@mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
class CommandLineDefaultsDoNotOverwriteConfigValues(unittest.TestCase):

    @staticmethod
    def _with_contact_table(args, **kwargs):
        args = cli.parse_args(args)
        options = '\n'.join('{}={}'.format(key, kwargs[key]) for key in kwargs)
        conf = config.Config(io.StringIO('[addressbooks]\n[[test]]\npath=.\n'
                                         '[contact table]\n' + options))
        return cli.merge_args_into_config(args, conf)

    def test_group_by_addressbook(self):
        conf = self._with_contact_table(['list'], group_by_addressbook=True)
        self.assertTrue(conf.group_by_addressbook)


@mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
class CommandLineArgumentsOverwriteConfigValues(unittest.TestCase):

    @staticmethod
    def _merge(args):
        args, _conf = cli.parse_args(args)
        # This config file just loads all defaults from the config.spec.
        conf = config.Config(io.StringIO('[addressbooks]\n[[test]]\npath=.'))
        return cli.merge_args_into_config(args, conf)

    def test_sort_is_picked_up_from_arguments(self):
        conf = self._merge(['list', '--sort=last_name'])
        self.assertEqual(conf.sort, 'last_name')

    def test_display_is_picked_up_from_arguments(self):
        conf = self._merge(['list', '--display=last_name'])
        self.assertEqual(conf.display, 'last_name')

    def test_reverse_is_picked_up_from_arguments(self):
        conf = self._merge(['list', '--reverse'])
        self.assertTrue(conf.reverse)

    def test_group_by_addressbook_is_picked_up_from_arguments(self):
        conf = self._merge(['list', '--group-by-addressbook'])
        self.assertTrue(conf.group_by_addressbook)

    def test_search_in_source_is_picked_up_from_arguments(self):
        conf = self._merge(['list', '--search-in-source-files'])
        self.assertTrue(conf.search_in_source_files)


class Merge(unittest.TestCase):

    def test_merge_with_exact_search_terms(self):
        with TmpConfig(["contact1.vcf", "contact2.vcf"]):
            with mock.patch('khard.khard.merge_existing_contacts') as merge:
                run_main("merge", "second", "--target", "third")
        merge.assert_called_once()
        # unpack the call arguments
        call = merge.mock_calls[0]
        name, args, kwargs = call
        first, second, delete = args
        self.assertTrue(delete)
        first = pathlib.Path(first.filename).name
        second = pathlib.Path(second.filename).name
        self.assertEqual('contact1.vcf', first)
        self.assertEqual('contact2.vcf', second)

    def test_merge_with_exact_uid_search_terms(self):
        with TmpConfig(["contact1.vcf", "contact2.vcf"]):
            with mock.patch('khard.khard.merge_existing_contacts') as merge:
                run_main("merge", "uid:testuid1", "--target", "uid:testuid2")
        merge.assert_called_once()
        # unpack the call arguments
        call = merge.mock_calls[0]
        name, args, kwargs = call
        first, second, delete = args
        self.assertTrue(delete)
        first = pathlib.Path(first.filename).name
        second = pathlib.Path(second.filename).name
        self.assertEqual('contact1.vcf', first)
        self.assertEqual('contact2.vcf', second)


class AddEmail(unittest.TestCase):

    @TmpConfig(["contact1.vcf", "contact2.vcf"])
    def test_contact_is_found_if_name_matches(self):
        email = [
            "From: third <third@example.com>\n",
            "To: anybody@example.com\n",
            "\n",
            "text\n"
        ]
        with tempfile.NamedTemporaryFile("w") as tmp:
            tmp.writelines(email)
            tmp.flush()
            with mock.patch("builtins.input",
                            mock.Mock(side_effect=["y", "y", ""])):
                run_main("add-email", "--input-file", tmp.name)
        emails = khard.config.abooks.get_short_uid_dict()["testuid2"].emails
        self.assertEqual(emails["internet"][0], "third@example.com")

    @TmpConfig(["contact1.vcf", "contact2.vcf"])
    def test_adding_several_email_addresses(self):
        email = [
            "From: third <third@example.com>\n",
            "To: anybody@example.com\n",
            "\n",
            "text\n"
        ]
        with tempfile.NamedTemporaryFile("w") as tmp:
            tmp.writelines(email)
            tmp.flush()
            with mock.patch("builtins.input", mock.Mock(side_effect=[
                    "y", "y", "label1", "y", "third contact", "y", "label2"])):
                run_main("add-email", "--headers=from,to", "--input-file",
                         tmp.name)
        emails = khard.config.abooks.get_short_uid_dict()["testuid2"].emails
        self.assertEqual(emails["label1"][0], "third@example.com")
        self.assertEqual(emails["label2"][0], "anybody@example.com")

    @TmpConfig(["contact1.vcf", "contact2.vcf"])
    def test_email_addresses_can_be_skipped(self):
        email = [
            "From: third <third@example.com>\n",
            "To: anybody@example.com\n",
            "\n",
            "text\n"
        ]
        with tempfile.NamedTemporaryFile("w") as tmp:
            tmp.writelines(email)
            tmp.flush()
            with mock.patch("builtins.input", lambda _: "n"):
                run_main("add-email", "--input-file", tmp.name)
        contacts = khard.config.abooks.get_short_uid_dict().values()
        emails1 = [c.emails for c in contacts if c.emails]
        emails2 = [list(e.values()) for e in emails1]
        emails = [eee for e in emails2 for ee in e for eee in ee]
        self.assertNotIn("third@example.com", emails)


if __name__ == "__main__":
    unittest.main()
