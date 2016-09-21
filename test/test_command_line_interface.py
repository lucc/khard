"""Test some features of the command line interface of khard."""

import io
import os
import subprocess
import sys
import unittest

from khard import khard


class HelpOption(unittest.TestCase):

    def setUp(self):
        self.stdout = sys.stdout
        self.output = io.StringIO()
        sys.stdout = self.output
        self.env = dict(os.environ)
        self.env['PYTHONPATH'] = '.'

    def tearDown(self):
        self.output.close()
        sys.stdout = self.stdout

    def test_khard_runner_script(self):
        output = subprocess.check_output(['./khard-runner.py', '-h'],
                                         env=self.env)
        line = output.splitlines()[0]
        self.assertTrue(line.startswith(b'usage: khard-runner.py [-h]'))

    def test_global_help(self):
        self.assertRaises(SystemExit, khard.main, ['-h'])
        text = self.output.getvalue().splitlines()
        self.assertRegex(text[0], r'^usage: setup.py \[-h\]')

    def test_subcommand_help(self):
        self.assertRaises(SystemExit, khard.main, ['list', '-h'])
        text = self.output.getvalue().splitlines()
        self.assertTrue(text[0].startswith('usage: setup.py list [-h]'))

    def test_global_help_with_subcommand(self):
        self.assertRaises(SystemExit, khard.main, ['-h', 'list'])
        text = self.output.getvalue().splitlines()
        self.assertRegex(text[0], r'^usage: setup.py \[-h\]')


if __name__ == "__main__":
    unittest.main()
