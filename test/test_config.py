"""Tests for the config module."""
# pylint: disable=missing-docstring

import logging
import os.path
import tempfile
import unittest
import unittest.mock as mock

import configobj

from khard import config


class LoadingConfigFile(unittest.TestCase):

    def test_load_non_existing_file_fails(self):
        filename = "I hope this file never exists"
        with self.assertRaises(OSError) as cm:
            config.Config._load_config_file(filename)
        self.assertTrue(str(cm.exception).startswith('Config file not found:'))

    def test_uses_khard_config_environment_variable(self):
        filename = "this is some very random string"
        with mock.patch.dict("os.environ", clear=True, KHARD_CONFIG=filename):
            with mock.patch("configobj.ConfigObj", dict):
                ret = config.Config._load_config_file("")
        self.assertEqual(ret['infile'], filename)

    def test_uses_xdg_config_home_environment_variable(self):
        prefix = "this is some very random string"
        with mock.patch.dict("os.environ", clear=True, XDG_CONFIG_HOME=prefix):
            with mock.patch("configobj.ConfigObj", dict):
                ret = config.Config._load_config_file("")
        expected = os.path.join(prefix, 'khard', 'khard.conf')
        self.assertEqual(ret['infile'], expected)

    def test_uses_config_dir_if_environment_unset(self):
        prefix = "this is some very random string"
        with mock.patch.dict("os.environ", clear=True, HOME=prefix):
            with mock.patch("configobj.ConfigObj", dict):
                ret = config.Config._load_config_file("")
        expected = os.path.join(prefix, '.config', 'khard', 'khard.conf')
        self.assertEqual(ret['infile'], expected)

    def test_load_empty_file_fails(self):
        with tempfile.NamedTemporaryFile() as name:
            with self.assertLogs(level=logging.ERROR):
                with self.assertRaises(config.ConfigError):
                    config.Config(name)

    @mock.patch.dict('os.environ', EDITOR='editor', MERGE_EDITOR='meditor')
    def test_load_minimal_file_by_name(self):
        cfg = config.Config("test/fixture/minimal.conf")
        self.assertEqual(cfg.editor, ["editor"])
        self.assertEqual(cfg.merge_editor, "meditor")


class ConfigPreferredVcardVersion(unittest.TestCase):

    def test_default_value_is_3(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.preferred_vcard_version, "3.0")

    def test_set_preferred_version(self):
        c = config.Config("test/fixture/minimal.conf")
        c.preferred_vcard_version = "11"
        self.assertEqual(c.preferred_vcard_version, "11")


class Defaults(unittest.TestCase):

    def test_debug_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.debug)

    def test_default_action_defaults_to_none(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertIsNone(c.default_action)

    def test_reverse_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.reverse)

    def test_group_by_addressbook_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.group_by_addressbook)

    def test_show_nicknames_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.show_nicknames)

    def test_show_uids_defaults_to_true(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertTrue(c.show_uids)

    def test_show_kinds_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.show_kinds)

    def test_sort_defaults_to_first_name(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.sort, 'first_name')

    def test_display_defaults_to_first_name(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.display, 'first_name')

    def test_localize_dates_defaults_to_true(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertTrue(c.localize_dates)

    def test_preferred_phone_number_type_defaults_to_pref(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertListEqual(c.preferred_phone_number_type, ['pref'])

    def test_preferred_email_address_type_defaults_to_pref(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertListEqual(c.preferred_email_address_type, ['pref'])

    def test_private_objects_defaults_to_empty(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertListEqual(c.private_objects, [])

    def test_search_in_source_files_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.search_in_source_files)

    def test_skip_unparsable_defaults_to_false(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertFalse(c.skip_unparsable)

    def test_preferred_version_defaults_to_3(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.preferred_vcard_version, '3.0')

    @mock.patch.dict('os.environ', clear=True)
    def test_editor_defaults_to_vim(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.editor, ['vim'])

    @mock.patch.dict('os.environ', clear=True)
    def test_merge_editor_defaults_to_vimdiff(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.merge_editor, 'vimdiff')


class Validation(unittest.TestCase):

    @staticmethod
    def _template(section, key, value):
        configspec = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  'khard', 'data', 'config.spec')
        c = configobj.ConfigObj(configspec=configspec)
        c['general'] = {}
        c['vcard'] = {}
        c['contact table'] = {}
        c['addressbooks'] = {'test': {'path': '/tmp'}}
        c[section][key] = value
        return c

    def test_rejects_invalid_default_actions(self):
        action = 'this is not a valid action'
        conf = self._template('general', 'default_action', action)
        with self.assertLogs(level=logging.ERROR):
            with self.assertRaises(config.ConfigError):
                config.Config._validate(conf)

    def test_rejects_unparsable_editor_commands(self):
        editor = 'editor --option "unparsable because quotes are missing'
        conf = self._template('general', 'editor', editor)
        with self.assertLogs(level=logging.ERROR):
            with self.assertRaises(config.ConfigError):
                config.Config._validate(conf)

    def test_rejects_private_objects_with_strange_chars(self):
        obj = 'X-VCÄRD-EXTENSIÖN'
        conf = self._template('vcard', 'private_objects', obj)
        with self.assertLogs(level=logging.ERROR):
            with self.assertRaises(config.ConfigError):
                config.Config._validate(conf)

    def test_rejects_private_objects_starting_with_minus(self):
        obj = '-INVALID-'
        conf = self._template('vcard', 'private_objects', obj)
        with self.assertLogs(level=logging.ERROR):
            with self.assertRaises(config.ConfigError):
                config.Config._validate(conf)


if __name__ == "__main__":
    unittest.main()
