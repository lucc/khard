"""Some helper functions for khard"""

import os
import pathlib
import random
import string
from datetime import datetime
from textwrap import dedent


def pretty_print(table, justify="L"):
    # support for multiline columns
    line_break_table = []
    for row in table:
        # get line break count
        most_line_breaks_in_row = 0
        for col in row:
            if str(col).count("\n") > most_line_breaks_in_row:
                most_line_breaks_in_row = col.count("\n")
        # fill table rows
        for index in range(0, most_line_breaks_in_row+1):
            line_break_row = []
            for col in row:
                try:
                    line_break_row.append(str(col).split("\n")[index])
                except IndexError:
                    line_break_row.append("")
            line_break_table.append(line_break_row)
    # replace table variable
    table = line_break_table
    # get width for every column
    column_widths = [0] * len(table[0])
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
                formated_column = str(col).rjust(column_widths[col_index] +
                                                 offset)
            elif justify == "L":  # justify left
                formated_column = str(col).ljust(column_widths[col_index] +
                                                 offset)
            elif justify == "C":  # justify center
                formated_column = str(col).center(column_widths[col_index] +
                                                  offset)
            single_row_list.append(formated_column)
        table_row_list.append(' '.join(single_row_list))
    return '\n'.join(table_row_list)


def list_to_string(input, delimiter):
    """converts list to string recursively so that nested lists are supported

    :param input: a list of strings and lists of strings (and so on recursive)
    :type input: list
    :param delimiter: the deimiter to use when joining the items
    :type delimiter: str
    :returns: the recursively joined list
    :rtype: str
    """
    if isinstance(input, list):
        return delimiter.join(
            list_to_string(item, delimiter) for item in input)
    return input


def string_to_list(input, delimiter):
    if isinstance(input, list):
        return input
    return [x.strip() for x in input.split(delimiter)]


def string_to_date(string):
    """Convert a date string into a date object.

    :param string: the date string to parse
    :type string: str
    :returns: the parsed datetime object
    :rtype: datetime.datetime
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


def get_random_uid():
    return ''.join([random.choice(string.ascii_lowercase + string.digits)
                    for _ in range(36)])


def file_modification_date(filename):
    return datetime.fromtimestamp(os.path.getmtime(filename))


def convert_to_yaml(name, value, indentation, index_of_colon,
                    show_multi_line_character):
    """converts a value list into yaml syntax

    :param str name: name of object (example: phone)
    :param value: object contents
    :type value: str, list(str), list(list(str)), list(dict)
    :param str indentation: indent all by number of spaces
    :param int index_of_colon: use to position : at the name string (-1 for no
        space)
    :param bool show_multi_line_character: option to hide "|"
    :returns: yaml formatted string array of name, value pair
    :rtype: list(str)
    """
    strings = []
    if isinstance(value, list):
        # special case for single item lists:
        if len(value) == 1 and isinstance(value[0], str):
            # value = ["string"] should not be converted to
            # name:
            #   - string
            # but to "name: string" instead
            value = value[0]
        elif len(value) == 1 and isinstance(value[0], list) \
                and len(value[0]) == 1 and isinstance(value[0][0], str):
            # same applies to value = [["string"]]
            value = value[0][0]
    if isinstance(value, str):
        strings.append("%s%s%s: %s" % (
            ' ' * indentation, name, ' ' * (index_of_colon-len(name)),
            indent_multiline_string(value, indentation+4,
                                    show_multi_line_character)))
    elif isinstance(value, list):
        strings.append("%s%s%s: " % (
            ' ' * indentation, name, ' ' * (index_of_colon-len(name))))
        for outer in value:
            # special case for single item sublists
            if isinstance(outer, list) and len(outer) == 1 \
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
            elif isinstance(outer, dict):
                # ABLABEL'd lists
                for k in outer:
                    strings += convert_to_yaml("- " + k, outer[k], indentation+4,
                        index_of_colon, show_multi_line_character)
    return strings


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


def get_new_contact_template(supported_private_objects=None):
    formatted_private_objects = []
    if supported_private_objects:
        formatted_private_objects.append("")
        longest_key = max(supported_private_objects, key=len)
        for object in supported_private_objects:
            formatted_private_objects += convert_to_yaml(
                object, "", 12, len(longest_key)+1, True)
    template = pathlib.Path(__file__).parent / 'data' / 'template.yaml'
    with template.open() as template:
        return template.read().format('\n'.join(formatted_private_objects))
