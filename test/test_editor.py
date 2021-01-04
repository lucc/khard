"""Tests for editing files and contacts in an external editor"""

import unittest
from unittest import mock

from khard.helpers.interactive import edit
from khard.khard import edit as edit2
from khard import khard


class EditFiles(unittest.TestCase):

    def test_calls_subprocess_popen(self):
        args = ["editor", "file1", "file2"]
        with mock.patch("subprocess.Popen") as popen:
            edit(*args)
        popen.assert_called_with(args)


class Edit2(unittest.TestCase):

    def setUp(self):
        # Set the uninitialized global variable in the khard module to make it
        # mockable. See https://stackoverflow.com/questions/61193676
        khard.config = mock.Mock()

    def test_calls_edit_from_interactive_helpers(self):
        with mock.patch("khard.khard.config.editor", "myeditor"):
            with mock.patch("khard.helpers.interactive.edit") as edit:
                edit2("file1", "file2")
        edit.assert_called_with("myeditor", "file1", "file2")

    def test_calls_edit_with_merge_editor(self):
        with mock.patch("khard.khard.config.merge_editor", "my merge editor"):
            with mock.patch("khard.helpers.interactive.edit") as edit:
                edit2("file1", "file2", merge=True)
        edit.assert_called_with("my merge editor", "file1", "file2")
