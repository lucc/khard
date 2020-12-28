"""Helper functions for user interaction."""

import contextlib
from datetime import datetime
from enum import Enum
import os.path
import subprocess
from tempfile import NamedTemporaryFile
from typing import Generator, List, Optional, TypeVar, Union


T = TypeVar("T")


def confirm(message: str) -> bool:
    """Ask the user for confirmation on the terminal.

    :param message: the question to print
    :returns: the answer of the user
    """
    while True:
        answer = input(message + ' (y/N) ')
        answer = answer.lower()
        if answer == 'y':
            return True
        if answer in ['', 'n', 'q']:
            return False
        print('Please answer with "y" for yes or "n" for no.')


def select(items: List[T], include_none: bool = False) -> Optional[T]:
    """Ask the user to select an item from a list.

    The list should be displayed to the user before calling this function and
    should be indexed starting with 1.

    :param items: the list from which to select
    :param include_none: whether to allow the selection of no item
    :returns: None or the selected item
    """
    while True:
        try:
            answer = input("Enter Index ({}q to quit): ".format(
                "0 for None, " if include_none else ""))
            answer = answer.lower()
            if answer in ["", "q"]:
                print("Canceled")
                return None
            index = int(answer)
            if include_none and index == 0:
                return None
            if index > 0:
                return items[index - 1]
        except (EOFError, IndexError, ValueError):
            pass
        print("Please enter an index value between 1 and {} or q to quit."
              .format(len(items)))


class EditState(Enum):
    modified = 1
    unmodified = 2
    aborted = 3


class Editor:

    """Wrapper around subprocess.Popen to edit and merge files."""

    def __init__(self, editor: Union[str, List[str]],
                 merge_editor: Union[str, List[str]]) -> None:
        self.editor = [editor] if isinstance(editor, str) else editor
        self.merge_editor = [merge_editor] if isinstance(merge_editor, str) \
            else merge_editor

    @staticmethod
    @contextlib.contextmanager
    def write_temp_file(text: str = "") -> Generator[str, None, None]:
        """Create a new temporary file and write some initial text to it.

        :param text: the text to write to the temp file
        :returns: the file name of the newly created temp file
        """
        with NamedTemporaryFile(mode='w+t', suffix='.yml', delete=False) as tmp:
            tmp.write(text)
            yield tmp.name

    @staticmethod
    def _mtime(filename: str) -> datetime:
        return datetime.fromtimestamp(os.path.getmtime(filename))

    def edit_files(self, file1: str, file2: Optional[str] = None) -> EditState:
        """Edit the given files

        If only one file is given the timestamp of this file is checked, if two
        files are given the timestamp of the second file is checked for
        modification.

        :param file1: the first file (checked for modification if file2 not
            present)
        :param file2: the second file (checked for modification of present)
        :returns: the result of the modification
        """
        if file2 is None:
            command = self.editor + [file1]
        else:
            command = self.merge_editor + [file1, file2]
        timestamp = self._mtime(command[-1])
        child = subprocess.Popen(command)
        child.communicate()
        if child.returncode != 0:
            return EditState.aborted
        if timestamp == self._mtime(command[-1]):
            return EditState.unmodified
        return EditState.modified
