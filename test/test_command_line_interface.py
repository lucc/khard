"""Test some features of the command line interface of khard."""

import io
import os
import subprocess
import sys
import unittest
import unittest.mock as mock

from khard import khard


class HelpOption(unittest.TestCase):

    def test_global_help(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                khard.main(['-h'])
        text = stdout.getvalue().splitlines()
        self.assertRegex(text[0], r'^usage: {} \[-h\]'.format(sys.argv[0]))

    def test_subcommand_help(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                khard.main(['list', '-h'])
        text = stdout.getvalue().splitlines()
        self.assertRegex(text[0], r'^usage: {} list \[-h\]'.format(
            sys.argv[0]))

    def test_global_help_with_subcommand(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(SystemExit):
                khard.main(['-h', 'list'])
        text = stdout.getvalue().splitlines()
        self.assertRegex(text[0], r'^usage: {} \[-h\]'.format(sys.argv[0]))


if __name__ == "__main__":
    unittest.main()
