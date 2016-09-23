"""Tests for the config module."""

import io
import os
import unittest
import unittest.mock as mock

from khard import config


class LoadingConfigFile(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Clear the environment.
        for varname in ["EDITOR", "MERGE_EDITOR", "XDG_CONFIG_HOME"]:
            if varname in os.environ:
                del os.environ[varname]

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


if __name__ == "__main__":
    unittest.main()
