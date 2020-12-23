"""Helper code for type annotations and runtime type conversion."""

from datetime import datetime
from enum import Enum
from typing import List, Union


class ObjectType(Enum):
    str = 1
    list = 2
    both = 3


# some type aliases
Date = Union[str, datetime]
StrList = Union[str, List[str]]


def convert_to_vcard(name: str, value: StrList, constraint: ObjectType
                     ) -> StrList:
    """converts user input into vcard compatible data structures

    :param name: object name, only required for error messages
    :param value: user input
    :param constraint: set the accepted return type for vcard attribute
    :returns: cleaned user input, ready for vcard or a ValueError
    """
    if isinstance(value, str):
        if constraint == ObjectType.list:
            return [value.strip()]
        return value.strip()
    if isinstance(value, list):
        if constraint == ObjectType.str:
            raise ValueError("Error: " + name + " must contain a string.")
        if not all(isinstance(entry, str) for entry in value):
            raise ValueError("Error: " + name +
                             " must not contain a nested list")
        # filter out empty list items and strip leading and trailing space
        return [x.strip() for x in value if x.strip()]
    if constraint == ObjectType.str:
        raise ValueError("Error: " + name + " must be a string.")
    if constraint == ObjectType.list:
        raise ValueError("Error: " + name + " must be a list with strings.")
    raise ValueError("Error: " + name +
                     " must be a string or a list with strings.")
