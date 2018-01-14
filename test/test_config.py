"""Tests for the config module."""

import io
import os
import unittest
import unittest.mock as mock

from khard import config


class LoadingConfigFile(unittest.TestCase):

    _patch1 = None
    _patch2 = None

    @classmethod
    def setUpClass(cls):
        # Mock the environment.
        cls._patch1 = mock.patch('os.environ', {})
        # Use a mock to "find" executables in the mocked environment.
        cls._patch2 = mock.patch('khard.config.find_executable', lambda x: x)
        cls._patch1.start()
        cls._patch2.start()

    @classmethod
    def tearDownClass(cls):
        cls._patch1.stop()
        cls._patch2.stop()

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
        self.assertEqual(
            stdout.getvalue(),
            'Error in config file\nMissing main section "[general]".\n')

    def test_load_minimal_file_by_name(self):
        cfg = config.Config("test/templates/minimal.conf")
        self.assertEqual(cfg.editor, "/bin/sh")
        self.assertEqual(cfg.merge_editor, "/bin/sh")
        self.assertEqual(cfg.default_action, "list")


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


if __name__ == "__main__":
    unittest.main()
