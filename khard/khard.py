"""Main application logic of khard includeing command line handling"""

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
from .address_book import AddressBookCollection, AddressBookParseError, \
    AddressBookNameError
from .carddav_object import CarddavObject
from . import cli
from .version import version as khard_version


config = None


def write_temp_file(text=""):
    """Create a new temporary file and write some initial text to it.

    :param text: the text to write to the temp file
    :type text: str
    :returns: the file name of the newly created temp file
    :rtype: str

    """
    with NamedTemporaryFile(mode='w+t', suffix='.yml', delete=False) as tmp:
        tmp.write(text)
        return tmp.name


def edit(*filenames, merge=False):
    """Edit the given files with the configured editor or merge editor"""
    editor = config.merge_editor if merge else config.editor
    editor = [editor] if isinstance(editor, str) else editor
    editor.extend(filenames)
    child = subprocess.Popen(editor)
    child.communicate()


def create_new_contact(address_book):
    # create temp file
    template = "# create new contact\n# Address book: {}\n# Vcard version: " \
        "{}\n# if you want to cancel, exit without saving\n\n{}".format(
            address_book, config.preferred_vcard_version,
            helpers.get_new_contact_template(config.private_objects))
    temp_file_name = write_temp_file(template)
    temp_file_creation = helpers.file_modification_date(temp_file_name)

    while True:
        edit(temp_file_name)
        if temp_file_creation == helpers.file_modification_date(
                temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        with open(temp_file_name, "r") as tmp:
            new_contact_yaml = tmp.read()

        # try to create new contact
        try:
            new_contact = CarddavObject.from_yaml(
                address_book, new_contact_yaml, config.private_objects,
                config.preferred_vcard_version, config.localize_dates)
        except ValueError as err:
            print("\n{}\n".format(err))
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
        print("Creation successful\n\n{}".format(new_contact.print_vcard()))


def modify_existing_contact(old_contact):
    # create temp file and open it with the specified text editor
    temp_file_name = write_temp_file(
        "# Edit contact: {}\n# Address book: {}\n# Vcard version: {}\n"
        "# if you want to cancel, exit without saving\n\n{}".format(
            old_contact, old_contact.address_book, old_contact.version,
            old_contact.get_template()))

    temp_file_creation = helpers.file_modification_date(temp_file_name)

    while True:
        edit(temp_file_name)
        if temp_file_creation == helpers.file_modification_date(
                temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        with open(temp_file_name, "r") as tmp:
            new_contact_template = tmp.read()

        # try to create contact from user input
        try:
            new_contact = CarddavObject.clone_with_yaml_update(
                old_contact, new_contact_template, config.localize_dates)
        except ValueError as err:
            print("\n{}\n".format(err))
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
        print("Nothing changed\n\n{}".format(old_contact.print_vcard()))
    else:
        new_contact.write_to_file(overwrite=True)
        print("Modification successful\n\n{}".format(
            new_contact.print_vcard()))


def merge_existing_contacts(source_contact, target_contact,
                            delete_source_contact):
    # show warning, if target vcard version is not 3.0 or 4.0
    if target_contact.version not in config.supported_vcard_versions:
        print("Warning:\nThe target contact in which to merge is based on "
              "vcard version {} but khard only supports the modification of "
              "vcards with version 3.0 and 4.0.\nIf you proceed, the contact "
              "will be converted to vcard version {} but beware: This could "
              "corrupt the contact file or cause data loss.".format(
                  target_contact.version, config.preferred_vcard_version))
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
        "# merge from {}\n# Address book: {}\n# Vcard version: {}\n"
        "# if you want to cancel, exit without saving\n\n{}".format(
            source_contact, source_contact.address_book,
            source_contact.version, source_contact.get_template()))
    # target vcard
    target_temp_file_name = write_temp_file(
        "# merge into {}\n# Address book: {}\n# Vcard version: {}\n"
        "# if you want to cancel, exit without saving\n\n{}".format(
            target_contact, target_contact.address_book,
            target_contact.version, target_contact.get_template()))

    target_temp_file_creation = helpers.file_modification_date(
        target_temp_file_name)
    while True:
        edit(source_temp_file_name, target_temp_file_name, merge=True)
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
            merged_contact = CarddavObject.clone_with_yaml_update(
                target_contact, merged_contact_template, config.localize_dates)
        except ValueError as err:
            print("\n{}\n".format(err))
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
        print("Target contact unmodified\n\n{}".format(
            target_contact.print_vcard()))
        sys.exit(0)

    print("Merge contact {} from address book {} into contact {} from address "
          "book {}\n\n".format(source_contact, source_contact.address_book,
                               merged_contact, merged_contact.address_book))
    if delete_source_contact:
        print("To be removed")
    else:
        print("Keep unchanged")
    print("\n\n{}\n\nMerged\n\n{}\n".format(source_contact.print_vcard(),
                                            merged_contact.print_vcard()))
    while True:
        input_string = input("Are you sure? (y/n): ")
        if input_string.lower() in ["", "n", "q"]:
            print("Canceled")
            return
        if input_string.lower() == "y":
            break

    # save merged_contact to disk and delete source contact
    merged_contact.write_to_file(overwrite=True)
    if delete_source_contact:
        source_contact.delete_vcard_file()
    print("Merge successful\n\n{}".format(merged_contact.print_vcard()))


def copy_contact(contact, target_address_book, delete_source_contact):
    source_contact_filename = ""
    if delete_source_contact:
        # if source file should be moved, get its file location to delete after
        # successful movement
        source_contact_filename = contact.filename
    if not delete_source_contact or not contact.uid:
        # if copy contact or contact has no uid yet
        # create a new uid
        contact.uid = helpers.get_random_uid()
    # set destination file name
    contact.filename = os.path.join(target_address_book.path,
                                    "{}.vcf".format(contact.uid))
    # save
    contact.write_to_file()
    # delete old file
    if os.path.isfile(source_contact_filename):
        os.remove(source_contact_filename)
    print("{} contact {} from address book {} to {}".format(
        "Moved" if delete_source_contact else "Copied", contact,
        contact.address_book, target_address_book))


def list_address_books(address_books):
    table = [["Index", "Address book"]]
    for index, address_book in enumerate(address_books):
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
        print("Address book: {}".format(selected_address_books[0]))
        table_header = ["Index", "Name", "Phone", "E-Mail"]
    else:
        print("Address books: {}".format(', '.join(
            [str(book) for book in selected_address_books])))
        table_header = ["Index", "Name", "Phone", "E-Mail", "Address book"]
    if config.show_uids:
        table_header.append("UID")
        abook_collection = AddressBookCollection('short uids collection',
                                                 selected_address_books)

    table.append(table_header)
    # table body
    for index, vcard in enumerate(vcard_list):
        row = []
        row.append(index + 1)
        if vcard.nicknames and config.show_nicknames:
            if config.display == "first_name":
                row.append("{} (Nickname: {})".format(
                    vcard.get_first_name_last_name(), vcard.nicknames[0]))
            elif config.display == "formatted_name":
                row.append("{} (Nickname: {})".format(vcard.formatted_name,
                                                      vcard.nicknames[0]))
            else:
                row.append("{} (Nickname: {})".format(
                    vcard.get_last_name_first_name(), vcard.nicknames[0]))
        else:
            if config.display == "first_name":
                row.append(vcard.get_first_name_last_name())
            elif config.display == "formatted_name":
                row.append(vcard.formatted_name)
            else:
                row.append(vcard.get_last_name_first_name())
        if vcard.phone_numbers:
            phone_dict = vcard.phone_numbers
            # filter out preferred phone type if set in config file
            phone_keys = []
            for pref_type in config.preferred_phone_number_type:
                for phone_type in phone_dict:
                    if pref_type.lower() in phone_type.lower():
                        phone_keys.append(phone_type)
                if phone_keys:
                    break
            if not phone_keys:
                phone_keys = [x for x in phone_dict if "pref" in x.lower()] \
                             or phone_dict.keys()
            # get first key in alphabetical order
            first_type = sorted(phone_keys, key=lambda k: k[0].lower())[0]
            row.append("{}: {}".format(first_type,
                                       sorted(phone_dict.get(first_type))[0]))
        else:
            row.append("")
        if vcard.emails:
            email_dict = vcard.emails
            # filter out preferred email type if set in config file
            email_keys = []
            for pref_type in config.preferred_email_address_type:
                for email_type in email_dict:
                    if pref_type.lower() in email_type.lower():
                        email_keys.append(email_type)
                if email_keys:
                    break
            if not email_keys:
                email_keys = [x for x in email_dict if "pref" in x.lower()] \
                             or email_dict.keys()
            # get first key in alphabetical order
            first_type = sorted(email_keys, key=lambda k: k[0].lower())[0]
            row.append("{}: {}".format(first_type,
                                       sorted(email_dict.get(first_type))[0]))
        else:
            row.append("")
        if len(selected_address_books) > 1:
            row.append(vcard.address_book.name)
        if config.show_uids:
            if abook_collection.get_short_uid(vcard.uid):
                row.append(abook_collection.get_short_uid(vcard.uid))
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


def choose_address_book_from_list(header_string, address_books):
    if not address_books:
        return None
    if len(address_books) == 1:
        return address_books[0]
    print(header_string)
    list_address_books(address_books)
    while True:
        try:
            input_string = input("Enter Index: ")
            if input_string in ["", "q", "Q"]:
                print("Canceled")
                sys.exit(0)
            addr_index = int(input_string)
            if addr_index > 0:
                # make sure the address book is loaded afterwards
                selected_address_book = address_books[addr_index - 1]
            else:
                raise ValueError
        except (EOFError, IndexError, ValueError):
            print("Please enter an index value between 1 and %d or nothing"
                  " to exit." % len(address_books))
        else:
            break
    print("")
    return selected_address_book


def choose_vcard_from_list(header_string, vcard_list, include_none=False):
    if not vcard_list:
        return None
    if len(vcard_list) == 1 and not include_none:
        return vcard_list[0]
    print(header_string)
    list_contacts(vcard_list)
    while True:
        try:
            prompt_string = "Enter Index ({}q to quit): ".format(
                "0 for None, " if include_none else "")
            input_string = input(prompt_string)
            if input_string in ["", "q", "Q"]:
                print("Canceled")
                sys.exit(0)
            addr_index = int(input_string)
            if addr_index == 0 and include_none:
                return None
            if addr_index > 0:
                selected_vcard = vcard_list[addr_index - 1]
            else:
                raise ValueError
        except (EOFError, IndexError, ValueError):
            print("Please enter an index value between 1 and {} or nothing"
                  " to exit.".format(len(vcard_list)))
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
    return get_contacts(address_books, search,
                        "name" if strict_search else "all", config.reverse,
                        config.group_by_addressbook, config.sort)


def get_contacts(address_books, query, method="all", reverse=False,
                 group=False, sort="first_name"):
    """Get a list of contacts from one or more address books.

    :param address_books: the address books to search
    :type address_books: list(address_book.AddressBook)
    :param str query: a search query to select contacts
    :param str method: the search method, one of "all", "name" or "uid"
    :param bool reverse: reverse the order of the returned contacts
    :param bool group: group results by address book
    :param str sort: the field to use for sorting, one of "first_name",
        "last_name", "formatted_name"
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
        if sort == "last_name":
            return sorted(contacts, reverse=reverse, key=lambda x: (
                unidecode(x.address_book.name).lower(),
                unidecode(x.get_last_name_first_name()).lower()))
        if sort == "formatted_name":
            return sorted(contacts, reverse=reverse, key=lambda x: (
                unidecode(x.address_book.name).lower(),
                unidecode(x.formatted_name.lower())))
    else:
        if sort == "first_name":
            return sorted(contacts, reverse=reverse, key=lambda x:
                          unidecode(x.get_first_name_last_name()).lower())
        if sort == "last_name":
            return sorted(contacts, reverse=reverse, key=lambda x:
                          unidecode(x.get_last_name_first_name()).lower())
        if sort == "formatted_name":
            return sorted(contacts, reverse=reverse, key=lambda x:
                          unidecode(x.formatted_name.lower()))
    raise ValueError('sort must be "first_name", "last_name" or '
                     '"formatted_name" not {}.'.format(sort))


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
    source_queries = "^.*({}).*$".format(')|('.join(source_queries)) \
        if source_queries else None
    target_queries = "^.*({}).*$".format(')|('.join(target_queries)) \
        if target_queries else None
    logging.debug('Created source query regex: %s', source_queries)
    logging.debug('Created target query regex: %s', target_queries)
    # Get all possible search queries for address book parsing, always
    # depending on the fact if the address book is used to find source or
    # target contacts or both.
    queries = {abook.name: [] for abook in config.abooks}
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


def generate_contact_list(args):
    """TODO: Docstring for generate_contact_list.

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
                print("    {}: {}".format(vcard, vcard.uid))
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
        sys.exit("Error: address book list is empty")
    # if there is some data in stdin
    if input_from_stdin_or_file:
        # create new contact from stdin
        try:
            new_contact = CarddavObject.from_yaml(
                selected_address_book, input_from_stdin_or_file,
                config.private_objects, config.preferred_vcard_version,
                config.localize_dates)
        except ValueError as err:
            sys.exit(err)
        else:
            new_contact.write_to_file()
        if open_editor:
            modify_existing_contact(new_contact)
        else:
            print("Creation successful\n\n{}".format(
                new_contact.print_vcard()))
    else:
        create_new_contact(selected_address_book)


def add_email_subcommand(text, abooks):
    """Add a new email address to contacts, creating new contacts if necessary.

    :param str text: the input text to search for the new email
    :param abooks: the addressbooks that were selected on the command line
    :type abooks: list of address_book.AddressBook
    :returns: None
    :rtype: None

    """
    # get name and email address
    message = message_from_string(text, policy=SMTP_POLICY)

    print("Khard: Add email address to contact")
    if not message['From'] or not message['From'].addresses:
        sys.exit("Found no email address")

    email_address = message['From'].addresses[0].addr_spec
    name = message['From'].addresses[0].display_name

    print("Email address: {}".format(email_address))
    if not name:
        name = input("Contact's name: ")

    # search for an existing contact
    selected_vcard = choose_vcard_from_list(
        "Select contact for the found e-mail address",
        get_contact_list_by_user_selection(abooks, name, True))
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
            sys.exit("Error: address book list is empty")
        # ask for name and organisation of new contact
        while True:
            first_name = input("First name: ")
            last_name = input("Last name: ")
            organisation = input("Organisation: ")
            if not first_name and not last_name and not organisation:
                print("Error: All fields are empty.")
            else:
                break
        selected_vcard = CarddavObject.from_yaml(
            selected_address_book,
            "First name : {}\nLast name : {}\nOrganisation : {}".format(
                first_name, last_name, organisation),
            config.private_objects, config.preferred_vcard_version,
            config.localize_dates)

    # check if the contact already contains the email address
    for _, email_list in sorted(selected_vcard.emails.items(),
                                key=lambda k: k[0].lower()):
        for email in email_list:
            if email == email_address:
                print("The contact {} already contains the email address {}"
                      .format(selected_vcard, email_address))
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
    print("\nAdding email address {} to contact {}\n"
          "Enter email label\n"
          "    vcard 3.0: At least one of home, internet, pref, work, x400\n"
          "    vcard 4.0: At least one of home, internet, pref, work\n"
          "    Or a custom label (only letters)".format(email_address,
                                                        selected_vcard))
    while True:
        label = input("email label [internet]: ") or "internet"
        try:
            selected_vcard.add_email(label, email_address)
        except ValueError as err:
            print(err)
        else:
            break
    # save to disk
    selected_vcard.write_to_file(overwrite=True)
    print("Done.\n\n{}".format(selected_vcard.print_vcard()))


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
        vcard for vcard in vcard_list if vcard.birthday is not None]
    # sort by date (month and day)
    # The sort function should work for strings and datetime objects.  All
    # strings will besorted before any datetime objects.
    vcard_list.sort(key=lambda x: (x.birthday.month, x.birthday.day)
                    if isinstance(x.birthday, datetime.datetime)
                    else (0, 0, x.birthday))
    # add to string list
    birthday_list = []
    for vcard in vcard_list:
        date = vcard.birthday
        if parsable:
            date = date.strftime("%Y.%m.%d")
            if config.display == "first_name":
                birthday_list.append("{}\t{}".format(
                    date, vcard.get_first_name_last_name()))
            elif config.display == "formatted_name":
                birthday_list.append("{}\t{}".format(date,
                                                     vcard.formatted_name))
            else:
                birthday_list.append("{}\t{}".format(
                    date, vcard.get_last_name_first_name()))
        else:
            date = vcard.get_formatted_birthday()
            if config.display == "first_name":
                birthday_list.append("{}\t{}".format(
                    vcard.get_first_name_last_name(), date))
            elif config.display == "formatted_name":
                birthday_list.append("{}\t{}".format(vcard.formatted_name,
                                                     date))
            else:
                birthday_list.append("{}\t{}".format(
                    vcard.get_last_name_first_name(), date))
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
        for type, number_list in sorted(vcard.phone_numbers.items(),
                                        key=lambda k: k[0].lower()):
            for number in sorted(number_list):
                if config.display == "first_name":
                    name = vcard.get_first_name_last_name()
                elif config.display == "last_name":
                    name = vcard.get_last_name_first_name()
                else:
                    name = vcard.formatted_name
                # create output lines
                line_formatted = "\t".join([name, type, number])
                line_parsable = "\t".join([number, name, type])
                if parsable:
                    # parsable option: start with phone number
                    phone_number_line = line_parsable
                else:
                    # else: start with name
                    phone_number_line = line_formatted
                if re.search(search_terms, "{}\n{}".format(line_formatted,
                                                           line_parsable),
                             re.IGNORECASE | re.DOTALL):
                    matching_phone_number_list.append(phone_number_line)
                elif len(re.sub(r"\D", "", search_terms)) >= 3:
                    # The user likely searches for a phone number cause the
                    # search string contains at least three digits.  So we
                    # remove all non-digit chars from the phone number field
                    # and match against that.
                    if re.search(re.sub(r"\D", "", search_terms),
                                 re.sub(r"\D", "", number), re.IGNORECASE):
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
        if config.display == "first_name":
            name = vcard.get_first_name_last_name()
        elif config.display == "last_name":
            name = vcard.get_last_name_first_name()
        else:
            name = vcard.formatted_name
        # create post address line list
        post_address_line_list = []
        if parsable:
            for type, post_address_list in sorted(
                    vcard.get_post_addresses().items(),
                    key=lambda k: k[0].lower()):
                for post_address in post_address_list:
                    post_address_line_list.append(
                        "\t".join([str(post_address), name, type]))
        else:
            for type, post_address_list in sorted(
                    vcard.get_formatted_post_addresses().items(),
                    key=lambda k: k[0].lower()):
                for post_address in sorted(post_address_list):
                    post_address_line_list.append(
                        "\t".join([name, type, post_address]))
        # add to matching and all post address lists
        for post_address_line in post_address_line_list:
            if re.search(search_terms, "{}\n{}".format(post_address_line,
                                                       post_address_line),
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

    .. code-block:: text

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
        for type, email_list in sorted(vcard.emails.items(),
                                       key=lambda k: k[0].lower()):
            for email in sorted(email_list):
                if config.display == "first_name":
                    name = vcard.get_first_name_last_name()
                elif config.display == "last_name":
                    name = vcard.get_last_name_first_name()
                else:
                    name = vcard.formatted_name
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
                             "{}\n{}".format(line_formatted, line_parsable),
                             re.IGNORECASE | re.DOTALL):
                    matching_email_address_list.append(email_address_line)
                # collect all email addresses in a different list as fallback
                all_email_address_list.append(email_address_line)
    if matching_email_address_list:
        if parsable:
            if not remove_first_line:
                # at least mutt requires that line
                print("searching for '{}' ...".format(search_terms))
            print('\n'.join(matching_email_address_list))
        else:
            list_email_addresses(matching_email_address_list)
    elif all_email_address_list:
        if parsable:
            if not remove_first_line:
                # at least mutt requires that line
                print("searching for '{}' ...".format(search_terms))
            print('\n'.join(all_email_address_list))
        else:
            list_email_addresses(all_email_address_list)
    else:
        if not parsable:
            print("Found no email addresses")
        elif not remove_first_line:
            print("searching for '{}' ...".format(search_terms))
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
            if config.display == "first_name":
                name = vcard.get_first_name_last_name()
            elif config.display == "last_name":
                name = vcard.get_last_name_first_name()
            else:
                name = vcard.formatted_name
            contact_line_list.append('\t'.join([vcard.uid, name,
                                                vcard.address_book.name]))
        print('\n'.join(contact_line_list))
    else:
        list_contacts(vcard_list)


def modify_subcommand(selected_vcard, input_from_stdin_or_file, open_editor,
                      source=False):
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
    :param source: edit the source file or a yaml version?
    :type source: bool
    :returns: None
    :rtype: None

    """
    if source:
        edit(selected_vcard.filename)
        return
    # show warning, if vcard version of selected contact is not 3.0 or 4.0
    if selected_vcard.version not in config.supported_vcard_versions:
        print("Warning:\nThe selected contact is based on vcard version {} "
              "but khard only supports the creation and modification of vcards"
              " with version 3.0 and 4.0.\nIf you proceed, the contact will be"
              " converted to vcard version {} but beware: This could corrupt "
              "the contact file or cause data loss.".format(
                  selected_vcard.version, config.preferred_vcard_version))
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
            new_contact = CarddavObject.clone_with_yaml_update(
                selected_vcard, input_from_stdin_or_file,
                config.localize_dates)
        except ValueError as err:
            sys.exit(err)
        if selected_vcard == new_contact:
            print("Nothing changed\n\n{}".format(new_contact.print_vcard()))
        else:
            print("Modification\n\n{}\n".format(new_contact.print_vcard()))
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
    print("Contact {} deleted successfully".format(
        selected_vcard.formatted_name))


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
        sys.exit("You can not specify a target uid and target search terms "
                 "for a merge.")
    # Find possible target contacts.
    if target_uid != "":
        target_vcards = get_contacts(selected_address_books, target_uid,
                                     method="uid")
        # We require that the uid given can uniquely identify a contact.
        if len(target_vcards) != 1:
            if not target_vcards:
                print("Found no contact for target uid {}".format(target_uid))
            else:
                print("Found multiple contacts for target uid {}".format(
                    target_uid))
                for vcard in target_vcards:
                    print("    {}: {}".format(vcard, vcard.uid))
            sys.exit(1)
    else:
        target_vcards = get_contact_list_by_user_selection(
            selected_address_books, search_terms, False)
    # get the source vcard, from which to merge
    source_vcard = choose_vcard_from_list("Select contact from which to merge",
                                          vcard_list)
    if source_vcard is None:
        sys.exit("Found no source contact for merging")
    else:
        print("Merge from {} from address book {}\n\n".format(
            source_vcard, source_vcard.address_book))
    # get the target vcard, into which to merge
    target_vcard = choose_vcard_from_list("Select contact into which to merge",
                                          target_vcards)
    if target_vcard is None:
        sys.exit("Found no target contact for merging")
    else:
        print("Merge into {} from address book {}\n\n".format(
            target_vcard, target_vcard.address_book))
    # merging
    if source_vcard == target_vcard:
        print("The selected contacts are already identical")
    else:
        merge_existing_contacts(source_vcard, target_vcard, True)


def copy_or_move_subcommand(action, vcard_list, target_address_books):
    """Copy or move a contact to a different address book.

    :param str action: the string "copy" or "move" to indicate what to do
    :param vcard_list: the contact list from which to select one for the action
    :type vcard_list: list of carddav_object.CarddavObject
    :param target_address_books: the target address books
    :type target_address_books: addressbook.AddressBookCollection
    :returns: None
    :rtype: None
    """
    # get the source vcard, which to copy or move
    source_vcard = choose_vcard_from_list(
        "Select contact to {}".format(action.title()), vcard_list)
    if source_vcard is None:
        sys.exit("Found no contact")
    else:
        print("{} contact {} from address book {}".format(
            action.title(), source_vcard, source_vcard.address_book))

    # get target address book
    if len(target_address_books) == 1 \
            and target_address_books[0] == source_vcard.address_book:
        sys.exit("The address book {} already contains the contact {}".format(
            target_address_books[0], source_vcard))
    else:
        available_address_books = [abook for abook in target_address_books
                                   if abook != source_vcard.address_book]
        selected_target_address_book = choose_address_book_from_list(
            "Select target address book", available_address_books)
        if selected_target_address_book is None:
            sys.exit("Error: address book list is empty")

    # check if a contact already exists in the target address book
    target_vcard = choose_vcard_from_list(
        "Select target contact to overwrite (or None to add a new entry)",
        get_contact_list_by_user_selection([selected_target_address_book],
                                           source_vcard.formatted_name, True),
        True)
    # If the target contact doesn't exist, move or copy the source contact into
    # the target address book without further questions.
    if target_vcard is None:
        copy_contact(source_vcard, selected_target_address_book,
                     action == "move")
    elif source_vcard == target_vcard:
        # source and target contact are identical
        print("Target contact: {}".format(target_vcard))
        if action == "move":
            copy_contact(source_vcard, selected_target_address_book, True)
        else:
            print("The selected contacts are already identical")
    else:
        # source and target contacts are different
        # either overwrite the target one or merge into target contact
        print("The address book {} already contains the contact {}\n\n"
              "Source\n\n{}\n\nTarget\n\n{}\n\nPossible actions:\n"
              "  a: {} anyway\n"
              "  m: Merge from source into target contact\n"
              "  o: Overwrite target contact\n"
              "  q: Quit".format(target_vcard.address_book, source_vcard,
                                 source_vcard.print_vcard(),
                                 target_vcard.print_vcard(), action.title()))
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


def main(argv=sys.argv[1:]):
    args, conf = cli.init(argv)

    # store the config instance in the module level variable
    global config
    config = conf

    # Check some of the simpler subcommands first.  These don't have any
    # options and can directly be run.
    if args.action == "addressbooks":
        print('\n'.join(str(book) for book in config.abooks))
        return
    if args.action == "template":
        print("# Contact template for khard version {}\n#\n"
              "# Use this yaml formatted template to create a new contact:\n"
              "#   either with: khard new -a address_book -i template.yaml\n"
              "#   or with: cat template.yaml | khard new -a address_book\n"
              "\n{}".format(khard_version, helpers.get_new_contact_template(
                  config.private_objects)))
        return

    search_queries = prepare_search_queries(args)

    # load address books
    try:
        if "addressbook" in args:
            args.addressbook = config.get_address_books(args.addressbook,
                                                        search_queries)
        if "target_addressbook" in args:
            args.target_addressbook = config.get_address_books(
                args.target_addressbook, search_queries)
    except AddressBookParseError as err:
        sys.exit("{}\nUse --debug for more information or --skip-unparsable "
                 "to proceed".format(err))
    except AddressBookNameError as err:
        sys.exit(err)

    vcard_list = generate_contact_list(args)

    if args.action == "filename":
        print('\n'.join(contact.filename for contact in vcard_list))
        return

    # read from template file or stdin if available
    input_from_stdin_or_file = ""
    if "input_file" in args:
        if args.input_file != "-":
            # try to read from specified input file
            try:
                with open(args.input_file, "r") as infile:
                    input_from_stdin_or_file = infile.read()
            except IOError as err:
                sys.exit("Error: {}\n       File: {}".format(err.strerror,
                                                             err.filename))
        elif not sys.stdin.isatty():
            # try to read from stdin
            try:
                input_from_stdin_or_file = sys.stdin.read()
            except IOError:
                sys.exit("Error: Can't read from stdin")
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
    elif args.action in ["show", "edit", "remove"]:
        selected_vcard = choose_vcard_from_list(
            "Select contact for {} action".format(args.action.title()),
            vcard_list)
        if selected_vcard is None:
            sys.exit("Found no contact")
        if args.action == "show":
            if args.format == "pretty":
                output = selected_vcard.print_vcard()
            elif args.format == "vcard":
                output = open(selected_vcard.filename).read()
            else:
                output = "# Contact template for khard version {}\n" \
                         "# Name: {}\n# Vcard version: {}\n\n{}".format(
                             khard_version, selected_vcard,
                             selected_vcard.version,
                             selected_vcard.get_template())
            args.output_file.write(output)
        elif args.action == "edit":
            modify_subcommand(selected_vcard, input_from_stdin_or_file,
                              args.open_editor, args.format == 'vcard')
        elif args.action == "remove":
            remove_subcommand(selected_vcard, args.force)
    elif args.action == "merge":
        merge_subcommand(vcard_list, args.target_addressbook,
                         args.target_contact, args.target_uid)
    elif args.action in ["copy", "move"]:
        copy_or_move_subcommand(
            args.action, vcard_list, args.target_addressbook)
