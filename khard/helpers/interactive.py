"""Helper functions for user interaction."""

import contextlib
from datetime import datetime
from enum import Enum
import os.path
import subprocess
from tempfile import NamedTemporaryFile
from typing import Callable, Generator, List, Optional, TypeVar, Union

from ..carddav_object import CarddavObject


T = TypeVar("T")


def confirm(message: str, accept_enter_key: bool = True) -> bool:
    """Ask the user for confirmation on the terminal.

    :param message: the question to print
    :param accept_enter_key: Accept ENTER as alternative for "n"
    :returns: the answer of the user
    """
    while True:
        answer = input(message + ' (y/N) ')
        answer = answer.lower()
        if answer == 'y':
            return True
        if answer == 'n':
            return False
        if answer == '' and accept_enter_key:
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
        with NamedTemporaryFile(mode='w+t', suffix='.yml') as tmp:
            tmp.write(text)
            tmp.flush()
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

    def edit_templates(self, yaml2card: Callable[[str], CarddavObject],
                       template1: str, template2: Optional[str] = None
                       ) -> Optional[CarddavObject]:
        """Edit YAML templates of contacts and parse them back

        :param yaml2card: a function to convert the modified YAML templates
            into a CarddavObject
        :param template1: the first template
        :param template2: the second template (optional, for merges)
        :returns: the parsed CarddavObject or None
        """
        templates = [t for t in (template1, template2) if t is not None]
        with contextlib.ExitStack() as stack:
            files = [stack.enter_context(self.write_temp_file(t))
                     for t in templates]
            # Try to edit the files until we detect a modification or the user
            # aborts
            while True:
                if self.edit_files(*files) == EditState.unmodified:
                    return None
                # read temp file contents after editing
                with open(files[-1], "r") as tmp:
                    modified_template = tmp.read()
                # No actual modification was done
                if modified_template == templates[-1]:
                    return None
                # try to create contact from user input
                try:
                    return yaml2card(modified_template)
                except ValueError as err:
                    print("\n{}\n".format(err))
                    if not confirm("Do you want to open the editor again?"):
                        print("Canceled")
                        return None
        return None  # only for mypy
