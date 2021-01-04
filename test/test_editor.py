"""Tests for editing files and contacts in an external editor"""

import datetime
import unittest
from unittest import mock

from khard.helpers.interactive import Editor


class EditFiles(unittest.TestCase):

    def test_calls_subprocess_popen_with_editor_for_one_args(self):
        editor = Editor("edit", "merge")
        now = datetime.datetime.now()
        with mock.patch("subprocess.Popen") as popen:
            with mock.patch("khard.helpers.interactive.file_modification_date",
                            mock.Mock(return_value=now)):
                editor.edit_files("file")
        popen.assert_called_with(["edit", "file"])

    def test_calls_subprocess_popen_with_merge_editor_for_two_args(self):
        editor = Editor("edit", "merge")
        now = datetime.datetime.now()
        with mock.patch("subprocess.Popen") as popen:
            with mock.patch("khard.helpers.interactive.file_modification_date",
                            mock.Mock(return_value=now)):
                editor.edit_files("file1", "file2")
        popen.assert_called_with(["merge", "file1", "file2"])
