# -*- coding: utf-8 -*-

import argparse
import datetime
from email import message_from_string
from email.policy import SMTP as SMTP_POLICY
import logging
import os
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
from unidecode import unidecode

from . import helpers
from .actions import Actions
from .address_book import AddressBookCollection
from .carddav_object import CarddavObject
from .config import Config
from .version import khard_version


config = None


def write_temp_file(text=""):
    """Create a new temporary file and write some initial text to it.

    :param text: the text to write to the temp file
    :type text: str
    :returns: the file name of the newly created temp file
    :rtype: str

    """
    with NamedTemporaryFile(mode='w+t', suffix='.yml', delete=False) \
         as tempfile:
        tempfile.write(text)
        return tempfile.name


def create_new_contact(address_book):
    # create temp file
    template = (
        "# create new contact\n# Address book: %s\n# Vcard version: %s\n"
        "# if you want to cancel, exit without saving\n\n%s"
        % (address_book, config.get_preferred_vcard_version(),
           helpers.get_new_contact_template(
               config.get_supported_private_objects())))
    temp_file_name = write_temp_file(template)
    temp_file_creation = helpers.file_modification_date(temp_file_name)

    while True:
        # start vim to edit contact template
        child = subprocess.Popen([config.editor, temp_file_name])
        child.communicate()
        if temp_file_creation == helpers.file_modification_date(
                temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        with open(temp_file_name, "r") as tf:
            new_contact_yaml = tf.read()

        # try to create new contact
        try:
            new_contact = CarddavObject.from_user_input(
                address_book, new_contact_yaml,
                config.get_supported_private_objects(),
                config.get_preferred_vcard_version(),
                config.localize_dates())
        except ValueError as err:
            print("\n%s\n" % err)
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
    if new_contact is None or template == new_contact_yaml:
        print("Canceled")
    else:
        new_contact.write_to_file()
        print("Creation successful\n\n%s" % new_contact.print_vcard())


def modify_existing_contact(old_contact):
    # create temp file and open it with the specified text editor
    temp_file_name = write_temp_file(
        "# Edit contact: %s\n# Address book: %s\n# Vcard version: %s\n"
        "# if you want to cancel, exit without saving\n\n%s"
        % (old_contact, old_contact.address_book, old_contact.get_version(),
           old_contact.get_template()))

    temp_file_creation = helpers.file_modification_date(temp_file_name)

    while True:
        # start editor to edit contact template
        child = subprocess.Popen([config.editor, temp_file_name])
        child.communicate()
        if temp_file_creation == helpers.file_modification_date(
                temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        with open(temp_file_name, "r") as tf:
            new_contact_template = tf.read()

        # try to create contact from user input
        try:
            new_contact = \
                CarddavObject.from_existing_contact_with_new_user_input(
                    old_contact, new_contact_template, config.localize_dates())
        except ValueError as err:
            print("\n%s\n" % err)
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
    if new_contact is None or old_contact == new_contact:
        print("Nothing changed\n\n%s" % old_contact.print_vcard())
    else:
        new_contact.write_to_file(overwrite=True)
        print("Modification successful\n\n%s" % new_contact.print_vcard())


def merge_existing_contacts(source_contact, target_contact,
                            delete_source_contact):
    # show warning, if target vcard version is not 3.0 or 4.0
    if target_contact.get_version() not in config.supported_vcard_versions:
        print("Warning:\nThe target contact in which to merge is based on "
              "vcard version %s but khard only supports the modification of "
              "vcards with version 3.0 and 4.0.\nIf you proceed, the contact "
              "will be converted to vcard version %s but beware: This could "
              "corrupt the contact file or cause data loss."
              % (target_contact.get_version(),
                 config.get_preferred_vcard_version()))
        while True:
            input_string = input("Do you want to proceed anyway (y/n)? ")
            if input_string.lower() in ["", "n", "q"]:
                print("Canceled")
                sys.exit(0)
            if input_string.lower() == "y":
                break
    # create temp files for each vcard
    # source vcard
    source_temp_file_name = write_temp_file(
        "# merge from %s\n# Address book: %s\n# Vcard version: %s\n"
        "# if you want to cancel, exit without saving\n\n%s"
        % (source_contact, source_contact.address_book,
           source_contact.get_version(), source_contact.get_template()))
    # target vcard
    target_temp_file_name = write_temp_file(
        "# merge into %s\n# Address book: %s\n# Vcard version: %s\n"
        "# if you want to cancel, exit without saving\n\n%s"
        % (target_contact, target_contact.address_book,
           target_contact.get_version(), target_contact.get_template()))

    target_temp_file_creation = helpers.file_modification_date(
        target_temp_file_name)
    while True:
        # start editor to edit contact template
        child = subprocess.Popen([config.merge_editor, source_temp_file_name,
                                  target_temp_file_name])
        child.communicate()
        if target_temp_file_creation == helpers.file_modification_date(
                target_temp_file_name):
            merged_contact = None
            os.remove(source_temp_file_name)
            os.remove(target_temp_file_name)
            break

        # load target template contents
        with open(target_temp_file_name, "r") as target_tf:
            merged_contact_template = target_tf.read()

        # try to create contact from user input
        try:
            merged_contact = \
                CarddavObject.from_existing_contact_with_new_user_input(
                    target_contact, merged_contact_template,
                    config.localize_dates())
        except ValueError as err:
            print("\n%s\n" % err)
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
                    source_contact, source_contact.address_book, merged_contact,
                    merged_contact.address_book, source_contact.print_vcard(),
                    merged_contact.print_vcard()))
        else:
            input_string = input(
                "Merge contact %s from address book %s into contact %s from "
                "address book %s\n\nKeep unchanged\n\n%s\n\nMerged:\n\n%s\n\n"
                "Are you sure? (y/n): " % (
                    source_contact, source_contact.address_book, merged_contact,
                    merged_contact.address_book, source_contact.print_vcard(),
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
        source_contact_filename = contact.filename
    if not delete_source_contact or not contact.get_uid():
        # if copy contact or contact has no uid yet
        # create a new uid
        contact.delete_vcard_object("UID")
        contact.add_uid(helpers.get_random_uid())
    # set destination file name
    contact.filename = os.path.join(target_address_book.path,
                                    "%s.vcf" % contact.get_uid())
    # save
    contact.write_to_file()
    # delete old file
    if os.path.isfile(source_contact_filename):
        os.remove(source_contact_filename)
    print("%s contact %s from address book %s to %s" % (
        "Moved" if delete_source_contact else "Copied", contact,
        contact.address_book, target_address_book))


def list_address_books(address_book_list):
    table = [["Index", "Address book"]]
    for index, address_book in enumerate(address_book_list):
        table.append([index + 1, address_book.name])
    print(helpers.pretty_print(table))


def list_contacts(vcard_list):
    selected_address_books = []
    for contact in vcard_list:
        if contact.address_book not in selected_address_books:
            selected_address_books.append(contact.address_book)
    table = []
    # table header
    if len(selected_address_books) == 1:
        print("Address book: %s" % str(selected_address_books[0]))
        table_header = ["Index", "Name", "Phone", "E-Mail"]
    else:
        print("Address books: %s" % ', '.join(
            [str(book) for book in selected_address_books]))
        table_header = ["Index", "Name", "Phone", "E-Mail", "Address book"]
    if config.has_uids():
        table_header.append("UID")
        abook_collection = AddressBookCollection(
            'short uids collection', selected_address_books,
            private_objects=config.get_supported_private_objects(),
            localize_dates=config.localize_dates(),
            skip=config.skip_unparsable())

    table.append(table_header)
    # table body
    for index, vcard in enumerate(vcard_list):
        row = []
        row.append(index + 1)
        if vcard.get_nicknames() and config.show_nicknames():
            if config.display_by_name() == "first_name":
                row.append("%s (Nickname: %s)" % (
                    vcard.get_first_name_last_name(),
                    vcard.get_nicknames()[0]))
            else:
                row.append("%s (Nickname: %s)" % (
                    vcard.get_last_name_first_name(),
                    vcard.get_nicknames()[0]))
        else:
            if config.display_by_name() == "first_name":
                row.append(vcard.get_first_name_last_name())
            else:
                row.append(vcard.get_last_name_first_name())
        if vcard.get_phone_numbers().keys():
            phone_dict = vcard.get_phone_numbers()
            # filter out preferred phone type if set in config file
            phone_keys = []
            for pref_type in config.preferred_phone_number_type():
                for phone_type in phone_dict.keys():
                    if pref_type.lower() in phone_type.lower():
                        phone_keys.append(phone_type)
                if phone_keys:
                    break
            if not phone_keys:
                phone_keys = [x for x in phone_dict.keys() if "pref" in x.lower()] \
                             or phone_dict.keys()
            # get first key in alphabetical order
            first_type = sorted(phone_keys, key=lambda k: k[0].lower())[0]
            row.append("%s: %s" % (first_type,
                                   sorted(phone_dict.get(first_type))[0]))
        else:
            row.append("")
        if vcard.get_email_addresses().keys():
            email_dict = vcard.get_email_addresses()
            # filter out preferred email type if set in config file
            email_keys = []
            for pref_type in config.preferred_email_address_type():
                for email_type in email_dict.keys():
                    if pref_type.lower() in email_type.lower():
                        email_keys.append(email_type)
                if email_keys:
                    break
            if not email_keys:
                email_keys = [x for x in email_dict.keys() if "pref" in x.lower()] \
                             or email_dict.keys()
            # get first key in alphabetical order
            first_type = sorted(email_keys, key=lambda k: k[0].lower())[0]
            row.append("%s: %s" % (first_type,
                                   sorted(email_dict.get(first_type))[0]))
        else:
            row.append("")
        if len(selected_address_books) > 1:
            row.append(vcard.address_book.name)
        if config.has_uids():
            if abook_collection.get_short_uid(vcard.get_uid()):
                row.append(abook_collection.get_short_uid(vcard.get_uid()))
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


def list_post_addresses(post_address_list):
    table = [["Name", "Type", "Post address"]]
    for row in post_address_list:
        table.append(row.split("\t"))
    print(helpers.pretty_print(table))


def list_email_addresses(email_address_list):
    table = [["Name", "Type", "E-Mail"]]
    for row in email_address_list:
        table.append(row.split("\t"))
    print(helpers.pretty_print(table))


def choose_address_book_from_list(header_string, address_book_list):
    if not address_book_list:
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
                    selected_address_book = address_book_list[addr_index - 1]
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
                    selected_vcard = vcard_list[addr_index - 1]
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
    :type address_books: list(address_book.AddressBook)
    :param search: filter contact list
    :type search: str
    :param strict_search: if True, search only in full name field
    :type strict_search: bool
    :returns: list of CarddavObject objects
    :rtype: list(CarddavObject)
    """
    return get_contacts(
        address_books, search, "name" if strict_search else "all",
        config.reverse(), config.group_by_addressbook(), config.sort)


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
    # Search for the contacts in all address books.
    contacts = []
    for address_book in address_books:
        contacts.extend(address_book.search(query, method=method))
    # Sort the contacts.
    if group:
        if sort == "first_name":
            return sorted(contacts, reverse=reverse, key=lambda x: (
                unidecode(x.address_book.name).lower(),
                unidecode(x.get_first_name_last_name()).lower()))
        elif sort == "last_name":
            return sorted(contacts, reverse=reverse, key=lambda x: (
                unidecode(x.address_book.name).lower(),
                unidecode(x.get_last_name_first_name()).lower()))
        else:
            raise ValueError('sort must be "first_name" or "last_name" not '
                             '{}.'.format(sort))
    else:
        if sort == "first_name":
            return sorted(contacts, reverse=reverse, key=lambda x:
                          unidecode(x.get_first_name_last_name()).lower())
        elif sort == "last_name":
            return sorted(contacts, reverse=reverse, key=lambda x:
                          unidecode(x.get_last_name_first_name()).lower())
        else:
            raise ValueError('sort must be "first_name" or "last_name" not '
                             '{}.'.format(sort))


def merge_args_into_config(args, config):
    """Merge the parsed arguments from argparse into the config object.

    :param args: the parsed command line arguments
    :type args: argparse.Namespace
    :param config: the parsed config file
    :type config: config.Config
    :returns: the merged config object
    :rtype: config.Config

    """
    # display by name: first or last name
    if "display" in args and args.display:
        config.set_display_by_name(args.display)
    # group by address book
    if "group_by_addressbook" in args and args.group_by_addressbook:
        config.set_group_by_addressbook(True)
    # reverse contact list
    if "reverse" in args and args.reverse:
        config.set_reverse(True)
    # sort criteria: first or last name
    if "sort" in args and args.sort:
        config.sort = args.sort
    # preferred vcard version
    if "vcard_version" in args and args.vcard_version:
        config.set_preferred_vcard_version(args.vcard_version)
    # search in source files
    if "search_in_source_files" in args and args.search_in_source_files:
        config.set_search_in_source_files(True)
    # skip unparsable vcards
    if "skip_unparsable" in args and args.skip_unparsable:
        config.set_skip_unparsable(True)
    # If the user could but did not specify address books on the command line
    # it means they want to use all address books in that place.
    if "addressbook" in args and not args.addressbook:
        args.addressbook = [abook.name for abook in config.abooks]
    if "target_addressbook" in args and not args.target_addressbook:
        args.target_addressbook = [abook.name for abook in config.abooks]


def load_address_books(names, config, search_queries):
    """Load all address books with the given names from the config.

    :param names: the address books to load
    :type names: list(str)
    :param config: the config instance to use when looking up address books
    :type config: config.Config
    :param search_queries: a mapping of address book names to search queries
    :type search_queries: dict
    :yields: the loaded address books
    :ytype: addressbook.AddressBook

    """
    all_names = {str(book) for book in config.abooks}
    if not names:
        names = all_names
    elif not all_names.issuperset(names):
        sys.exit('Error: The entered address books "{}" do not exist.\n'
                 'Possible values are: {}'.format(
                     '", "'.join(set(names) - all_names),
                     ', '.join(all_names)))
    # load address books which are defined in the configuration file
    for name in names:
        address_book = config.abook.get_abook(name)
        address_book.load(search_queries[address_book.name],
                search_in_source_files=config.search_in_source_files())
        yield address_book


def prepare_search_queries(args):
    """Prepare the search query string from the given command line args.

    Each address book can get a search query string to filter vcards befor
    loading them.  Depending on the question if the address book is used for
    source or target searches different regexes have to be combined into one
    search string.

    :param args: the parsed command line
    :type args: argparse.Namespace
    :returns: a dict mapping abook names to their loading queries, if the query
        is None it means that all cards should be loaded
    :rtype: dict(str:str or None)

    """
    # get all possible search queries for address book parsing
    source_queries = []
    target_queries = []
    if "source_search_terms" in args and args.source_search_terms:
        escaped_term = ".*".join(re.escape(x)
                                 for x in args.source_search_terms)
        source_queries.append(escaped_term)
        args.source_search_terms = escaped_term
    if "search_terms" in args and args.search_terms:
        escaped_term = ".*".join(re.escape(x) for x in args.search_terms)
        source_queries.append(escaped_term)
        args.search_terms = escaped_term
    if "target_contact" in args and args.target_contact:
        escaped_term = re.escape(args.target_contact)
        target_queries.append(escaped_term)
        args.target_contact = escaped_term
    if "uid" in args and args.uid:
        source_queries.append(args.uid)
    if "target_uid" in args and args.target_uid:
        target_queries.append(args.target_uid)
    # create and return regexp, None means that no query is given and hence all
    # contacts should be searched.
    source_queries = "^.*(%s).*$" % ')|('.join(source_queries) \
        if source_queries else None
    target_queries = "^.*(%s).*$" % ')|('.join(target_queries) \
        if target_queries else None
    logging.debug('Created source query regex: %s', source_queries)
    logging.debug('Created target query regex: %s', target_queries)
    # Get all possible search queries for address book parsing, always
    # depending on the fact if the address book is used to find source or
    # target contacts or both.
    queries = {abook.name: [] for abook in config.abook._abooks}
    for name in queries:
        if "addressbook" in args and name in args.addressbook:
            queries[name].append(source_queries)
        if "target_addressbook" in args and name in args.target_addressbook:
            queries[name].append(target_queries)
        # If None is included in the search queries of an address book it means
        # that either no source or target query was given and this address book
        # is affected by this.  All contacts should be loaded from that address
        # book.
        if None in queries[name]:
            queries[name] = None
        else:
            queries[name] = "({})".format(')|('.join(queries[name]))
    logging.debug('Created query regex: %s', queries)
    return queries


def generate_contact_list(config, args):
    """TODO: Docstring for generate_contact_list.

    :param config: the config object to use
    :type config: config.Config
    :param args: the command line arguments
    :type args: argparse.Namespace
    :returns: the contacts for further processing (TODO)
    :rtype: list(TODO)

    """
    # fill contact list
    vcard_list = []
    if "uid" in args and args.uid:
        # If an uid was given we use it to find the contact.
        logging.debug("args.uid=%s", args.uid)
        # set search terms to the empty query to prevent errors in
        # phone and email actions
        args.search_terms = ".*"
        vcard_list = get_contacts(args.addressbook, args.uid, method="uid")
        # We require that the uid given can uniquely identify a contact.
        if not vcard_list:
            sys.exit("Found no contact for {}uid {}".format(
                "source " if args.action == "merge" else "", args.uid))
        elif len(vcard_list) != 1:
            print("Found multiple contacts for {}uid {}".format(
                "source " if args.action == "merge" else "", args.uid))
            for vcard in vcard_list:
                print("    {}: {}".format(vcard, vcard.get_uid()))
            sys.exit(1)
    else:
        # No uid was given so we try to use the search terms to select a
        # contact.
        if "source_search_terms" in args:
            # exception for merge command
            if args.source_search_terms:
                args.search_terms = args.source_search_terms
            else:
                args.search_terms = ".*"
        elif "search_terms" in args:
            if args.search_terms:
                args.search_terms = args.search_terms
            else:
                args.search_terms = ".*"
        else:
            # If no search terms where given on the command line we match
            # everything with the empty search pattern.
            args.search_terms = ".*"
        logging.debug("args.search_terms=%s", args.search_terms)
        vcard_list = get_contact_list_by_user_selection(
            args.addressbook, args.search_terms,
            args.strict_search if "strict_search" in args else False)
    return vcard_list


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
                config.get_supported_private_objects(),
                config.get_preferred_vcard_version(),
                config.localize_dates())
        except ValueError as err:
            print(err)
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
    message = message_from_string(input_from_stdin_or_file, policy=SMTP_POLICY)

    print("Khard: Add email address to contact")
    if not message['From'] \
            or not message['From'].addresses:
        print("Found no email address")
        sys.exit(1)

    email_address = message['From'].addresses[0].addr_spec
    name = message['From'].addresses[0].display_name

    print("Email address: %s" % email_address)
    if not name:
        name = input("Contact's name: ")

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
            "Select address book for new contact", config.abooks)
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
            config.get_supported_private_objects(),
            config.get_preferred_vcard_version(),
            config.localize_dates())

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
            % (email_address, selected_vcard))
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
        except ValueError as err:
            print(err)
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
    # The sort function should work for strings and datetime objects.  All
    # strings will besorted before any datetime objects.
    vcard_list.sort(
        key=lambda x: (x.get_birthday().month, x.get_birthday().day)
        if isinstance(x.get_birthday(), datetime.datetime)
        else (0, 0, x.get_birthday()))
    # add to string list
    birthday_list = []
    for vcard in vcard_list:
        date = vcard.get_birthday()
        if parsable:
            if config.display_by_name() == "first_name":
                birthday_list.append("%04d.%02d.%02d\t%s"
                                     % (date.year, date.month, date.day,
                                        vcard.get_first_name_last_name()))
            else:
                birthday_list.append("%04d.%02d.%02d\t%s"
                                     % (date.year, date.month, date.day,
                                        vcard.get_last_name_first_name()))
        else:
            if config.display_by_name() == "first_name":
                birthday_list.append("%s\t%s"
                                     % (vcard.get_first_name_last_name(),
                                        vcard.get_formatted_birthday()))
            else:
                birthday_list.append("%s\t%s"
                                     % (vcard.get_last_name_first_name(),
                                        vcard.get_formatted_birthday()))
    if birthday_list:
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
    for vcard in vcard_list:
        for type, number_list in sorted(vcard.get_phone_numbers().items(),
                                        key=lambda k: k[0].lower()):
            for number in sorted(number_list):
                if config.display_by_name() == "first_name":
                    name = vcard.get_first_name_last_name()
                else:
                    name = vcard.get_last_name_first_name()
                # create output lines
                line_formatted = "\t".join([name, type, number])
                line_parsable = "\t".join([number, name, type])
                if parsable:
                    # parsable option: start with phone number
                    phone_number_line = line_parsable
                else:
                    # else: start with name
                    phone_number_line = line_formatted
                if re.search(search_terms,
                             "%s\n%s" % (line_formatted, line_parsable),
                             re.IGNORECASE | re.DOTALL):
                    matching_phone_number_list.append(phone_number_line)
                elif len(re.sub("\D", "", search_terms)) >= 3:
                    # The user likely searches for a phone number cause the
                    # search string contains at least three digits.  So we
                    # remove all non-digit chars from the phone number field
                    # and match against that.
                    if re.search(re.sub("\D", "", search_terms),
                                 re.sub("\D", "", number), re.IGNORECASE):
                        matching_phone_number_list.append(phone_number_line)
                # collect all phone numbers in a different list as fallback
                all_phone_numbers_list.append(phone_number_line)
    if matching_phone_number_list:
        if parsable:
            print('\n'.join(matching_phone_number_list))
        else:
            list_phone_numbers(matching_phone_number_list)
    elif all_phone_numbers_list:
        if parsable:
            print('\n'.join(all_phone_numbers_list))
        else:
            list_phone_numbers(all_phone_numbers_list)
    else:
        if not parsable:
            print("Found no phone numbers")
        sys.exit(1)


def post_address_subcommand(search_terms, vcard_list, parsable):
    """Print a contact table. with all postal / mailing addresses

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
    all_post_address_list = []
    matching_post_address_list = []
    for vcard in vcard_list:
        # vcard name
        if config.display_by_name() == "first_name":
            name = vcard.get_first_name_last_name()
        else:
            name = vcard.get_last_name_first_name()
        # create post address line list
        post_address_line_list = []
        if parsable:
            for type, post_address_list in sorted(vcard.get_post_addresses().items(),
                                           key=lambda k: k[0].lower()):
                for post_address in post_address_list:
                    post_address_line_list.append(
                            "\t".join([str(post_address), name, type]))
        else:
            for type, post_address_list in sorted(vcard.get_formatted_post_addresses().items(),
                                           key=lambda k: k[0].lower()):
                for post_address in sorted(post_address_list):
                    post_address_line_list.append(
                            "\t".join([name, type, post_address]))
        # add to matching and all post address lists
        for post_address_line in post_address_line_list:
            if re.search(search_terms,
                         "%s\n%s" % (post_address_line, post_address_line),
                         re.IGNORECASE | re.DOTALL):
                matching_post_address_list.append(post_address_line)
            # collect all post addresses in a different list as fallback
            all_post_address_list.append(post_address_line)
    if matching_post_address_list:
        if parsable:
            print('\n'.join(matching_post_address_list))
        else:
            list_post_addresses(matching_post_address_list)
    elif all_post_address_list:
        if parsable:
            print('\n'.join(all_post_address_list))
        else:
            list_post_addresses(all_post_address_list)
    else:
        if not parsable:
            print("Found no post adresses")
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
    for vcard in vcard_list:
        for type, email_list in sorted(vcard.get_email_addresses().items(),
                                       key=lambda k: k[0].lower()):
            for email in sorted(email_list):
                if config.display_by_name() == "first_name":
                    name = vcard.get_first_name_last_name()
                else:
                    name = vcard.get_last_name_first_name()
                # create output lines
                line_formatted = "\t".join([name, type, email])
                line_parsable = "\t".join([email, name, type])
                if parsable:
                    # parsable option: start with email address
                    email_address_line = line_parsable
                else:
                    # else: start with name
                    email_address_line = line_formatted
                if re.search(search_terms,
                             "%s\n%s" % (line_formatted, line_parsable),
                             re.IGNORECASE | re.DOTALL):
                    matching_email_address_list.append(email_address_line)
                # collect all email addresses in a different list as fallback
                all_email_address_list.append(email_address_line)
    if matching_email_address_list:
        if parsable:
            if not remove_first_line:
                # at least mutt requires that line
                print("searching for '%s' ..." % search_terms)
            print('\n'.join(matching_email_address_list))
        else:
            list_email_addresses(matching_email_address_list)
    elif all_email_address_list:
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


def list_subcommand(vcard_list, parsable):
    """Print a user friendly contacts table.

    :param vcard_list: the vcards to print
    :type vcard_list: list of carddav_object.CarddavObject
    :param parsable: machine readable output: columns devided by tabulator (\t)
    :type parsable: bool
    :returns: None
    :rtype: None

    """
    if not vcard_list:
        if not parsable:
            print("Found no contacts")
        sys.exit(1)
    elif parsable:
        contact_line_list = []
        for vcard in vcard_list:
            if config.display_by_name() == "first_name":
                name = vcard.get_first_name_last_name()
            else:
                name = vcard.get_last_name_first_name()
            contact_line_list.append('\t'.join([vcard.get_uid(), name,
                                                vcard.address_book.name]))
        print('\n'.join(contact_line_list))
    else:
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
    if selected_vcard.get_version() not in config.supported_vcard_versions:
        print("Warning:\nThe selected contact is based on vcard version %s "
              "but khard only supports the creation and modification of vcards"
              " with version 3.0 and 4.0.\nIf you proceed, the contact will be"
              " converted to vcard version %s but beware: This could corrupt "
              "the contact file or cause data loss."
              % (selected_vcard.get_version(),
                 config.get_preferred_vcard_version()))
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
                    selected_vcard, input_from_stdin_or_file,
                    config.localize_dates())
        except ValueError as err:
            print(err)
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


def remove_subcommand(selected_vcard, force):
    """Remove a contact from the addressbook.

    :param selected_vcard: the contact to delete
    :type selected_vcard: carddav_object.CarddavObject
    :param force: delete without confirmation
    :type force: bool
    :returns: None
    :rtype: None

    """
    if not force:
        while True:
            input_string = input(
                "Deleting contact %s from address book %s. Are you sure? "
                "(y/n): " % (selected_vcard, selected_vcard.address_book))
            if input_string.lower() in ["", "n", "q"]:
                print("Canceled")
                sys.exit(0)
            if input_string.lower() == "y":
                break
    selected_vcard.delete_vcard_file()
    print("Contact %s deleted successfully" % selected_vcard.get_full_name())


def source_subcommand(selected_vcard, editor):
    """Open the vcard file for a contact in an external editor.

    :param selected_vcard: the contact to edit
    :type selected_vcard: carddav_object.CarddavObject
    :param editor: the eitor command to use
    :type editor: str
    :returns: None
    :rtype: None

    """
    child = subprocess.Popen([editor, selected_vcard.filename])
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
            if not target_vcards:
                print("Found no contact for target uid %s" % target_uid)
            else:
                print("Found multiple contacts for target uid %s" % target_uid)
                for vcard in target_vcards:
                    print("    %s: %s" % (vcard, vcard.get_uid()))
            sys.exit(1)
    else:
        target_vcards = get_contact_list_by_user_selection(
            selected_address_books, search_terms, False)
    # get the source vcard, from which to merge
    source_vcard = choose_vcard_from_list("Select contact from which to merge",
                                          vcard_list)
    if source_vcard is None:
        print("Found no source contact for merging")
        sys.exit(1)
    else:
        print("Merge from %s from address book %s\n\n"
              % (source_vcard, source_vcard.address_book))
    # get the target vcard, into which to merge
    target_vcard = choose_vcard_from_list("Select contact into which to merge",
                                          target_vcards)
    if target_vcard is None:
        print("Found no target contact for merging")
        sys.exit(1)
    else:
        print("Merge into %s from address book %s\n\n"
              % (target_vcard, target_vcard.address_book))
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
              % (action.title(), source_vcard, source_vcard.address_book))

    # get target address book
    if len(target_address_book_list) == 1 \
            and target_address_book_list[0] == source_vcard.address_book:
        print("The address book %s already contains the contact %s"
              % (target_address_book_list[0], source_vcard))
        sys.exit(1)
    else:
        available_address_books = [abook for abook in target_address_book_list
                                   if abook != source_vcard.address_book]
        selected_target_address_book = choose_address_book_from_list(
            "Select target address book", available_address_books)
        if selected_target_address_book is None:
            print("Error: address book list is empty")
            sys.exit(1)

    # check if a contact already exists in the target address book
    target_vcard = choose_vcard_from_list(
        "Select target contact which to overwrite",
        get_contact_list_by_user_selection([selected_target_address_book],
                                           source_vcard.get_full_name(), True))
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
                  "  q: Quit" % (
                      target_vcard.address_book, source_vcard,
                      source_vcard.print_vcard(), target_vcard.print_vcard(),
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


def parse_args(argv):
    """Parse the command line arguments and return the namespace that was
    creates by argparse.ArgumentParser.parse_args().

    :returns: the namespace parsed from the command line
    :rtype: argparse.Namespace

    """
    # Create the base argument parser.  It will be reused for the first and
    # second round of argument parsing.
    base = argparse.ArgumentParser(
        description="Khard is a carddav address book for the console",
        formatter_class=argparse.RawTextHelpFormatter, add_help=False)
    base.add_argument("-c", "--config", default="", help="config file to use")
    base.add_argument("--debug", action="store_true",
                      help="enable debug output")
    base.add_argument("--skip-unparsable", action="store_true",
                      help="skip unparsable vcard files")
    base.add_argument("-v", "--version", action="version",
                      version="Khard version %s" % khard_version)

    # Create the first argument parser.  Its main job is to set the correct
    # config file.  The config file is needed to get the default command if no
    # subcommand is given on the command line.  This parser will ignore most
    # arguments, as they will be parsed by the second parser.
    first_parser = argparse.ArgumentParser(parents=[base])
    first_parser.add_argument('remainder', nargs=argparse.REMAINDER)

    # Create the main argument parser.  It will handle the complete command
    # line only ignoring the config and debug options as these have already
    # been set.
    parser = argparse.ArgumentParser(parents=[base])

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
        "-f", "--search-in-source-files", action="store_true",
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
        "-f", "--search-in-source-files", action="store_true",
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
    list_parser = subparsers.add_parser(
        "list",
        aliases=Actions.get_aliases("list"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list all (selected) contacts",
        help="list all (selected) contacts")
    list_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: uid\\tcontact_name\\taddress_book_name")
    subparsers.add_parser(
        "details",
        aliases=Actions.get_aliases("details"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="display detailed information about one contact",
        help="display detailed information about one contact")
    export_parser = subparsers.add_parser(
        "export",
        aliases=Actions.get_aliases("export"),
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
        aliases=Actions.get_aliases("birthdays"),
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
        aliases=Actions.get_aliases("email"),
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
        aliases=Actions.get_aliases("phone"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list phone numbers",
        help="list phone numbers")
    phone_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: number\\tname\\ttype")
    post_address_parser = subparsers.add_parser(
        "postaddress",
        aliases=Actions.get_aliases("postaddress"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list postal addresses",
        help="list postal addresses")
    post_address_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: address\\tname\\ttype")
    subparsers.add_parser(
        "source",
        aliases=Actions.get_aliases("source"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="edit the vcard file of a contact directly",
        help="edit the vcard file of a contact directly")
    new_parser = subparsers.add_parser(
        "new",
        aliases=Actions.get_aliases("new"),
        parents=[new_addressbook_parser, template_input_file_parser],
        description="create a new contact",
        help="create a new contact")
    new_parser.add_argument(
        "--vcard-version", choices=("3.0", "4.0"),
        help="Select preferred vcard version for new contact")
    add_email_parser = subparsers.add_parser(
        "add-email",
        aliases=Actions.get_aliases("add-email"),
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
        aliases=Actions.get_aliases("merge"),
        parents=[merge_addressbook_parser, merge_search_parser, sort_parser],
        description="merge two contacts",
        help="merge two contacts")
    subparsers.add_parser(
        "modify",
        aliases=Actions.get_aliases("modify"),
        parents=[default_addressbook_parser, template_input_file_parser,
                 default_search_parser, sort_parser],
        description="edit the data of a contact",
        help="edit the data of a contact")
    subparsers.add_parser(
        "copy",
        aliases=Actions.get_aliases("copy"),
        parents=[copy_move_addressbook_parser, default_search_parser,
                 sort_parser],
        description="copy a contact to a different addressbook",
        help="copy a contact to a different addressbook")
    subparsers.add_parser(
        "move",
        aliases=Actions.get_aliases("move"),
        parents=[copy_move_addressbook_parser, default_search_parser,
                 sort_parser],
        description="move a contact to a different addressbook",
        help="move a contact to a different addressbook")
    remove_parser = subparsers.add_parser(
        "remove",
        aliases=Actions.get_aliases("remove"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="remove a contact",
        help="remove a contact")
    remove_parser.add_argument(
        "--force", action="store_true",
        help="Remove contact without confirmation")
    subparsers.add_parser(
        "addressbooks",
        aliases=Actions.get_aliases("addressbooks"),
        description="list addressbooks",
        help="list addressbooks")
    subparsers.add_parser(
        "filename",
        aliases=Actions.get_aliases("filename"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list filenames of all matching contacts",
        help="list filenames of all matching contacts")

    # Replace the print_help method of the first parser with the print_help
    # method of the main parser.  This makes it possible to have the first
    # parser handle the help option so that command line help can be printed
    # without parsing the config file first (which is a problem if there are
    # errors in the config file).  The config file will still be parsed before
    # the full command line is parsed so errors in the config file might be
    # reported before command line syntax errors.
    first_parser.print_help = parser.print_help

    # Parese the command line with the first argument parser.  It will handle
    # the config option (its main job) and also the help, version and debug
    # options as these do not depend on anything else.
    args = first_parser.parse_args(argv)
    remainder = args.remainder

    # Set the loglevel to debug if given on the command line.  This is done
    # before parsing the config file to make it possible to debug the parsing
    # of the config file.
    if "debug" in args and args.debug:
        logging.basicConfig(level=logging.DEBUG)

    # Create the global config instance.
    global config
    config = Config(args.config)

    # Check the log level again and merge the value from the command line with
    # the config file.
    if ("debug" in args and args.debug) or config.debug:
        logging.basicConfig(level=logging.DEBUG)
    logging.debug("first args=%s", args)
    logging.debug("remainder=%s", remainder)

    # Set the default command from the config file if none was given on the
    # command line.
    if not remainder or remainder[0] not in Actions.get_all():
        remainder.insert(0, config.default_action)
        logging.debug("updated remainder=%s", remainder)

    # Save the last option that needs to be carried from the first parser run
    # to the second.
    skip = args.skip_unparsable

    # Parse the remainder of the command line.  All options from the previous
    # run have already been processed and are not needed any more.
    args = parser.parse_args(remainder)

    # Restore settings that are left from the first parser run.
    args.skip_unparsable = skip
    logging.debug("second args=%s", args)

    # An integrity check for some options.
    if "uid" in args and args.uid and (
            ("search_terms" in args and args.search_terms) or
            ("source_search_terms" in args and args.source_search_terms)):
        # If an uid was given we require that no search terms where given.
        parser.error("You can not give arbitrary search terms and --uid at the"
                     " same time.")
    return args


def main(argv=sys.argv[1:]):
    args = parse_args(argv)

    # if args.action isn't one of the defined actions, it must be an alias
    if args.action not in Actions.get_actions():
        # convert alias to corresponding action
        # example: "ls" --> "list"
        args.action = Actions.get_action(args.action)

    # Check some of the simpler subcommands first.  These don't have any
    # options and can directly be run.  That is much faster than checking all
    # options first and getting default values.
    if args.action == "addressbooks":
        print('\n'.join(str(book) for book in config.abooks))
        return

    merge_args_into_config(args, config)
    search_queries = prepare_search_queries(args)

    # load address books
    if "addressbook" in args:
        args.addressbook = list(load_address_books(args.addressbook, config,
                                                   search_queries))
    if "target_addressbook" in args:
        args.target_addressbook = list(load_address_books(
            args.target_addressbook, config, search_queries))

    vcard_list = generate_contact_list(config, args)

    if args.action == "filename":
        print('\n'.join(contact.filename for contact in vcard_list))
        return

    # read from template file or stdin if available
    input_from_stdin_or_file = ""
    if "input_file" in args:
        if args.input_file != "-":
            # try to read from specified input file
            try:
                with open(args.input_file, "r") as f:
                    input_from_stdin_or_file = f.read()
            except IOError as err:
                print("Error: %s\n       File: %s" % (err.strerror,
                                                      err.filename))
                sys.exit(1)
        elif not sys.stdin.isatty():
            # try to read from stdin
            try:
                input_from_stdin_or_file = sys.stdin.read()
            except IOError:
                print("Error: Can't read from stdin")
                sys.exit(1)
            # try to reopen console
            # otherwise further user interaction is not possible (for example
            # selecting a contact from the contact table)
            try:
                sys.stdin = open('/dev/tty')
            except IOError:
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
    elif args.action == "postaddress":
        post_address_subcommand(args.search_terms, vcard_list, args.parsable)
    elif args.action == "email":
        email_subcommand(args.search_terms, vcard_list,
                         args.parsable, args.remove_first_line)
    elif args.action == "list":
        list_subcommand(vcard_list, args.parsable)
    elif args.action == "export" and "empty_contact_template" in args \
            and args.empty_contact_template:
        # export empty template must work without selecting a contact first
        args.output_file.write(
            "# Contact template for khard version %s\n#\n"
            "# Use this yaml formatted template to create a new contact:\n"
            "#   either with: khard new -a address_book -i template.yaml\n"
            "#   or with: cat template.yaml | khard new -a address_book\n"
            "\n%s" % (khard_version, helpers.get_new_contact_template(
                config.get_supported_private_objects())))
    elif args.action in ["details", "modify", "remove", "source", "export"]:
        selected_vcard = choose_vcard_from_list(
            "Select contact for %s action" % args.action.title(), vcard_list)
        if selected_vcard is None:
            print("Found no contact")
            sys.exit(1)
        if args.action == "details":
            print(selected_vcard.print_vcard())
        elif args.action == "export":
            args.output_file.write(
                "# Contact template for khard version %s\n"
                "# Name: %s\n# Vcard version: %s\n\n%s"
                % (khard_version, selected_vcard, selected_vcard.get_version(),
                   selected_vcard.get_template()))
        elif args.action == "modify":
            modify_subcommand(selected_vcard, input_from_stdin_or_file,
                              args.open_editor)
        elif args.action == "remove":
            remove_subcommand(selected_vcard, args.force)
        elif args.action == "source":
            source_subcommand(selected_vcard, config.editor)
    elif args.action == "merge":
        merge_subcommand(vcard_list, args.target_addressbook,
                         args.target_contact, args.target_uid)
    elif args.action in ["copy", "move"]:
        copy_or_move_subcommand(
            args.action, vcard_list, args.target_addressbook)
