# -*- coding: utf-8 -*-

from datetime import datetime
import os
import random
import string

from .object_type import ObjectType


def pretty_print(table, justify="L"):
    # get width for every column
    column_widths = [0] * table[0].__len__()
    offset = 3
    for row in table:
        for index, col in enumerate(row):
            width = len(str(col))
            if width > column_widths[index]:
                column_widths[index] = width
    table_row_list = []
    for row in table:
        single_row_list = []
        for col_index, col in enumerate(row):
            if justify == "R":  # justify right
                formated_column = str(col).rjust(
                    column_widths[col_index] + offset)
            elif justify == "L":  # justify left
                formated_column = str(col).ljust(
                    column_widths[col_index] + offset)
            elif justify == "C":  # justify center
                formated_column = str(col).center(
                    column_widths[col_index] + offset)
            single_row_list.append(formated_column)
        table_row_list.append(' '.join(single_row_list))
    return '\n'.join(table_row_list)


def list_to_string(input, delimiter):
    """
    converts list to string recursively so that nested lists are supported
    """
    if isinstance(input, list):
        flat_list = []
        for item in input:
            flat_list.append(list_to_string(item, delimiter))
        return delimiter.join(flat_list)
    return input


def string_to_list(input, delimiter):
    if isinstance(input, list):
        return input
    return [x.strip() for x in input.split(delimiter)]


def string_to_date(input):
    """convert string to date object"""
    # try date format --mmdd
    try:
        return datetime.strptime(input, "--%m%d")
    except ValueError:
        pass
    # try date format --mm-dd
    try:
        return datetime.strptime(input, "--%m-%d")
    except ValueError:
        pass
    # try date format yyyymmdd
    try:
        return datetime.strptime(input, "%Y%m%d")
    except ValueError:
        pass
    # try date format yyyy-mm-dd
    try:
        return datetime.strptime(input, "%Y-%m-%d")
    except ValueError:
        pass
    # try datetime format yyyymmddThhmmss
    try:
        return datetime.strptime(input, "%Y%m%dT%H%M%S")
    except ValueError:
        pass
    # try datetime format yyyy-mm-ddThh:mm:ss
    try:
        return datetime.strptime(input, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        pass
    # try datetime format yyyymmddThhmmssZ
    try:
        return datetime.strptime(input, "%Y%m%dT%H%M%SZ")
    except ValueError:
        pass
    # try datetime format yyyy-mm-ddThh:mm:ssZ
    try:
        return datetime.strptime(input, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass
    # try datetime format yyyymmddThhmmsstz where tz may look like -06:00
    try:
        return datetime.strptime(
            ''.join(input.rsplit(":", 1)), "%Y%m%dT%H%M%S%z")
    except ValueError:
        pass
    # try datetime format yyyy-mm-ddThh:mm:sstz where tz may look like -06:00
    try:
        return datetime.strptime(
            ''.join(input.rsplit(":", 1)), "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        pass
    raise ValueError


def get_random_uid():
    return ''.join([random.choice(string.ascii_lowercase + string.digits)
                    for _ in range(36)])


def compare_uids(uid1, uid2):
    sum = 0
    for c1, c2 in zip(uid1, uid2):
        if c1 == c2:
            sum += 1
        else:
            break
    return sum


def file_modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.fromtimestamp(t)


def convert_to_yaml(
        name, value, indentation, indexOfColon, show_multi_line_character):
    """converts a value list into yaml syntax
    :param name: name of object (example: phone)
    :type name: str
    :param value: object contents
    :type value: str, list(str), list(list(str))
    :param indentation: indent all by number of spaces
    :type indentation: int
    :param indexOfColon: use to position : at the name string (-1 for no space)
    :type indexOfColon: int
    :param show_multi_line_character: option to hide "|"
    :type show_multi_line_character: boolean
    :returns: yaml formatted string array of name, value pair
    :rtype: list(str)
    """
    strings = []
    if isinstance(value, list):
        # special case for single item lists:
        if len(value) == 1 \
                and isinstance(value[0], str):
            # value = ["string"] should not be converted to
            # name:
            #   - string
            # but to "name: string" instead
            value = value[0]
        elif len(value) == 1 \
                and isinstance(value[0], list) \
                and len(value[0]) == 1 \
                and isinstance(value[0][0], str):
            # same applies to value = [["string"]]
            value = value[0][0]
    if isinstance(value, str):
        strings.append("%s%s%s: %s" % (
            ' ' * indentation, name, ' ' * (indexOfColon-len(name)),
            indent_multiline_string(value, indentation+4,
                                    show_multi_line_character)))
    elif isinstance(value, list):
        strings.append("%s%s%s: " % (
            ' ' * indentation, name, ' ' * (indexOfColon-len(name))))
        for outer in value:
            # special case for single item sublists
            if isinstance(outer, list) \
                    and len(outer) == 1 \
                    and isinstance(outer[0], str):
                # outer = ["string"] should not be converted to
                # -
                #   - string
                # but to "- string" instead
                outer = outer[0]
            if isinstance(outer, str):
                strings.append("%s- %s" % (
                    ' ' * (indentation+4), indent_multiline_string(
                        outer, indentation+8, show_multi_line_character)))
            elif isinstance(outer, list):
                strings.append("%s- " % (' ' * (indentation+4)))
                for inner in outer:
                    if isinstance(inner, str):
                        strings.append("%s- %s" % (
                            ' ' * (indentation+8), indent_multiline_string(
                                inner, indentation+12,
                                show_multi_line_character)))
    return strings


def convert_to_vcard(name, value, allowed_object_type):
    """converts user input into vcard compatible data structures
    :param name: object name, only required for error messages
    :type name: str
    :param value: user input
    :type value: str or list(str)
    :param allowed_object_type: set the accepted return type for vcard
        attribute
    :type allowed_object_type: enum of type ObjectType
    :returns: cleaned user input, ready for vcard or a ValueError
    :rtype: str or list(str)
    """
    if isinstance(value, str):
        if allowed_object_type == ObjectType.list_with_strings:
            raise ValueError(
                "Error: " + name + " must not contain a single string.")
        else:
            return value.strip()
    elif isinstance(value, list):
        if allowed_object_type == ObjectType.string:
            raise ValueError(
                "Error: " + name + " must not contain a list.")
        else:
            for entry in value:
                if not isinstance(entry, str):
                    raise ValueError(
                        "Error: " + name + " must not contain a nested list")
            # filter out empty list items and strip leading and trailing space
            return [x.strip() for x in value if x]
    else:
        if allowed_object_type == ObjectType.string:
            raise ValueError(
                "Error: " + name + " must be a string.")
        elif allowed_object_type == ObjectType.list_with_strings:
            raise ValueError(
                "Error: " + name + " must be a list with strings.")
        else:
            raise ValueError(
                "Error: " + name + " must be a string or a list with strings.")


def indent_multiline_string(input, indentation, show_multi_line_character):
    # if input is a list, convert to string first
    if isinstance(input, list):
        input = list_to_string(input, "")
    # format multiline string
    if "\n" in input:
        lines = ["|"] if show_multi_line_character else [""]
        for line in input.split("\n"):
            lines.append("%s%s" % (' ' * indentation, line.strip()))
        return '\n'.join(lines)
    return input.strip()


def get_new_contact_template():
    return """# name components
# every entry may contain a string or a list of strings
# format:
#   First name : name1
#   Additional : 
#       - name2
#       - name3
#   Last name  : name4
Prefix     : 
First name : 
Additional : 
Last name  : 
Suffix     : 

# person related information
#
# birthday
# Formats:
#   vcard 3.0 and 4.0: yyy-mm-dd or yyyy-mm-ddTHH:MM:SS
#   vcard 4.0 only: --mm-dd or text= string value
Birthday : 
# nickname
# may contain a string or a list of strings
Nickname : 

# organisation
# format:
#   Organisation : company
# or
#   Organisation :
#       - company1
#       - company2
# or
#   Organisation :
#       -
#           - company
#           - unit
Organisation : 

# organisation title and role
# every entry may contain a string or a list of strings
#
# title at organisation
# example usage: research scientist
Title : 
# role at organisation
# example usage: project leader
Role  : 

# phone numbers
# format:
#   Phone:
#       type1, type2: number
#       type3:
#           - number1
#           - number2
#       custom: number
# allowed types:
#   vcard 3.0: At least one of bbs, car, cell, fax, home, isdn, msg, modem,
#                              pager, pcs, pref, video, voice, work
#   vcard 4.0: At least one of home, work, pref, text, voice, fax, cell, video,
#                              pager, textphone
#   Alternatively you may use a single custom label (only letters).
#   But beware, that not all address book clients will support custom labels.
Phone :
    cell : 
    home : 

# email addresses
# format like phone numbers above
# allowed types:
#   vcard 3.0: At least one of home, internet, pref, work, x400
#   vcard 4.0: At least one of home, internet, pref, work
#   Alternatively you may use a single custom label (only letters).
Email :
    home : 
    work : 

# post addresses
# allowed types:
#   vcard 3.0: At least one of dom, intl, home, parcel, postal, pref, work
#   vcard 4.0: At least one of home, pref, work
#   Alternatively you may use a single custom label (only letters).
Address :
    home :
        Box      : 
        Extended : 
        Street   : 
        Code     : 
        City     : 
        Region   : 
        Country  : 

# categories or tags
# format:
#   Categories : single category
# or
#   Categories :
#       - category1
#       - category2
Categories : 

# web pages
# may contain a string or a list of strings
Webpage : 

# private objects
# define your own private objects in the vcard section of your khard.conf file
# these objects are stored with a leading "X-" before the object name in the
# vcard files.
# every entry may contain a string or a list of strings
Private :

# notes
# may contain a string or a list of strings
# for multi-line notes use:
#   Note : |
#       line one
#       line two
Note : """
