"""Tests for editing files and contacts in an external editor"""

from contextlib import contextmanager
import datetime
import unittest
from unittest import mock

from khard.helpers.interactive import Editor, EditState

from .helpers import mock_stream


class EditFiles(unittest.TestCase):

    t1 = datetime.datetime(2021, 1, 1, 12, 21, 42)
    t2 = datetime.datetime(2021, 1, 1, 12, 21, 43)
    editor = Editor("edit", "merge")

    @staticmethod
    @contextmanager
    def _mock_popen(returncode=0):
        """Mock the subprocess.Popen class, set the returncode attribute of the
        child process object."""
        child_process = mock.Mock()
        child_process.returncode = returncode
        Popen = mock.Mock(return_value=child_process)
        with mock.patch("subprocess.Popen", Popen) as popen:
            yield popen

    @staticmethod
    def _edit_files(write="changed"):
        """Mock function for khar.helpers.interactive.Editor.edit_files

        Create a function that will write the specified text to all files
        passed as arguments.
        """
        def edit_files(self, *files):
            for f in files:
                with open(f, "w") as fp:
                    fp.write(write)
        return edit_files

    def test_calls_subprocess_popen_with_editor_for_one_args(self):
        with self._mock_popen() as popen:
            with mock.patch("khard.helpers.interactive.Editor._mtime",
                            mock.Mock(return_value=self.t1)):
                self.editor.edit_files("file")
        popen.assert_called_with(["edit", "file"])

    def test_calls_subprocess_popen_with_merge_editor_for_two_args(self):
        with self._mock_popen() as popen:
            with mock.patch("khard.helpers.interactive.Editor._mtime",
                            mock.Mock(return_value=self.t1)):
                self.editor.edit_files("file1", "file2")
        popen.assert_called_with(["merge", "file1", "file2"])

    def test_failing_external_command_returns_aborted_state(self):
        with self._mock_popen(1):
            with mock.patch("khard.helpers.interactive.Editor._mtime",
                            mock.Mock(return_value=self.t1)):
                actual = self.editor.edit_files("file")
        self.assertEqual(actual, EditState.aborted)

    def test_returns_state_modiefied_if_timestamp_does_change(self):
        with self._mock_popen():
            with mock.patch("khard.helpers.interactive.Editor._mtime",
                            mock.Mock(side_effect=[self.t1, self.t2])):
                actual = self.editor.edit_files("file")
        self.assertEqual(actual, EditState.modified)

    def test_returns_state_unmodiefied_if_timestamp_does_not_change(self):
        with self._mock_popen():
            with mock.patch("khard.helpers.interactive.Editor._mtime",
                            mock.Mock(side_effect=[self.t1, self.t1])):
                actual = self.editor.edit_files("file")
        self.assertEqual(actual, EditState.unmodified)

    def test_editing_templates(self):
        t1 = "some: yaml\ndocument: true\n"
        with mock.patch("khard.helpers.interactive.Editor.edit_files",
                        self._edit_files()):
            actual = self.editor.edit_templates(lambda x: x, t1)
        self.assertEqual(actual, "changed")

    def test_exception_from_yaml_conversion_is_caught(self):
        t1 = "key: value\n"
        with mock.patch("khard.helpers.interactive.Editor.edit_files",
                        self._edit_files()):
            with mock.patch("khard.helpers.interactive.confirm",
                            mock.Mock(return_value=False)) as confirm:
                with mock_stream():  # hide stdout in test
                    actual = self.editor.edit_templates(
                        mock.Mock(side_effect=ValueError), t1)
        self.assertIsNone(actual)
        confirm.assert_called_once()
