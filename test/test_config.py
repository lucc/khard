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

    def test_load_minimal_file_by_name(self):
        cfg = config.Config("test/fixture/minimal.conf")
        self.assertEqual(cfg.editor, "editor")
        self.assertEqual(cfg.merge_editor, "meditor")


class TestConvertBooleanConfigValue(unittest.TestCase):

    config = {'some key': 'some value',
              'trueish': 'yes',
              'falseish': 'no',
              'realtrue': True,
              'realfalse': False}

    def test_if_name_not_available_return_default(self):
        key = 'this key does not exists'
        expected = default = 'my default object'
        config.Config._convert_boolean_config_value(self.config, key, default)
        self.assertEqual(self.config[key], expected)

    def test_yes_is_converted_to_true(self):
        key = 'trueish'
        expected = True
        config.Config._convert_boolean_config_value(self.config, key)
        self.assertEqual(self.config[key], expected)

    def test_no_is_converted_to_false(self):
        key = 'falseish'
        expected = False
        config.Config._convert_boolean_config_value(self.config, key)
        self.assertEqual(self.config[key], expected)

    def test_other_values_raise_value_error(self):
        with self.assertRaises(ValueError):
            config.Config._convert_boolean_config_value(self.config,
                                                        'some key')
        with self.assertRaises(ValueError):
            config.Config._convert_boolean_config_value(self.config,
                                                        'realtrue')
        with self.assertRaises(ValueError):
            config.Config._convert_boolean_config_value(self.config,
                                                        'realfalse')


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


if __name__ == "__main__":
    unittest.main()
