# -*- coding: utf-8 -*-

import datetime, os, random, string

def format_yaml_values(input, indentation, start_character):
    if "\n" in input:
        lines = []
        if start_character is not None:
            lines.append(start_character)
        for line in input.split("\n"):
            lines.append("%s%s" % (' ' * indentation, line))
        return '\n'.join(lines)
    else:
        return input


def pretty_print(table, justify = "L"):
    # get width for every column
    column_widths = [0] * table[0].__len__()
    offset = 3
    for row in table:
        for index, col in enumerate(row):
            width = len(str(col).decode("utf-8"))
            if width > column_widths[index]:
                column_widths[index] = width
    table_row_list = []
    for row in table:
        single_row_list = []
        for col_index, col in enumerate(row):
            if justify == "R": # justify right
                formated_column = str(col).decode("utf-8").rjust(column_widths[col_index] + offset)
            elif justify == "L": # justify left
                formated_column = str(col).decode("utf-8").ljust(column_widths[col_index] + offset)
            elif justify == "C": # justify center
                formated_column = str(col).decode("utf-8").center(column_widths[col_index] + offset)
            single_row_list.append(formated_column.encode("utf-8"))
        table_row_list.append(' '.join(single_row_list))
    return '\n'.join(table_row_list)


def get_random_uid():
    return ''.join([ random.choice(string.ascii_lowercase + string.digits) for _ in range(36) ])


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
    return datetime.datetime.fromtimestamp(t)


def get_new_contact_template():
    return """# name components
Prefix     : 
First name : 
Additional : 
Last name  : 
Suffix     : 

# organisation, title and role
Organisation : 
Role         : 
Title        : 

# phone numbers
# format:
#   Phone:
#       type1, type2: number
#       type3:
#           - number1
#           - number2
#       custom: number
# allowed types:
#   At least one of: bbs, car, cell, fax, home, isdn, msg, modem, pager, pcs, pref, video, voice, work
#   Alternatively you may use a single custom label (only letters).
#   But beware, that not all address book clients will support custom labels.
Phone :
    cell : 
    work : 

# email addresses
# allowed types:
#   At least one of: home, internet, pref, uri, work, x400
#   Alternatively you may use a single custom label (only letters).
Email :
    home : 
    work : 

# post addresses
# allowed types:
#   At least one of: home, pref, work
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

# web pages
# either
#   Webpage: http://example.com
# or
#   Webpage:
#       - http://example.com
#       - http://example.org
Webpage : 

# instant messaging and social networks
# Warning: may only work with the contacts app of some Android devices
Jabber  : 
Skype   : 
Twitter : 

# birthday
# day.month.year or year.month.day
Birthday : 

# categories or tags
# format: category1, category2, ...
Categories : 

# nickname
Nickname : 

# note
# for multi-line notes use:
#   Note : |
#       line one
#       line two
Note : """

