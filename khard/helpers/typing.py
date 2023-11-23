"""Helper code for type annotations and runtime type conversion."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Union


class ObjectType(Enum):
    str = 1
    list = 2
    both = 3


# some type aliases
Date = Union[str, datetime]
StrList = Union[str, List[str]]
PostAddress = Dict[str, str]


def convert_to_vcard(name: str, value: StrList, constraint: ObjectType
                     ) -> StrList:
    """converts user input into vCard compatible data structures

    :param name: object name, only required for error messages
    :param value: user input
    :param constraint: set the accepted return type for vCard attribute
    :returns: cleaned user input, ready for vCard or a ValueError
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


def list_to_string(input: Union[str, List], delimiter: str) -> str:
    """converts list to string recursively so that nested lists are supported

    :param input: a list of strings and lists of strings (and so on recursive)
    :param delimiter: the delimiter to use when joining the items
    :returns: the recursively joined list
    """
    if isinstance(input, list):
        return delimiter.join(
            list_to_string(item, delimiter) for item in input)
    return input


def string_to_list(input: Union[str, List[str]], delimiter: str) -> List[str]:
    if isinstance(input, list):
        return input
    return [x.strip() for x in input.split(delimiter)]


def string_to_date(string: str) -> datetime:
    """Convert a date string into a date object.

    :param string: the date string to parse
    :returns: the parsed datetime object
    """
    # try date formats --mmdd, --mm-dd, yyyymmdd, yyyy-mm-dd and datetime
    # formats yyyymmddThhmmss, yyyy-mm-ddThh:mm:ss, yyyymmddThhmmssZ,
    # yyyy-mm-ddThh:mm:ssZ.
    for fmt in ("--%m%d", "--%m-%d", "%Y%m%d", "%Y-%m-%d", "%Y%m%dT%H%M%S",
                "%Y-%m-%dT%H:%M:%S", "%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(string, fmt)
        except ValueError:
            continue  # with the next format
    # try datetime formats yyyymmddThhmmsstz and yyyy-mm-ddThh:mm:sstz where tz
    # may look like -06:00.
    for fmt in ("%Y%m%dT%H%M%S%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(''.join(string.rsplit(":", 1)), fmt)
        except ValueError:
            continue  # with the next format
    raise ValueError
