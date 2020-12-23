"""Helper functions for user interaction."""

import subprocess
from typing import List, Optional, TypeVar, Union


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


def edit(editor: Union[str, List[str]], *filenames: str) -> None:
    """Edit the given files"""
    editor = [editor] if isinstance(editor, str) else editor
    editor.extend(filenames)
    child = subprocess.Popen(editor)
    child.communicate()
