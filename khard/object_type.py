"""Helper module for validating typed vcard properties"""

from enum import Enum


class ObjectType(Enum):
    string = 1
    list_with_strings = 2
    string_or_list_with_strings = 3
