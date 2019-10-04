"""Tests for the config module."""

import io
import unittest
import unittest.mock as mock

from khard import config


class LoadingConfigFile(unittest.TestCase):

    def test_load_non_existing_file_fails(self):
        filename = "I hope this file never exists"
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                config.Config(filename)
        self.assertEqual(stdout.getvalue(),
                         "Config file " + filename + " not available\n")

    def test_load_empty_file_fails(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                config.Config("/dev/null")
        self.assertTrue(stdout.getvalue().startswith('Error in config file\n'))

    @mock.patch.dict('os.environ', EDITOR='editor', MERGE_EDITOR='meditor')
    def test_load_minimal_file_by_name(self):
        cfg = config.Config("test/fixture/minimal.conf")
        self.assertEqual(cfg.editor, "editor")
        self.assertEqual(cfg.merge_editor, "meditor")


class ConfigPreferredVcardVersion(unittest.TestCase):

    def test_default_value_is_3(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.get_preferred_vcard_version(), "3.0")

    def test_set_preferred_version(self):
        c = config.Config("test/fixture/minimal.conf")
        c.set_preferred_vcard_version("11")
        self.assertEqual(c.get_preferred_vcard_version(), "11")


class Defaults(unittest.TestCase):

    def test_debug_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.debug)

    def test_default_action_defaults_to_list(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.default_action, 'list')

    def test_reverse_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.reverse())

    def test_group_by_addressbook_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.group_by_addressbook())

    def test_show_nicknames_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.show_nicknames())

    def test_show_uids_defaults_to_true(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertTrue(c.has_uids())

    def test_sort_defaults_to_first_name(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.sort, 'first_name')

    def test_display_defaults_to_first_name(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.display_by_name(), 'first_name')

    def test_localize_dates_defaults_to_true(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertTrue(c.localize_dates())

    def test_preferred_phone_number_type_defaults_to_pref(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertListEqual(c.preferred_phone_number_type(), ['pref'])

    def test_preferred_email_address_type_defaults_to_pref(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertListEqual(c.preferred_email_address_type(), ['pref'])

    def test_private_objects_defaults_to_empty(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertListEqual(c.get_supported_private_objects(), [])

    def search_in_source_files_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.search_in_source_files())

    def skip_unparsable_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.skip_unparsable())

    def preferred_version_defaults_to_3(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.get_preferred_vcard_version(), '3.0')

    @mock.patch.dict('os.environ', clear=True)
    def test_editor_defaults_to_vim(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.editor, 'vim')

    @mock.patch.dict('os.environ', clear=True)
    def test_merge_editor_defaults_to_vimdiff(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.merge_editor, 'vimdiff')


if __name__ == "__main__":
    unittest.main()
