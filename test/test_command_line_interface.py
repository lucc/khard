"""Test some features of the command line interface of khard."""

import os
import subprocess
import unittest


class HelpOption(unittest.TestCase):

    def setUp(self):
        self.env = dict(os.environ)
        self.env['PYTHONPATH'] = '.'

    def test_global_help(self):
        output = subprocess.check_output(['./khard-runner.py', '-h'],
                                         env=self.env)
        line = output.splitlines()[0]
        self.assertTrue(line.startswith(b'usage: khard-runner.py [-h]'))

    def test_subcommand_help(self):
        output = subprocess.check_output(['./khard-runner.py', 'list', '-h'],
                                         env=self.env)
        line = output.splitlines()[0]
        self.assertTrue(line.startswith(b'usage: khard-runner.py list [-h]'))

    def test_global_help_with_subcommand(self):
        output = subprocess.check_output(['./khard-runner.py', '-h', 'list'],
                                         env=self.env)
        line = output.splitlines()[0]
        self.assertTrue(line.startswith(b'usage: khard-runner.py [-h]'))


if __name__ == "__main__":
    unittest.main()
