# -*- coding: utf-8 -*-

import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile

from email.header import decode_header

from . import helpers
from .actions import Actions
from .carddav_object import CarddavObject
from .config import Config
from .version import khard_version


def create_new_contact(address_book):
    # create temp file
    tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    temp_file_name = tf.name
    old_contact_template = "# create new contact\n" \
        "# Address book: %s\n" \
        "# Vcard version: %s\n" \
        "# if you want to cancel, exit without saving\n\n%s" \
        % (address_book.get_name(), Config().get_preferred_vcard_version(),
           helpers.get_new_contact_template())
    tf.write(old_contact_template)
    tf.close()

    temp_file_creation = helpers.file_modification_date(temp_file_name)
    while True:
        # start vim to edit contact template
        child = subprocess.Popen([Config().get_editor(), temp_file_name])
        child.communicate()
        if temp_file_creation == helpers.file_modification_date(
                temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        tf = open(temp_file_name, "r")
        new_contact_template = tf.read()
        tf.close()

        # try to create new contact
        try:
            new_contact = CarddavObject.from_user_input(
                address_book, new_contact_template,
                Config().get_supported_private_objects(),
                Config().get_preferred_vcard_version())
        except ValueError as e:
            print("\n%s\n" % e)
            while True:
                input_string = input(
                    "Do you want to open the editor again (y/n)? ")
                if input_string.lower() in ["", "n", "q"]:
                    print("Canceled")
                    os.remove(temp_file_name)
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
        else:
            os.remove(temp_file_name)
            break

    # create carddav object from temp file
    if new_contact is None \
            or old_contact_template == new_contact_template:
        print("Canceled")
    else:
        new_contact.write_to_file()
        print("Creation successful\n\n%s" % new_contact.print_vcard())


def modify_existing_contact(old_contact):
    # create temp file and open it with the specified text editor
    tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    temp_file_name = tf.name
    tf.write("# Edit contact: %s\n# Address book: %s\n# Vcard version: %s\n"
             "# if you want to cancel, exit without saving\n\n%s"
             % (old_contact.get_full_name(),
                old_contact.get_address_book().get_name(),
                old_contact.get_version(), old_contact.get_template()))
    tf.close()

    temp_file_creation = helpers.file_modification_date(temp_file_name)
    while True:
        # start editor to edit contact template
        child = subprocess.Popen([Config().get_editor(), temp_file_name])
        child.communicate()
        if temp_file_creation == helpers.file_modification_date(
                temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        tf = open(temp_file_name, "r")
        new_contact_template = tf.read()
        tf.close()

        # try to create contact from user input
        try:
            new_contact = \
                    CarddavObject.from_existing_contact_with_new_user_input(
                        old_contact, new_contact_template)
        except ValueError as e:
            print("\n%s\n" % e)
            while True:
                input_string = input(
                    "Do you want to open the editor again (y/n)? ")
                if input_string.lower() in ["", "n", "q"]:
                    print("Canceled")
                    os.remove(temp_file_name)
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
        else:
            os.remove(temp_file_name)
            break

    # check if the user changed anything
    if new_contact is None \
            or old_contact == new_contact:
        print("Nothing changed\n\n%s" % old_contact.print_vcard())
    else:
        new_contact.write_to_file(overwrite=True)
        print("Modification successful\n\n%s" % new_contact.print_vcard())


def merge_existing_contacts(source_contact, target_contact,
                            delete_source_contact):
    # show warning, if target vcard version is not 3.0 or 4.0
    if target_contact.get_version() not in \
            Config().get_supported_vcard_versions():
        print("Warning:\nThe target contact in which to merge is based on "
              "vcard version %s but khard only supports the modification of "
              "vcards with version 3.0 and 4.0.\nIf you proceed, the contact "
              "will be converted to vcard version %s but beware: This could "
              "corrupt the contact file or cause data loss."
              % (target_contact.get_version(),
                 Config().get_preferred_vcard_version()))
        while True:
            input_string = input("Do you want to proceed anyway (y/n)? ")
            if input_string.lower() in ["", "n", "q"]:
                print("Canceled")
                sys.exit(0)
            if input_string.lower() == "y":
                break
    # create temp files for each vcard
    # source vcard
    source_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    source_temp_file_name = source_tf.name
    source_tf.write("# merge from %s\n# Address book: %s\n"
                    "# Vcard version: %s\n"
                    "# if you want to cancel, exit without saving\n\n%s"
                    % (source_contact.get_full_name(),
                       source_contact.get_address_book().get_name(),
                       source_contact.get_version(),
                       source_contact.get_template()))
    source_tf.close()

    # target vcard
    target_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    target_temp_file_name = target_tf.name
    target_tf.write("# merge into %s\n# Address book: %s\n"
                    "# Vcard version: %s\n"
                    "# if you want to cancel, exit without saving\n\n%s"
                    % (target_contact.get_full_name(),
                       target_contact.get_address_book().get_name(),
                       target_contact.get_version(),
                       target_contact.get_template()))
    target_tf.close()

    target_temp_file_creation = helpers.file_modification_date(
        target_temp_file_name)
    while True:
        # start editor to edit contact template
        child = subprocess.Popen([Config().get_merge_editor(),
                                  source_temp_file_name,
                                  target_temp_file_name])
        child.communicate()
        if target_temp_file_creation == helpers.file_modification_date(
                target_temp_file_name):
            merged_contact = None
            os.remove(source_temp_file_name)
            os.remove(target_temp_file_name)
            break

        # load target template contents
        target_tf = open(target_temp_file_name, "r")
        merged_contact_template = target_tf.read()
        target_tf.close()

        # try to create contact from user input
        try:
            merged_contact = \
                    CarddavObject.from_existing_contact_with_new_user_input(
                        target_contact, merged_contact_template)
        except ValueError as e:
            print("\n%s\n" % e)
            while True:
                input_string = input(
                    "Do you want to open the editor again (y/n)? ")
                if input_string.lower() in ["", "n", "q"]:
                    print("Canceled")
                    os.remove(source_temp_file_name)
                    os.remove(target_temp_file_name)
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
        else:
            os.remove(source_temp_file_name)
            os.remove(target_temp_file_name)
            break

    # compare them
    if merged_contact is None or target_contact == merged_contact:
        print("Target contact unmodified\n\n%s" % target_contact.print_vcard())
        sys.exit(0)

    while True:
        if delete_source_contact:
            input_string = input(
                "Merge contact %s from address book %s into contact %s from "
                "address book %s\n\nTo be removed\n\n%s\n\nMerged\n\n%s\n\n"
                "Are you sure? (y/n): " % (
                    source_contact.get_full_name(),
                    source_contact.get_address_book().get_name(),
                    merged_contact.get_full_name(),
                    merged_contact.get_address_book().get_name(),
                    source_contact.print_vcard(),
                    merged_contact.print_vcard()))
        else:
            input_string = input(
                "Merge contact %s from address book %s into contact %s from "
                "address book %s\n\nKeep unchanged\n\n%s\n\nMerged:\n\n%s\n\n"
                "Are you sure? (y/n): " % (
                    source_contact.get_full_name(),
                    source_contact.get_address_book().get_name(),
                    merged_contact.get_full_name(),
                    merged_contact.get_address_book().get_name(),
                    source_contact.print_vcard(),
                    merged_contact.print_vcard()))
        if input_string.lower() in ["", "n", "q"]:
            print("Canceled")
            return
        if input_string.lower() == "y":
            break

    # save merged_contact to disk and delete source contact
    merged_contact.write_to_file(overwrite=True)
    if delete_source_contact:
        source_contact.delete_vcard_file()
    print("Merge successful\n\n%s" % merged_contact.print_vcard())


def copy_contact(contact, target_address_book, delete_source_contact):
    source_contact_filename = ""
    if delete_source_contact:
        # if source file should be moved, get its file location to delete after
        # successful movement
        source_contact_filename = contact.get_filename()
    else:
        # else create a new uid
        contact.delete_vcard_object("UID")
        contact.add_uid(helpers.get_random_uid())
    # set destination file name
    contact.set_filename(
        os.path.join(target_address_book.get_path(),
                     "%s.vcf" % contact.get_uid()))
    # save
    contact.write_to_file()
    # delete old file
    if os.path.isfile(source_contact_filename):
        os.remove(source_contact_filename)
    print("%s contact %s from address book %s to %s" % (
        "Moved" if delete_source_contact else "Copied",
        contact.get_full_name(),
        contact.get_address_book().get_name(),
        target_address_book.get_name()))


def list_address_books(address_book_list):
    table = [["Index", "Address book"]]
    for index, address_book in enumerate(address_book_list):
        table.append([index+1, address_book.name])
    print(helpers.pretty_print(table))


def list_contacts(vcard_list):
    selected_address_books = []
    for contact in vcard_list:
        if contact.get_address_book() not in selected_address_books:
            selected_address_books.append(contact.get_address_book())
    table = []
    # table header
    if len(selected_address_books) == 1:
        print("Address book: %s" % str(selected_address_books[0]))
        table_header = ["Index", "Name", "Phone", "E-Mail"]
    else:
        print("Address books: %s" % ', '.join(
            [str(book) for book in selected_address_books]))
        table_header = ["Index", "Name", "Phone", "E-Mail", "Address book"]
    if Config().has_uids():
        table_header.append("UID")
    table.append(table_header)
    # table body
    for index, vcard in enumerate(vcard_list):
        row = []
        row.append(index+1)
        if len(vcard.get_nicknames()) > 0 \
                and Config().show_nicknames():
            if Config().display_by_name() == "first_name":
                row.append("%s (Nickname: %s)" % (
                    vcard.get_first_name_last_name(),
                    vcard.get_nicknames()[0]))
            else:
                row.append("%s (Nickname: %s)" % (
                    vcard.get_last_name_first_name(),
                    vcard.get_nicknames()[0]))
        else:
            if Config().display_by_name() == "first_name":
                row.append(vcard.get_first_name_last_name())
            else:
                row.append(vcard.get_last_name_first_name())
        if len(vcard.get_phone_numbers().keys()) > 0:
            phone_dict = vcard.get_phone_numbers()
            first_type = sorted(phone_dict.keys(),
                                key=lambda k: k[0].lower())[0]
            row.append("%s: %s" % (first_type,
                                   sorted(phone_dict.get(first_type))[0]))
        else:
            row.append("")
        if len(vcard.get_email_addresses().keys()) > 0:
            email_dict = vcard.get_email_addresses()
            first_type = sorted(email_dict.keys(),
                                key=lambda k: k[0].lower())[0]
            row.append("%s: %s" % (first_type,
                                   sorted(email_dict.get(first_type))[0]))
        else:
            row.append("")
        if len(selected_address_books) > 1:
            row.append(vcard.get_address_book().get_name())
        if Config().has_uids():
            if Config().get_shortened_uid(vcard.get_uid()):
                row.append(Config().get_shortened_uid(vcard.get_uid()))
            else:
                row.append("")
        table.append(row)
    print(helpers.pretty_print(table))


def list_birthdays(birthday_list):
    table = [["Name", "Birthday"]]
    for row in birthday_list:
        table.append(row.split("\t"))
    print(helpers.pretty_print(table))


def list_phone_numbers(phone_number_list):
    table = [["Name", "Type", "Phone"]]
    for row in phone_number_list:
        table.append(row.split("\t"))
    print(helpers.pretty_print(table))


def list_email_addresses(email_address_list):
    table = [["Name", "Type", "E-Mail"]]
    for row in email_address_list:
        table.append(row.split("\t"))
    print(helpers.pretty_print(table))


def choose_address_book_from_list(header_string, address_book_list):
    if len(address_book_list) == 0:
        return None
    elif len(address_book_list) == 1:
        return address_book_list[0]
    else:
        print(header_string)
        list_address_books(address_book_list)
        while True:
            try:
                input_string = input("Enter Index: ")
                if input_string in ["", "q", "Q"]:
                    print("Canceled")
                    sys.exit(0)
                addr_index = int(input_string)
                if addr_index > 0:
                    # make sure the address book is loaded afterwards
                    selected_address_book = Config().get_address_book(
                        address_book_list[addr_index-1].name)
                else:
                    raise ValueError
            except (EOFError, IndexError, ValueError):
                print("Please enter an index value between 1 and %d or nothing"
                      " to exit." % len(address_book_list))
            else:
                break
        print("")
        return selected_address_book


def choose_vcard_from_list(header_string, vcard_list):
    if vcard_list.__len__() == 0:
        return None
    elif vcard_list.__len__() == 1:
        return vcard_list[0]
    else:
        print(header_string)
        list_contacts(vcard_list)
        while True:
            try:
                input_string = input("Enter Index: ")
                if input_string in ["", "q", "Q"]:
                    print("Canceled")
                    sys.exit(0)
                addr_index = int(input_string)
                if addr_index > 0:
                    selected_vcard = vcard_list[addr_index-1]
                else:
                    raise ValueError
            except (EOFError, IndexError, ValueError):
                print("Please enter an index value between 1 and %d or nothing"
                      " to exit." % len(vcard_list))
            else:
                break
        print("")
        return selected_vcard


def get_contact_list_by_user_selection(address_books, search, strict_search):
    """returns a list of CarddavObject objects
    :param address_books: list of selected address books
    :type address_books: list(AddressBook)
    :param search: filter contact list
    :type search: str
    :param strict_search: if True, search only in full name field
    :type strict_search: bool
    :returns: list of CarddavObject objects
    :rtype: list(CarddavObject)
    """
    return get_contacts(
        address_books, search, "name" if strict_search else "all",
        Config().reverse(), Config().group_by_addressbook(),
        Config().sort_by_name())


def get_contacts(address_books, query, method="all", reverse=False,
                 group=False, sort="first_name"):
    """Get a list of contacts from one or more address books.

    :param address_books: the address books to search
    :type address_books: list(address_book.AddressBook)
    :param query: a search query to select contacts
    :type quer: str
    :param method: the search method, one of "all", "name" or "uid"
    :type method: str
    :param reverse: reverse the order of the returned contacts
    :type reverse: bool
    :param group: group results by address book
    :type group: bool
    :param sort: the field to use for sorting, one of "first_name", "last_name"
    :type sort: str
    :returns: contacts from the address_books that match the query
    :rtype: list(CarddavObject)

    """
    # Search for the contacts.
    contacts = []
    if method == "uid":
        # Search for contacts with uid == query.
        for address_book in address_books:
            for contact in address_book.get_contact_list():
                if contact.get_uid() == query:
                    contacts.append(contact)
        # If that fails, search for contacts where uid starts with query.
        if len(contacts) == 0:
            for address_book in address_books:
                for contact in address_book.get_contact_list():
                    if contact.get_uid().startswith(query):
                        contacts.append(contact)
    else:
        regexp = re.compile(query.replace("*", ".*").replace(" ", ".*"),
                            re.IGNORECASE | re.DOTALL)
        for address_book in address_books:
            for contact in address_book.get_contact_list():
                if method == "name":
                    # only search in contact name
                    if regexp.search(contact.get_full_name()) is not None:
                        contacts.append(contact)
                elif method == "all":
                    # search in all contact fields
                    contact_details = contact.print_vcard()
                    contact_details_without_special_chars = re.sub(
                        "[^a-zA-Z0-9\n]", "", contact_details)
                    if regexp.search(contact_details) is not None or \
                            regexp.search(
                                    contact_details_without_special_chars) \
                            is not None:
                        contacts.append(contact)
    # Sort the contacts.
    if group:
        if sort == "first_name":
            return sorted(contacts, reverse=reverse, key=lambda x: (
                x.get_address_book().get_name().lower(),
                x.get_first_name_last_name().lower()))
        elif sort == "last_name":
            return sorted(contacts, reverse=reverse, key=lambda x: (
                x.get_address_book().get_name().lower(),
                x.get_last_name_first_name().lower()))
        else:
            raise ValueError('sort must be "first_name" or "last_name" not '
                             '{}.'.format(sort))
    else:
        if sort == "first_name":
            return sorted(contacts, reverse=reverse,
                          key=lambda x: x.get_first_name_last_name().lower())
        elif sort == "last_name":
            return sorted(contacts, reverse=reverse,
                          key=lambda x: x.get_last_name_first_name().lower())
        else:
            raise ValueError('sort must be "first_name" or "last_name" not '
                             '{}.'.format(sort))


def new_subcommand(selected_address_books, input_from_stdin_or_file,
                   open_editor):
    """Create a new contact.

    :param selected_address_books: a list of addressbooks that were selected on
        the command line
    :type selected_address_books: list of address_book.AddressBook
    :param input_from_stdin_or_file: the data for the new contact as a yaml
        formatted string
    :type input_from_stdin_or_file: str
    :param open_editor: whether to open the new contact in the edior after
        creation
    :type open_editor: bool
    :returns: None
    :rtype: None

    """
    # ask for address book, in which to create the new contact
    selected_address_book = choose_address_book_from_list(
        "Select address book for new contact", selected_address_books)
    if selected_address_book is None:
        print("Error: address book list is empty")
        sys.exit(1)
    # if there is some data in stdin
    if input_from_stdin_or_file:
        # create new contact from stdin
        try:
            new_contact = CarddavObject.from_user_input(
                selected_address_book, input_from_stdin_or_file,
                Config().get_supported_private_objects(),
                Config().get_preferred_vcard_version())
        except ValueError as e:
            print(e)
            sys.exit(1)
        else:
            new_contact.write_to_file()
        if open_editor:
            modify_existing_contact(new_contact)
        else:
            print("Creation successful\n\n%s" % new_contact.print_vcard())
    else:
        create_new_contact(selected_address_book)


def add_email_subcommand(input_from_stdin_or_file, selected_address_books):
    """Add a new email address to contacts, creating new contacts if necessary.

    :param input_from_stdin_or_file: the input text to search for the new email
    :type input_from_stdin_or_file: str
    :param selected_address_books: the addressbooks that were selected on the
        command line
    :type selected_address_books: list of address_book.AddressBook
    :returns: None
    :rtype: None

    """
    # get name and email address
    email_address = ""
    name = ""
    for line in input_from_stdin_or_file.splitlines():
        if line.startswith("From:"):
            try:
                name = line[6:line.index("<")-1]
                email_address = line[line.index("<")+1:line.index(">")]
            except ValueError:
                email_address = line[6:].strip()
            break
    print("Khard: Add email address to contact")
    if not email_address:
        print("Found no email address")
        sys.exit(1)
    print("Email address: %s" % email_address)
    if not name:
        name = input("Contact's name: ")
    else:
        # remove quotes from name string, otherwise decoding fails
        name = name.replace("\"", "")
        # fix encoding of senders name
        name, encoding = decode_header(name)[0]
        if encoding:
            name = name.decode(encoding).replace("\"", "")
        # query user input.
        user_input = input("Contact's name [%s]: " % name)
        # if empty, use the extracted name from above
        name = user_input or name

    # search for an existing contact
    selected_vcard = choose_vcard_from_list(
        "Select contact for the found e-mail address",
        get_contact_list_by_user_selection(selected_address_books, name, True))
    if selected_vcard is None:
        # create new contact
        while True:
            input_string = input("Contact %s does not exist. Do you want "
                                 "to create it (y/n)? " % name)
            if input_string.lower() in ["", "n", "q"]:
                print("Canceled")
                sys.exit(0)
            if input_string.lower() == "y":
                break
        # ask for address book, in which to create the new contact
        selected_address_book = choose_address_book_from_list(
            "Select address book for new contact",
            Config().get_all_address_books())
        if selected_address_book is None:
            print("Error: address book list is empty")
            sys.exit(1)
        # ask for name and organisation of new contact
        while True:
            first_name = input("First name: ")
            last_name = input("Last name: ")
            organisation = input("Organisation: ")
            if not first_name and not last_name and not organisation:
                print("Error: All fields are empty.")
            else:
                break
        selected_vcard = CarddavObject.from_user_input(
            selected_address_book,
            "First name : %s\nLast name : %s\nOrganisation : %s" % (
                first_name, last_name, organisation),
            Config().get_supported_private_objects(),
            Config().get_preferred_vcard_version())

    # check if the contact already contains the email address
    for type, email_list in sorted(
            selected_vcard.get_email_addresses().items(),
            key=lambda k: k[0].lower()):
        for email in email_list:
            if email == email_address:
                print("The contact %s already contains the email address %s" %
                      (selected_vcard, email_address))
                sys.exit(0)

    # ask for confirmation again
    while True:
        input_string = input(
            "Do you want to add the email address %s to the contact %s (y/n)? "
            % (email_address, selected_vcard.get_full_name()))
        if input_string.lower() in ["", "n", "q"]:
            print("Canceled")
            sys.exit(0)
        if input_string.lower() == "y":
            break

    # ask for the email label
    print("\nAdding email address %s to contact %s\n"
          "Enter email label\n"
          "    vcard 3.0: At least one of home, internet, pref, work, x400\n"
          "    vcard 4.0: At least one of home, internet, pref, work\n"
          "    Or a custom label (only letters" %
          (email_address, selected_vcard))
    while True:
        label = input("email label [internet]: ") or "internet"
        try:
            selected_vcard.add_email_address(label, email_address)
        except ValueError as e:
            print(e)
        else:
            break
    # save to disk
    selected_vcard.write_to_file(overwrite=True)
    print("Done.\n\n%s" % selected_vcard.print_vcard())


def birthdays_subcommand(vcard_list, parsable):
    """Print birthday contact table.

    :param vcard_list: the vcards to search for matching entries which should
        be printed
    :type vcard_list: list of carddav_object.CarddavObject
    :param parsable: machine readable output: columns devided by tabulator (\t)
    :type parsable: bool
    :returns: None
    :rtype: None

    """
    # filter out contacts without a birthday date
    vcard_list = [
        vcard for vcard in vcard_list if vcard.get_birthday() is not None]
    # sort by date (month and day)
    vcard_list.sort(
        key=lambda x: (x.get_birthday().month, x.get_birthday().day))
    # add to string list
    birthday_list = []
    for vcard in vcard_list:
        date = vcard.get_birthday()
        if parsable:
            if Config().display_by_name() == "first_name":
                birthday_list.append("%04d.%02d.%02d\t%s"
                                     % (date.year, date.month, date.day,
                                        vcard.get_first_name_last_name()))
            else:
                birthday_list.append("%04d.%02d.%02d\t%s"
                                     % (date.year, date.month, date.day,
                                        vcard.get_last_name_first_name()))
        else:
            if Config().display_by_name() == "first_name":
                birthday_list.append("%s\t%s"
                                     % (vcard.get_first_name_last_name(),
                                        vcard.get_formatted_birthday()))
            else:
                birthday_list.append("%s\t%s"
                                     % (vcard.get_last_name_first_name(),
                                        vcard.get_formatted_birthday()))
    if len(birthday_list) > 0:
        if parsable:
            print('\n'.join(birthday_list))
        else:
            list_birthdays(birthday_list)
    else:
        if not parsable:
            print("Found no birthdays")
        sys.exit(1)


def phone_subcommand(search_terms, vcard_list, parsable):
    """Print a phone application friendly contact table.

    :param search_terms: used as search term to filter the contacts before
        printing
    :type search_terms: str
    :param vcard_list: the vcards to search for matching entries which should
        be printed
    :type vcard_list: list of carddav_object.CarddavObject
    :param parsable: machine readable output: columns devided by tabulator (\t)
    :type parsable: bool
    :returns: None
    :rtype: None

    """
    all_phone_numbers_list = []
    matching_phone_number_list = []
    regexp = re.compile(search_terms.replace("*", ".*").replace(" ", ".*"),
                        re.IGNORECASE)
    for vcard in vcard_list:
        for type, number_list in sorted(vcard.get_phone_numbers().items(),
                                        key=lambda k: k[0].lower()):
            for number in sorted(number_list):
                # create output line
                if parsable:
                    # parsable option: start with phone number
                    if Config().display_by_name() == "first_name":
                        phone_number_line = "%s\t%s\t%s" % (
                            number, vcard.get_first_name_last_name(), type)
                    else:
                        phone_number_line = "%s\t%s\t%s" % (
                            number, vcard.get_last_name_first_name(), type)
                else:
                    # else: start with name
                    if Config().display_by_name() == "first_name":
                        phone_number_line = "%s\t%s\t%s" % (
                            vcard.get_first_name_last_name(), type, number)
                    else:
                        phone_number_line = "%s\t%s\t%s" % (
                            vcard.get_last_name_first_name(), type, number)
                if len(re.sub("\D", "", search_terms)) >= 3:
                    # The user likely searches for a phone number cause the
                    # search string contains at least three digits.  So we
                    # remove all non-digit chars from the phone number field
                    # and match against that.
                    if regexp.search(re.sub("\D", "", number)) is not None:
                        matching_phone_number_list.append(phone_number_line)
                else:
                    # The user doesn't search for a phone number so we can
                    # perform a standard search without removing all non-digit
                    # chars from the phone number string
                    if regexp.search(phone_number_line) is not None:
                        matching_phone_number_list.append(phone_number_line)
                # collect all phone numbers in a different list as fallback
                all_phone_numbers_list.append(phone_number_line)
    if len(matching_phone_number_list) > 0:
        if parsable:
            print('\n'.join(matching_phone_number_list))
        else:
            list_phone_numbers(matching_phone_number_list)
    elif len(all_phone_numbers_list) > 0:
        if parsable:
            print('\n'.join(all_phone_numbers_list))
        else:
            list_phone_numbers(all_phone_numbers_list)
    else:
        if not parsable:
            print("Found no phone numbers")
        sys.exit(1)


def email_subcommand(search_terms, vcard_list, parsable, remove_first_line):
    """Print a mail client friendly contacts table that is compatible with the
    default format used by mutt.
    Output format:
        single line of text
        email_address\tname\ttype
        email_address\tname\ttype
        [...]

    :param search_terms: used as search term to filter the contacts before
        printing
    :type search_terms: str
    :param vcard_list: the vcards to search for matching entries which should
        be printed
    :type vcard_list: list of carddav_object.CarddavObject
    :param parsable: machine readable output: columns devided by tabulator (\t)
    :type parsable: bool
    :param remove_first_line: remove first line (searching for '' ...)
    :type remove_first_line: bool
    :returns: None
    :rtype: None

    """
    matching_email_address_list = []
    all_email_address_list = []
    regexp = re.compile(search_terms.replace("*", ".*").replace(" ", ".*"),
                        re.IGNORECASE)
    for vcard in vcard_list:
        for type, email_list in sorted(vcard.get_email_addresses().items(),
                                       key=lambda k: k[0].lower()):
            for email in sorted(email_list):
                # create output line
                if parsable:
                    # parsable option: start with email address
                    if Config().display_by_name() == "first_name":
                        email_address_line = "%s\t%s\t%s" % (
                            email, vcard.get_first_name_last_name(), type)
                    else:
                        email_address_line = "%s\t%s\t%s" % (
                            email, vcard.get_last_name_first_name(), type)
                else:
                    # else: start with name
                    if Config().display_by_name() == "first_name":
                        email_address_line = "%s\t%s\t%s" % (
                            vcard.get_first_name_last_name(), type, email)
                    else:
                        email_address_line = "%s\t%s\t%s" % (
                            vcard.get_last_name_first_name(), type, email)
                if regexp.search(email_address_line) is not None:
                    matching_email_address_list.append(email_address_line)
                # collect all email addresses in a different list as fallback
                all_email_address_list.append(email_address_line)
    if len(matching_email_address_list) > 0:
        if parsable:
            if not remove_first_line:
                # at least mutt requires that line
                print("searching for '%s' ..." % search_terms)
            print('\n'.join(matching_email_address_list))
        else:
            list_email_addresses(matching_email_address_list)
    elif len(all_email_address_list) > 0:
        if parsable:
            if not remove_first_line:
                # at least mutt requires that line
                print("searching for '%s' ..." % search_terms)
            print('\n'.join(all_email_address_list))
        else:
            list_email_addresses(all_email_address_list)
    else:
        if not parsable:
            print("Found no email addresses")
        elif not remove_first_line:
            print("searching for '%s' ..." % search_terms)
        sys.exit(1)


def list_subcommand(vcard_list):
    """Print a user friendly contacts table.

    :param vcard_list: the vcards to print
    :type vcard_list: list of carddav_object.CarddavObject
    :returns: None
    :rtype: None

    """
    if len(vcard_list) == 0:
        print("Found no contacts")
        sys.exit(1)
    list_contacts(vcard_list)


def modify_subcommand(selected_vcard, input_from_stdin_or_file, open_editor):
    """Modify a contact in an external editor.

    :param selected_vcard: the contact to modify
    :type selected_vcard: carddav_object.CarddavObject
    :param input_from_stdin_or_file: new data from stdin (or a file) that
        should be incorperated into the contact, this should be a yaml
        formatted string
    :type input_from_stdin_or_file: str
    :param open_editor: whether to open the new contact in the edior after
        creation
    :type open_editor: bool
    :returns: None
    :rtype: None

    """
    # show warning, if vcard version of selected contact is not 3.0 or 4.0
    if selected_vcard.get_version() not in \
            Config().get_supported_vcard_versions():
        print("Warning:\nThe selected contact is based on vcard version %s "
              "but khard only supports the creation and modification of vcards"
              " with version 3.0 and 4.0.\nIf you proceed, the contact will be"
              " converted to vcard version %s but beware: This could corrupt "
              "the contact file or cause data loss."
              % (selected_vcard.get_version(),
                 Config().get_preferred_vcard_version()))
        while True:
            input_string = input("Do you want to proceed anyway (y/n)? ")
            if input_string.lower() in ["", "n", "q"]:
                print("Canceled")
                sys.exit(0)
            if input_string.lower() == "y":
                break
    # if there is some data in stdin
    if input_from_stdin_or_file:
        # create new contact from stdin
        try:
            new_contact = \
                    CarddavObject.from_existing_contact_with_new_user_input(
                        selected_vcard, input_from_stdin_or_file)
        except ValueError as e:
            print(e)
            sys.exit(1)
        if selected_vcard == new_contact:
            print("Nothing changed\n\n%s" % new_contact.print_vcard())
        else:
            print("Modification\n\n%s\n" % new_contact.print_vcard())
            while True:
                input_string = input("Do you want to proceed (y/n)? ")
                if input_string.lower() in ["", "n", "q"]:
                    print("Canceled")
                    break
                if input_string.lower() == "y":
                    new_contact.write_to_file(overwrite=True)
                    if open_editor:
                        modify_existing_contact(new_contact)
                    else:
                        print("Done")
                    break
    else:
        modify_existing_contact(selected_vcard)


def remove_subcommand(selected_vcard):
    """Remove a contact from the addressbook.

    :param selected_vcard: the contact to delete
    :type selected_vcard: carddav_object.CarddavObject
    :returns: None
    :rtype: None

    """
    while True:
        input_string = input(
            "Deleting contact %s from address book %s. Are you sure? (y/n): "
            % (selected_vcard.get_full_name(),
               selected_vcard.get_address_book().get_name()))
        if input_string.lower() in ["", "n", "q"]:
            print("Canceled")
            sys.exit(0)
        if input_string.lower() == "y":
            break
    selected_vcard.delete_vcard_file()
    print("Contact deleted successfully")


def source_subcommand(selected_vcard, editor):
    """Open the vcard file for a contact in an external editor.

    :param selected_vcard: the contact to edit
    :type selected_vcard: carddav_object.CarddavObject
    :param editor: the eitor command to use
    :type editor: str
    :returns: None
    :rtype: None

    """
    child = subprocess.Popen([editor, selected_vcard.get_filename()])
    child.communicate()


def merge_subcommand(vcard_list, selected_address_books, search_terms,
                     target_uid):
    """Merge two contacts into one.

    :param vcard_list: the vcards from which to choose contacts for mergeing
    :type vcard_list: list of carddav_object.CarddavObject
    :param selected_address_books: the addressbooks to use to find the target
        contact
    :type selected_address_books: list(addressbook.AddressBook)
    :param search_terms: the search terms to find the target contact
    :type search_terms: str
    :param target_uid: the uid of the target contact or empty
    :type target_uid: str
    :returns: None
    :rtype: None

    """
    # Check arguments.
    if target_uid != "" and search_terms != "":
        print("You can not specify a target uid and target search terms for a "
              "merge.")
        sys.exit(1)
    # Find possible target contacts.
    if target_uid != "":
        target_vcards = get_contacts(selected_address_books, target_uid,
                                     method="uid")
        # We require that the uid given can uniquely identify a contact.
        if len(target_vcards) != 1:
            if len(target_vcards) == 0:
                print("Found no contact for target uid %s" % target_uid)
            else:
                print("Found multiple contacts for target uid %s" % target_uid)
                for vcard in target_vcards:
                    print("    %s: %s" % (vcard.get_full_name(),
                                          vcard.get_uid()))
            sys.exit(1)
    else:
        target_vcards = get_contact_list_by_user_selection(
            selected_address_books, search_terms, False)
    # get the source vcard, from which to merge
    source_vcard = choose_vcard_from_list(
            "Select contact from which to merge", vcard_list)
    if source_vcard is None:
        print("Found no source contact for merging")
        sys.exit(1)
    else:
        print("Merge from %s from address book %s\n\n"
              % (source_vcard.get_full_name(),
                 source_vcard.get_address_book().get_name()))
    # get the target vcard, into which to merge
    target_vcard = choose_vcard_from_list(
            "Select contact into which to merge", target_vcards)
    if target_vcard is None:
        print("Found no target contact for merging")
        sys.exit(1)
    else:
        print("Merge into %s from address book %s\n\n"
              % (target_vcard.get_full_name(),
                 target_vcard.get_address_book().get_name()))
    # merging
    if source_vcard == target_vcard:
        print("The selected contacts are already identical")
    else:
        merge_existing_contacts(source_vcard, target_vcard, True)


def copy_or_move_subcommand(action, vcard_list, target_address_book_list):
    """Copy or move a contact to a different address book.

    :action: the string "copy" or "move" to indicate what to do
    :type action: str
    :param vcard_list: the contact list from which to select one for the action
    :type vcard_list: list of carddav_object.CarddavObject
    :param target_address_book_list: the list of target address books
    :type target_address_book_list: list(addressbook.AddressBook)
    :returns: None
    :rtype: None

    """
    # get the source vcard, which to copy or move
    source_vcard = choose_vcard_from_list(
            "Select contact to %s" % action.title(), vcard_list)
    if source_vcard is None:
        print("Found no contact")
        sys.exit(1)
    else:
        print("%s contact %s from address book %s"
              % (action.title(), source_vcard.get_full_name(),
                 source_vcard.get_address_book().get_name()))

    # get target address book
    if len(target_address_book_list) == 1 \
            and target_address_book_list[0] == source_vcard.get_address_book():
        print("The address book %s already contains the contact %s"
              % (source_vcard.get_full_name(),
                 target_address_book_list[0].get_name()))
        sys.exit(1)
    else:
        available_address_books = []
        for address_book in target_address_book_list:
            if address_book != source_vcard.get_address_book():
                available_address_books.append(address_book)
        selected_target_address_book = choose_address_book_from_list(
            "Select target address book", available_address_books)
        if selected_target_address_book is None:
            print("Error: address book list is empty")
            sys.exit(1)

    # check if a contact already exists in the target address book
    target_vcard = choose_vcard_from_list(
            "Select target contact which to overwrite",
            get_contact_list_by_user_selection(
                [selected_target_address_book], source_vcard.get_full_name(),
                True))
    # If the target contact doesn't exist, move or copy the source contact into
    # the target address book without further questions.
    if target_vcard is None:
        copy_contact(source_vcard, selected_target_address_book,
                     action == "move")
    else:
        if source_vcard == target_vcard:
            # source and target contact are identical
            print("Target contact: %s" % target_vcard)
            if action == "move":
                copy_contact(source_vcard, selected_target_address_book, True)
            else:
                print("The selected contacts are already identical")
        else:
            # source and target contacts are different
            # either overwrite the target one or merge into target contact
            print("The address book %s already contains the contact %s\n\n"
                  "Source\n\n%s\n\nTarget\n\n%s\n\n"
                  "Possible actions:\n"
                  "  a: %s anyway\n"
                  "  m: Merge from source into target contact\n"
                  "  o: Overwrite target contact\n"
                  "  q: Quit"
                  % (
                      target_vcard.get_address_book().get_name(),
                      source_vcard.get_full_name(), source_vcard.print_vcard(),
                      target_vcard.print_vcard(),
                      "Move" if action == "move" else "Copy"))
            while True:
                input_string = input("Your choice: ")
                if input_string.lower() == "a":
                    copy_contact(source_vcard, selected_target_address_book,
                                 action == "move")
                    break
                if input_string.lower() == "o":
                    copy_contact(source_vcard, selected_target_address_book,
                                 action == "move")
                    target_vcard.delete_vcard_file()
                    break
                if input_string.lower() == "m":
                    merge_existing_contacts(source_vcard, target_vcard,
                                            action == "move")
                    break
                if input_string.lower() in ["", "q"]:
                    print("Canceled")
                    break


# Patch argparse.ArgumentParser, taken from http://stackoverflow.com/a/26379693
def set_default_subparser(self, name):
    """Default subparser selection. Call after setup, just before parse_args().

    :param name: the name of the subparser to call by default
    :type name: str
    :returns: None
    :rtype: None

    """
    for arg in sys.argv[1:]:
        if arg in ['-h', '--help']:  # global help if no subparser
            break
    else:
        for x in self._subparsers._actions:
            if not isinstance(x, argparse._SubParsersAction):
                continue
            for sp_name in x._name_parser_map.keys():
                if sp_name in sys.argv[1:]:
                    return  # found a subcommand
        else:
            # Find position to insert default command.
            options = self._option_string_actions.keys()
            for index, arg in enumerate(sys.argv[1:], 1):
                if arg in options:
                    continue
                else:
                    # Insert command before first non option string (possibly
                    # an argument for the subcommand).
                    sys.argv.insert(index, name)
                    break
            else:
                # Otherwise append default command.
                sys.argv.append(name)


argparse.ArgumentParser.set_default_subparser = set_default_subparser


def main():
    # create the args parser
    parser = argparse.ArgumentParser(
        description="Khard is a carddav address book for the console",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--debug", action="store_true",
                        help="enable debug output")
    parser.add_argument("--skip-unparsable", action="store_true",
                        help="skip unparsable vcard files")
    parser.add_argument("-v", "--version", action="version",
                        version="Khard version %s" % khard_version)

    # create address book subparsers with different help texts
    default_addressbook_parser = argparse.ArgumentParser(add_help=False)
    default_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of contacts")
    new_addressbook_parser = argparse.ArgumentParser(add_help=False)
    new_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify address book in which to create the new contact")
    copy_move_addressbook_parser = argparse.ArgumentParser(add_help=False)
    copy_move_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of contacts")
    copy_move_addressbook_parser.add_argument(
        "-A", "--target-addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify target address book in which to copy / move the "
        "selected contact")
    merge_addressbook_parser = argparse.ArgumentParser(add_help=False)
    merge_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of source contacts")
    merge_addressbook_parser.add_argument(
        "-A", "--target-addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of target contacts")

    # create input file subparsers with different help texts
    email_header_input_file_parser = argparse.ArgumentParser(add_help=False)
    email_header_input_file_parser.add_argument(
        "-i", "--input-file", default="-",
        help="Specify input email header file name or use stdin by default")
    template_input_file_parser = argparse.ArgumentParser(add_help=False)
    template_input_file_parser.add_argument(
        "-i", "--input-file", default="-",
        help="Specify input template file name or use stdin by default")
    template_input_file_parser.add_argument(
        "--open-editor", action="store_true", help="Open the default text "
        "editor after successful creation of new contact")

    # create sort subparser
    sort_parser = argparse.ArgumentParser(add_help=False)
    sort_parser.add_argument(
        "-d", "--display", choices=("first_name", "last_name"),
        help="Display names in contact table by first or last name")
    sort_parser.add_argument(
        "-g", "--group-by-addressbook", action="store_true",
        help="Group contact table by address book")
    sort_parser.add_argument(
        "-r", "--reverse", action="store_true",
        help="Reverse order of contact table")
    sort_parser.add_argument(
        "-s", "--sort", choices=("first_name", "last_name"),
        help="Sort contact table by first or last name")

    # create search subparsers
    default_search_parser = argparse.ArgumentParser(add_help=False)
    default_search_parser.add_argument(
        "-c", "--search-in-source-files", action="store_true",
        help="Look into source vcf files to speed up search queries in "
        "large address books. Beware that this option could lead "
        "to incomplete results.")
    default_search_parser.add_argument(
        "-e", "--strict-search", action="store_true",
        help="narrow contact search to name field")
    default_search_parser.add_argument(
        "-u", "--uid", default="", help="select contact by uid")
    default_search_parser.add_argument(
        "search_terms", nargs="*", metavar="search terms",
        help="search in all fields to find matching contact")
    merge_search_parser = argparse.ArgumentParser(add_help=False)
    merge_search_parser.add_argument(
        "-c", "--search-in-source-files", action="store_true",
        help="Look into source vcf files to speed up search queries in "
        "large address books. Beware that this option could lead "
        "to incomplete results.")
    merge_search_parser.add_argument(
        "-e", "--strict-search", action="store_true",
        help="narrow contact search to name fields")
    merge_search_parser.add_argument(
        "-t", "--target-contact", "--target", default="",
        help="search in all fields to find matching target contact")
    merge_search_parser.add_argument(
        "-u", "--uid", default="", help="select source contact by uid")
    merge_search_parser.add_argument(
        "-U", "--target-uid", default="", help="select target contact by uid")
    merge_search_parser.add_argument(
        "source_search_terms", nargs="*", metavar="source",
        help="search in all fields to find matching source contact")

    # create subparsers for actions
    subparsers = parser.add_subparsers(dest="action")
    subparsers.add_parser(
        "list",
        aliases=Actions.get_alias_list_for_action("list"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list all (selected) contacts",
        help="list all (selected) contacts")
    subparsers.add_parser(
        "details",
        aliases=Actions.get_alias_list_for_action("details"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="display detailed information about one contact",
        help="display detailed information about one contact")
    export_parser = subparsers.add_parser(
        "export",
        aliases=Actions.get_alias_list_for_action("export"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="export a contact to the custom yaml format that is "
        "also used for editing and creating contacts",
        help="export a contact to the custom yaml format that is also "
        "used for editing and creating contacts")
    export_parser.add_argument(
        "--empty-contact-template", action="store_true",
        help="Export an empty contact template")
    export_parser.add_argument(
        "-o", "--output-file", default=sys.stdout,
        type=argparse.FileType("w"),
        help="Specify output template file name or use stdout by default")
    birthdays_parser = subparsers.add_parser(
        "birthdays",
        aliases=Actions.get_alias_list_for_action("birthdays"),
        parents=[default_addressbook_parser, default_search_parser],
        description="list birthdays (sorted by month and day)",
        help="list birthdays (sorted by month and day)")
    birthdays_parser.add_argument(
        "-d", "--display", choices=("first_name", "last_name"),
        help="Display names in birthdays table by first or last name")
    birthdays_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: name\\tdate")
    email_parser = subparsers.add_parser(
        "email",
        aliases=Actions.get_alias_list_for_action("email"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list email addresses",
        help="list email addresses")
    email_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: address\\tname\\ttype")
    email_parser.add_argument(
        "--remove-first-line", action="store_true",
        help="remove \"searching for '' ...\" line from parsable output "
        "(that line is required by mutt)")
    phone_parser = subparsers.add_parser(
        "phone",
        aliases=Actions.get_alias_list_for_action("phone"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list phone numbers",
        help="list phone numbers")
    phone_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: number\\tname\\ttype")
    subparsers.add_parser(
        "source",
        aliases=Actions.get_alias_list_for_action("source"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="edit the vcard file of a contact directly",
        help="edit the vcard file of a contact directly")
    new_parser = subparsers.add_parser(
        "new",
        aliases=Actions.get_alias_list_for_action("new"),
        parents=[new_addressbook_parser, template_input_file_parser],
        description="create a new contact",
        help="create a new contact")
    new_parser.add_argument(
        "--vcard-version", choices=("3.0", "4.0"),
        help="Select preferred vcard version for new contact")
    add_email_parser = subparsers.add_parser(
        "add-email",
        aliases=Actions.get_alias_list_for_action("add-email"),
        parents=[default_addressbook_parser, email_header_input_file_parser,
                 default_search_parser, sort_parser],
        description="Extract email address from the \"From:\" field of an "
        "email header and add to an existing contact or create a new one",
        help="Extract email address from the \"From:\" field of an email "
        "header and add to an existing contact or create a new one")
    add_email_parser.add_argument(
        "--vcard-version", choices=("3.0", "4.0"),
        help="Select preferred vcard version for new contact")
    subparsers.add_parser(
        "merge",
        aliases=Actions.get_alias_list_for_action("merge"),
        parents=[merge_addressbook_parser, merge_search_parser, sort_parser],
        description="merge two contacts",
        help="merge two contacts")
    subparsers.add_parser(
        "modify",
        aliases=Actions.get_alias_list_for_action("modify"),
        parents=[default_addressbook_parser, template_input_file_parser,
                 default_search_parser, sort_parser],
        description="edit the data of a contact",
        help="edit the data of a contact")
    subparsers.add_parser(
        "copy",
        aliases=Actions.get_alias_list_for_action("copy"),
        parents=[copy_move_addressbook_parser, default_search_parser,
                 sort_parser],
        description="copy a contact to a different addressbook",
        help="copy a contact to a different addressbook")
    subparsers.add_parser(
        "move",
        aliases=Actions.get_alias_list_for_action("move"),
        parents=[copy_move_addressbook_parser, default_search_parser,
                 sort_parser],
        description="move a contact to a different addressbook",
        help="move a contact to a different addressbook")
    subparsers.add_parser(
        "remove",
        aliases=Actions.get_alias_list_for_action("remove"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="remove a contact",
        help="remove a contact")
    subparsers.add_parser(
        "addressbooks",
        aliases=Actions.get_alias_list_for_action("addressbooks"),
        description="list addressbooks",
        help="list addressbooks")

    parser.set_default_subparser(Config().get_default_action())
    args = parser.parse_args()

    # debug
    if "debug" in args and args.debug:
        Config().set_debug(True)
    if Config().debug():
        logging.basicConfig(level=logging.DEBUG)
    logging.debug("args={}".format(args))

    # if args.action isn't one of the defined actions, it must be an alias
    if args.action not in Actions.get_list_of_all_actions():
        # convert alias to corresponding action
        # example: "ls" --> "list"
        args.action = Actions.get_action_for_alias(args.action)

    # display by name: first or last name
    if "display" in args and args.display:
        Config().set_display_by_name(args.display)

    # group by address book
    if "group_by_addressbook" in args and args.group_by_addressbook:
        Config().set_group_by_addressbook(True)

    # reverse contact list
    if "reverse" in args and args.reverse:
        Config().set_reverse(True)

    # sort criteria: first or last name
    if "sort" in args and args.sort:
        Config().set_sort_by_name(args.sort)

    # preferred vcard version
    if "vcard_version" in args and args.vcard_version:
        Config().set_preferred_vcard_version(args.vcard_version)

    # search in source files
    if "search_in_source_files" in args and args.search_in_source_files:
        Config().set_search_in_source_files(True)

    # skip unparsable vcards
    if "skip_unparsable" in args and args.skip_unparsable:
        Config().set_skip_unparsable(True)

    # get all possible search queries for address book parsing
    search_query_list = []
    if "source_search_terms" in args and args.source_search_terms:
        search_query_list.append(".*".join(
            [x.replace("*", ".*") for x in args.source_search_terms]))
    if "search_terms" in args and args.search_terms:
        search_query_list.append(".*".join(
            [x.replace("*", ".*") for x in args.search_terms]))
    if "target_contact" in args and args.target_contact:
        search_query_list.append(
            args.target_contact.replace("*", ".*").replace(" ", ".*"))
    if "uid" in args and args.uid:
        search_query_list.append(
            args.uid.replace("*", ".*").replace(" ", ".*"))
    if "target_uid" in args and args.target_uid:
        search_query_list.append(
            args.target_uid.replace("*", ".*").replace(" ", ".*"))
    # create regexp
    search_queries = None
    if search_query_list:
        search_queries = "^.*(%s).*$" % ')|('.join(search_query_list)

    # load address books
    if "addressbook" in args and args.addressbook != []:
        # load address books which are defined in the configuration file
        for index, name in enumerate(args.addressbook):
            address_book = Config().get_address_book(name, search_queries)
            if address_book is None:
                print("Error: The entered address book \"%s\" does not exist."
                      "\nPossible values are: %s" % (
                          name, ', '.join([str(book) for book in
                                           Config().get_all_address_books()])))
                sys.exit(1)
            else:
                args.addressbook[index] = address_book
    else:
        # load contacts of all address books
        args.addressbook = []
        for address_book in Config().get_all_address_books():
            args.addressbook.append(Config().get_address_book(
                address_book.get_name(), search_queries))
    logging.debug("addressbooks: {}".format(args.addressbook))

    # load target address books
    if "target_addressbook" in args and args.target_addressbook != []:
        for index, name in enumerate(args.target_addressbook):
            address_book = Config().get_address_book(name, search_queries)
            if address_book is None:
                print("Error: The entered address book \"%s\" does not exist."
                      "\nPossible values are: %s" % (
                          name, ', '.join([str(book) for book in
                                           Config().get_all_address_books()])))
                sys.exit(1)
            else:
                args.target_addressbook[index] = address_book
    else:
        args.target_addressbook = []
        for address_book in Config().get_all_address_books():
            args.target_addressbook.append(Config().get_address_book(
                address_book.get_name(), search_queries))
    logging.debug("target addressbooks: {}".format(args.target_addressbook))

    # fill contact list
    vcard_list = []
    if "uid" in args and args.uid != "":
        # If an uid was given we use it to find the contact.
        logging.debug("args.uid={}".format(args.uid))
        # We require that no search terms where given.
        if ("search_terms" in args and args.search_terms != []) or (
                "source_search_terms" in args and
                args.source_search_terms != []):
            parser.error("You can not give arbitrary search terms and "
                         "--uid at the same time.")
        else:
            # set search terms to the empty string to prevent errors in
            # phone and email actions
            args.search_terms = ""
        vcard_list = get_contacts(Config().get_all_address_books(),
                                  args.uid, method="uid")
        # We require that the uid given can uniquely identify a contact.
        if len(vcard_list) != 1:
            if len(vcard_list) == 0:
                print("Found no contact for %suid %s" % (
                    "source " if args.action == "merge" else "", args.uid))
            else:
                print("Found multiple contacts for %suid %s" % (
                    "source " if args.action == "merge" else "", args.uid))
                for vcard in vcard_list:
                    print("    %s: %s" % (vcard.get_full_name(),
                                          vcard.get_uid()))
            sys.exit(1)
    else:
        # No uid was given so we try to use the search terms to select a
        # contact.
        if hasattr(args, "source_search_terms"):
            # exception for merge command
            args.search_terms = " ".join(args.source_search_terms)
        elif hasattr(args, "search_terms"):
            args.search_terms = " ".join(args.search_terms)
        else:
            # If no search terms where given on the command line we match
            # everything with the empty search pattern.
            args.search_terms = ""
        logging.debug("args.search_terms={}".format(args.search_terms))
        vcard_list = get_contact_list_by_user_selection(
            args.addressbook, args.search_terms,
            args.strict_search if "strict_search" in args else False)

    # read from template file or stdin if available
    input_from_stdin_or_file = ""
    if hasattr(args, "input_file"):
        if args.input_file != "-":
            # try to read from specified input file
            try:
                with open(args.input_file, "r") as f:
                    input_from_stdin_or_file = f.read()
            except IOError as e:
                print("Error: %s\n       File: %s" % (e.strerror, e.filename))
                sys.exit(1)
        elif not sys.stdin.isatty():
            # try to read from stdin
            try:
                input_from_stdin_or_file = sys.stdin.read()
            except IOError as e:
                print("Error: Can't read from stdin")
                sys.exit(1)
            # try to reopen console
            # otherwise further user interaction is not possible (for example
            # selecting a contact from the contact table)
            try:
                sys.stdin = open('/dev/tty')
            except IOError as e:
                pass

    if args.action == "new":
        new_subcommand(args.addressbook, input_from_stdin_or_file,
                       args.open_editor)
    elif args.action == "add-email":
        add_email_subcommand(input_from_stdin_or_file, args.addressbook)
    elif args.action == "birthdays":
        birthdays_subcommand(vcard_list, args.parsable)
    elif args.action == "phone":
        phone_subcommand(args.search_terms, vcard_list, args.parsable)
    elif args.action == "email":
        email_subcommand(args.search_terms, vcard_list,
                         args.parsable, args.remove_first_line)
    elif args.action == "list":
        list_subcommand(vcard_list)
    elif args.action == "export" \
            and "empty_contact_template" in args \
            and args.empty_contact_template:
        # export empty template must work without selecting a contact first
        args.output_file.write(
                "# Contact template for khard version %s\n#\n"
                "# Use this yaml formatted template to create a new contact:\n"
                "#   either with: khard new -a address_book -i template.yaml\n"
                "#   or with: cat template.yaml | khard new -a address_book\n\n"
                "%s" % (khard_version, helpers.get_new_contact_template()))
    elif args.action in ["details", "modify", "remove", "source", "export"]:
        selected_vcard = choose_vcard_from_list(
                "Select contact for %s action" % args.action.title(),
                vcard_list)
        if selected_vcard is None:
            print("Found no contact")
            sys.exit(1)
        if args.action == "details":
            print(selected_vcard.print_vcard())
        elif args.action == "export":
            args.output_file.write(
                "# Contact template for khard version %s\n"
                "# Name: %s\n# Vcard version: %s\n\n%s"
                % (khard_version, selected_vcard.get_full_name(),
                   selected_vcard.get_version(),
                   selected_vcard.get_template()))
        elif args.action == "modify":
            modify_subcommand(selected_vcard, input_from_stdin_or_file,
                              args.open_editor)
        elif args.action == "remove":
            remove_subcommand(selected_vcard)
        elif args.action == "source":
            source_subcommand(selected_vcard, Config().get_editor())
    elif args.action == "merge":
        merge_subcommand(vcard_list, args.target_addressbook,
                         args.target_contact, args.target_uid)
    elif args.action in ["copy", "move"]:
        copy_or_move_subcommand(
            args.action, vcard_list, args.target_addressbook)
    elif args.action == "addressbooks":
        print(
            '\n'.join(str(book) for book in Config().get_all_address_books()))
