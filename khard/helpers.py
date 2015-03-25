# -*- coding: utf-8 -*-

from config import Config

# Pretty Print table in tabular format
def pretty_print(table, justify = "L"):
    # get width for every column
    column_widths = [0] * table[0].__len__()
    offset = 3
    for row in table:
        for index, col in enumerate(row):
            width = len(str(col).decode("utf-8"))
            if width > column_widths[index]:
                column_widths[index] = width
    outputStr = ""
    for row_index, row in enumerate(table):
        rowList = []
        for col_index, col in enumerate(row):
            if justify == "R": # justify right
                formated_column = str(col).decode("utf-8").rjust(column_widths[col_index] + offset)
            elif justify == "L": # justify left
                formated_column = str(col).decode("utf-8").ljust(column_widths[col_index] + offset)
            elif justify == "C": # justify center
                formated_column = str(col).decode("utf-8").center(column_widths[col_index] + offset)
            rowList.append(formated_column.encode("utf-8"))
        if row_index == table.__len__()-1:
            outputStr += ' '.join(rowList)
        else:
            outputStr += ' '.join(rowList) + "\n"
    return outputStr

def get_new_contact_template(addressbook_name):
    return """# new contact
# Address book: %s
# if you want to cancel, exit without saving

# first and last name
# at least enter first name, first and last name or an organisation
First name   = 
Last name    = 
Organisation = 

# phone numbers
# format: PhoneX = type: number
# allowed types:
#   Standard: cell, home, work
#   Alternatively you can use every custom label (only letters). But maybe not all address book
#   clients support that.
Phone1 = cell: 
Phone2 = Dresden: 

# email addresses
# format: EmailX = type: address
# allowed types:
#   Standard: home, work
#   or a custom label (only letters)
Email1 = home: 

# post addresses
# format: AddressX = type: street and house number; postcode; city; region; country
# the region is optional so the following is allowed too:
# format: AddressX = type: street and house number; postcode; city;; country
# allowed types:
#   Standard: home, work
#   or a custom label (only letters)
Address1 = home: ; ; ; ; %s

# instant messaging and social networks
Jabber  = 
Skype   = 
Twitter = 
Webpage = 

# Miscellaneous stuff
# Birthday: day.month.year
Birthday = 
Nickname = """ % (addressbook_name, Config().get_default_country())

def get_existing_contact_template(vcard):
    strings = []
    for line in get_new_contact_template(vcard.get_addressbook_name()).splitlines():
        if line == "# new contact":
            strings.append("# Edit contact: %s" % vcard.get_full_name())
        elif line.lower().startswith("# if you want to cancel"):
            continue
        elif line.lower().startswith("first name"):
            strings.append("First name   = %s" % vcard.get_first_name())
        elif line.lower().startswith("last name"):
            strings.append("Last name    = %s" % vcard.get_last_name())
        elif line.lower().startswith("organisation"):
            strings.append("Organisation = %s" % vcard.get_organisation())
        elif line.lower().startswith("phone"):
            if line.lower().startswith("phone1"):
                if vcard.get_phone_numbers().__len__() == 0:
                    strings.append("Phone1 = cell: ")
                else:
                    for index, entry in enumerate(vcard.get_phone_numbers()):
                        strings.append("Phone%d = %s: %s" % (index+1, entry['type'], entry['value']))
        elif line.lower().startswith("email"):
            if line.lower().startswith("email1"):
                if vcard.get_email_addresses().__len__() == 0:
                    strings.append("Email1 = home: ")
                else:
                    for index, entry in enumerate(vcard.get_email_addresses()):
                        strings.append("Email%d = %s: %s" % (index+1, entry['type'], entry['value']))
        elif line.lower().startswith("address"):
            if line.lower().startswith("address1"):
                if vcard.get_post_addresses().__len__() == 0:
                    strings.append("Address1 = home: ; ; ; ; %s" % Config().get_default_country())
                else:
                    for index, entry in enumerate(vcard.get_post_addresses()):
                        strings.append("Address%d = %s: %s; %s; %s; %s; %s" % (index+1, entry['type'],
                                entry['street_and_house_number'], entry['postcode'], entry['city'],
                                entry['region'], entry['country']))
        elif line.lower().startswith("jabber"):
            strings.append("Jabber  = %s" % vcard.get_jabber_id())
        elif line.lower().startswith("skype"):
            strings.append("Skype   = %s" % vcard.get_skype_id())
        elif line.lower().startswith("twitter"):
            strings.append("Twitter = %s" % vcard.get_twitter_id())
        elif line.lower().startswith("webpage"):
            strings.append("Webpage = %s" % vcard.get_webpage())
        elif line.lower().startswith("birthday") and vcard.get_birthday() != None:
            date = vcard.get_birthday()
            strings.append("Birthday = %.2d.%.2d.%.4d" % (date.day, date.month, date.year))
        elif line.lower().startswith("nickname"):
            strings.append("Nickname = %s" % vcard.get_nickname())
        else:
            strings.append(line)
    return '\n'.join(strings)

