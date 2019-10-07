"""Tests for the config module."""

import io
import os.path
import tempfile
import unittest
import unittest.mock as mock

from khard import config

import configobj


class LoadingConfigFile(unittest.TestCase):

    def test_load_non_existing_file_fails(self):
        filename = "I hope this file never exists"
        stdout = io.StringIO()
        with self.assertRaises(IOError) as cm:
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
        stdout = io.StringIO()
        with tempfile.NamedTemporaryFile() as name:
            with mock.patch("sys.stdout", stdout):
                with self.assertRaises(SystemExit):
                    config.Config(name)
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


class Validation(unittest.TestCase):

    @staticmethod
    def _template(section, key, value):
        c = configobj.ConfigObj(configspec=config.Config.SPEC_FILE)
        c['general'] = {}
        c['vcard'] = {}
        c['contact table'] = {}
        c['addressbooks'] = {'test': {'path': '/tmp'}}
        c[section][key] = value
        return c

    @unittest.expectedFailure
    def test_rejects_invalid_default_actions(self):
        action = 'this is not a valid action'
        conf = self._template('general', 'default_action', action)
        with self.assertLogs(level=logging.ERROR):
            with self.assertRaises(SystemExit):
                config.Config._validate(conf)


if __name__ == "__main__":
    unittest.main()
