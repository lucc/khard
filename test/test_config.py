"""Tests for the config module."""

import io
import unittest
import unittest.mock as mock

from khard import config


# Find executables without looking at the users $PATH.
@mock.patch('khard.config.find_executable', lambda x: x)
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


@mock.patch('khard.config.find_executable', lambda x: x)
class ConfigPreferredVcardVersion(unittest.TestCase):

    def test_default_value_is_3(self):
        c = config.Config("test/fixture/minimal.conf")
        self.assertEqual(c.get_preferred_vcard_version(), "3.0")

    def test_set_preferred_version(self):
        c = config.Config("test/fixture/minimal.conf")
        c.set_preferred_vcard_version("11")
        self.assertEqual(c.get_preferred_vcard_version(), "11")


if __name__ == "__main__":
    unittest.main()
