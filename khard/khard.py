"""Main application logic of khard includeing command line handling"""

from argparse import Namespace
import datetime
from email import message_from_string
from email.policy import SMTP as SMTP_POLICY
from email.headerregistry import Address, AddressHeader, Group
import logging
import operator
import os
import subprocess
import sys
from tempfile import NamedTemporaryFile
from typing import cast, Dict, Iterable, List, Optional, TypeVar, Union

from unidecode import unidecode

from . import helpers
from .address_book import (AddressBookCollection, AddressBookNameError,
                           AddressBookParseError, VdirAddressBook)
from .carddav_object import CarddavObject
from . import cli
from .config import Config
from .formatter import Formatter
from .query import AndQuery, AnyQuery, NameQuery, OrQuery, Query, TermQuery
from .version import version as khard_version


logger = logging.getLogger(__name__)
config: Config
T = TypeVar("T")


def confirm(message: str) -> bool:
    """Ask the user for confirmation on the terminal.

    :param message: the question to print
    :returns: the answer of the user
    """
    while True:
        answer = input(message + ' (y/N) ')
        answer = answer.lower()
        if answer == 'y':
            return True
        if answer in ['', 'n', 'q']:
            return False
        print('Please answer with "y" for yes or "n" for no.')


def select(items: List[T], include_none: bool = False) -> Optional[T]:
    """Ask the user to select an item from a list.

    The list should be displayed to the user before calling this function and
    should be indexed starting with 1.  This function might exit if the user
    selects "q".

    :param items: the list from which to select
    :param include_none: whether to allow the selection of no item
    :returns: None or the selected item
    """
    while True:
        try:
            answer = input("Enter Index ({}q to quit): ".format(
                "0 for None, " if include_none else ""))
            answer = answer.lower()
            if answer in ["", "q"]:
                print("Canceled")
                return None
            index = int(answer)
            if include_none and index == 0:
                return None
            if index > 0:
                return items[index - 1]
        except (EOFError, IndexError, ValueError):
            pass
        print("Please enter an index value between 1 and {} or q to exit."
              .format(len(items)))


def write_temp_file(text: str = "") -> str:
    """Create a new temporary file and write some initial text to it.

    :param text: the text to write to the temp file
    :returns: the file name of the newly created temp file
    """
    with NamedTemporaryFile(mode='w+t', suffix='.yml', delete=False) as tmp:
        tmp.write(text)
        return tmp.name


def edit(*filenames: str, merge: bool = False) -> None:
    """Edit the given files with the configured editor or merge editor"""
    editor = config.merge_editor if merge else config.editor
    editor = [editor] if isinstance(editor, str) else editor
    editor.extend(filenames)
    child = subprocess.Popen(editor)
    child.communicate()


def create_new_contact(address_book: VdirAddressBook) -> None:
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
            if not confirm("Do you want to open the editor again?"):
                print("Canceled")
                os.remove(temp_file_name)
                sys.exit(0)
        else:
            os.remove(temp_file_name)
            break

    # create carddav object from temp file
    if new_contact is None or template == new_contact_yaml:
        print("Canceled")
    else:
        new_contact.write_to_file()
        print("Creation successful\n\n{}".format(new_contact.pretty()))


def modify_existing_contact(old_contact: CarddavObject) -> None:
    # create temp file and open it with the specified text editor
    temp_file_name = write_temp_file(
        "# Edit contact: {}\n# Address book: {}\n# Vcard version: {}\n"
        "# if you want to cancel, exit without saving\n\n{}".format(
            old_contact, old_contact.address_book, old_contact.version,
            old_contact.to_yaml()))

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
            if not confirm("Do you want to open the editor again?"):
                print("Canceled")
                os.remove(temp_file_name)
                sys.exit(0)
        else:
            os.remove(temp_file_name)
            break

    # check if the user changed anything
    if new_contact is None or old_contact == new_contact:
        print("Nothing changed\n\n{}".format(old_contact.pretty()))
    else:
        new_contact.write_to_file(overwrite=True)
        print("Modification successful\n\n{}".format(new_contact.pretty()))


def merge_existing_contacts(source_contact: CarddavObject,
                            target_contact: CarddavObject,
                            delete_source_contact: bool) -> None:
    # show warning, if target vcard version is not 3.0 or 4.0
    if target_contact.version not in config.supported_vcard_versions:
        print("Warning:\nThe target contact in which to merge is based on "
              "vcard version {} but khard only supports the modification of "
              "vcards with version 3.0 and 4.0.\nIf you proceed, the contact "
              "will be converted to vcard version {} but beware: This could "
              "corrupt the contact file or cause data loss.".format(
                  target_contact.version, config.preferred_vcard_version))
        if not confirm("Do you want to proceed anyway?"):
            print("Canceled")
            sys.exit(0)
    # create temp files for each vcard
    # source vcard
    source_temp_file_name = write_temp_file(
        "# merge from {}\n# Address book: {}\n# Vcard version: {}\n"
        "# if you want to cancel, exit without saving\n\n{}".format(
            source_contact, source_contact.address_book,
            source_contact.version, source_contact.to_yaml()))
    # target vcard
    target_temp_file_name = write_temp_file(
        "# merge into {}\n# Address book: {}\n# Vcard version: {}\n"
        "# if you want to cancel, exit without saving\n\n{}".format(
            target_contact, target_contact.address_book,
            target_contact.version, target_contact.to_yaml()))

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
            if not confirm("Do you want to open the editor again?"):
                print("Canceled")
                os.remove(source_temp_file_name)
                os.remove(target_temp_file_name)
                return
        else:
            os.remove(source_temp_file_name)
            os.remove(target_temp_file_name)
            break

    # compare them
    if merged_contact is None or target_contact == merged_contact:
        print("Target contact unmodified\n\n{}".format(
            target_contact.pretty()))
        sys.exit(0)

    print("Merge contact {} from address book {} into contact {} from address "
          "book {}\n\n".format(source_contact, source_contact.address_book,
                               merged_contact, merged_contact.address_book))
    if delete_source_contact:
        print("To be removed")
    else:
        print("Keep unchanged")
    print("\n\n{}\n\nMerged\n\n{}\n".format(source_contact.pretty(),
                                            merged_contact.pretty()))
    if not confirm("Are you sure?"):
        print("Canceled")
        return

    # save merged_contact to disk and delete source contact
    merged_contact.write_to_file(overwrite=True)
    if delete_source_contact:
        source_contact.delete_vcard_file()
    print("Merge successful\n\n{}".format(merged_contact.pretty()))


def copy_contact(contact: CarddavObject, target_address_book: VdirAddressBook,
                 delete_source_contact: bool) -> None:
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


def list_address_books(address_books: Union[AddressBookCollection,
                                            List[VdirAddressBook]]) -> None:
    table = [["Index", "Address book"]]
    for index, address_book in enumerate(address_books, 1):
        table.append([cast(str, index), address_book.name])
    print(helpers.pretty_print(table))


def list_contacts(vcard_list: List[CarddavObject], fields: Iterable[str] = (),
                  parsable: bool = False) -> None:
    selected_address_books: List[VdirAddressBook] = []
    for contact in vcard_list:
        if contact.address_book not in selected_address_books:
            selected_address_books.append(contact.address_book)
    table = []
    # table header
    if len(selected_address_books) == 1:
        if not parsable:
            print("Address book: {}".format(selected_address_books[0]))
        table_header = ["index", "name", "phone", "email"]
    else:
        if not parsable:
            print("Address books: {}".format(', '.join(
                [str(book) for book in selected_address_books])))
        table_header = ["index", "name", "phone", "email", "address_book"]
    if config.show_uids:
        table_header.append("uid")

    if parsable:
        # Legacy default header fields for parsable.
        table_header = ["uid", "name", "address_book"]

    if fields:
        table_header = [x.lower().replace(' ', '_') for x in fields]

    abook_collection = AddressBookCollection('short uids collection',
                                             selected_address_books)

    if not parsable:
        table.append([x.title().replace('_', ' ') for x in table_header])
    # table body
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    for index, vcard in enumerate(vcard_list):
        row = []
        for field in table_header:
            if field == 'index':
                row.append(str(index + 1))
            elif field in ['name', 'phone', 'email']:
                row.append(formatter.get_special_field(vcard, field))
            elif field == 'uid':
                if parsable:
                    row.append(vcard.uid)
                elif abook_collection.get_short_uid(vcard.uid):
                    row.append(abook_collection.get_short_uid(vcard.uid))
                else:
                    row.append("")
            else:
                row.append(formatter.get_nested_field(vcard, field))
        if parsable:
            print("\t".join([str(v) for v in row]))
        else:
            table.append(row)
    if not parsable:
        print(helpers.pretty_print(table))


def list_with_headers(the_list: List, *headers: str) -> None:
    table = [list(headers)]
    for row in the_list:
        table.append(row.split("\t"))
    print(helpers.pretty_print(table))


def choose_address_book_from_list(header_string: str,
                                  address_books: Union[AddressBookCollection,
                                                       List[VdirAddressBook]]
                                  ) -> Optional[VdirAddressBook]:
    if not address_books:
        return None
    if len(address_books) == 1:
        return address_books[0]
    print(header_string)
    list_address_books(address_books)
    # For all intents and purposes of select() an AddressBookCollection can
    # also be considered a List[VdirAddressBook].
    return select(cast(List[VdirAddressBook], address_books))


def choose_vcard_from_list(header_string: str, vcard_list: List[CarddavObject],
                           include_none: bool = False
                           ) -> Optional[CarddavObject]:
    if not vcard_list:
        return None
    if len(vcard_list) == 1 and not include_none:
        return vcard_list[0]
    print(header_string)
    list_contacts(vcard_list)
    return select(vcard_list, True)


def get_contact_list_by_user_selection(
        address_books: Union[VdirAddressBook, AddressBookCollection],
        query: Query) -> List[CarddavObject]:
    """Find contacts in the given address book grouped, sorted and reversed
    acording to the loaded configuration.

    :param address_books: the address book to search
    :param query: the query to use when searching
    :returns: list of found CarddavObject objects
    """
    contacts = address_books.search(query)
    return sort_contacts(contacts, config.reverse, config.group_by_addressbook,
                         config.sort)


def sort_contacts(contacts: Iterable[CarddavObject], reverse: bool = False,
                  group: bool = False, sort: str = "first_name") -> List[
                      CarddavObject]:
    """Sort a list of contacts

    :param contacts: the contact list to sort
    :param reverse: reverse the order of the returned contacts
    :param group: group results by address book
    :param sort: the field to use for sorting, one of "first_name",
        "last_name", "formatted_name"
    :returns: sorted contact list
    """
    keys = []
    if group:
        keys.append(operator.attrgetter("address_book.name"))
    if sort == "first_name":
        keys.append(operator.methodcaller("get_first_name_last_name"))
    elif sort == "last_name":
        keys.append(operator.methodcaller("get_last_name_first_name"))
    elif sort == "formatted_name":
        keys.append(operator.attrgetter("formatted_name"))
    else:
        raise ValueError('sort must be "first_name", "last_name" or '
                         '"formatted_name" not {}.'.format(sort))
    return sorted(contacts, reverse=reverse,
                  key=lambda x: [unidecode(key(x)).lower() for key in keys])


def prepare_search_queries(args: Namespace) -> Dict[str, Query]:
    """Prepare the search query string from the given command line args.

    Each address book can get a search query string to filter vcards befor
    loading them.  Depending on the question if the address book is used for
    source or target searches different queries have to be combined.

    :param args: the parsed command line
    :returns: a dict mapping abook names to their loading queries
    """
    # get all possible search queries for address book parsing
    source_queries: List[Query] = []
    target_queries: List[Query] = []
    if "source_search_terms" in args:
        source_queries.append(args.source_search_terms)
    if "search_terms" in args:
        source_queries.append(args.search_terms)
    if "target_contact" in args:
        target_queries.append(args.target_contact)
    source_query = AndQuery.reduce(source_queries)
    target_query = AndQuery.reduce(target_queries)
    logger.debug('Created source query: %s', source_query)
    logger.debug('Created target query: %s', target_query)
    # Get all possible search queries for address book parsing, always
    # depending on the fact if the address book is used to find source or
    # target contacts or both.
    queries: Dict[str, List[Query]] = {
        abook.name: [] for abook in config.abooks}
    for name in queries:
        if "addressbook" in args and name in args.addressbook:
            queries[name].append(source_query)
        if "target_addressbook" in args and name in args.target_addressbook:
            queries[name].append(target_query)
    queries2: Dict[str, Query] = {
        n: OrQuery.reduce(q) for n, q in queries.items()}
    logger.debug('Created query: %s', queries)
    return queries2


def generate_contact_list(args: Namespace) -> List[CarddavObject]:
    """Find the contact list with which we will work later on

    :param args: the command line arguments
    :returns: the contacts for further processing
    """
    if "source_search_terms" in args:
        # exception for merge command
        args.search_terms = args.source_search_terms or AnyQuery()
    if "search_terms" not in args:
        # It is simpler to handle subcommand that do not have and need search
        # terms here than conditionally calling generate_contact_list().
        return []
    return get_contact_list_by_user_selection(args.addressbook,
                                              args.search_terms)


def new_subcommand(selected_address_books: AddressBookCollection,
                   input_from_stdin_or_file: str, open_editor: bool) -> None:
    """Create a new contact.

    :param selected_address_books: a list of addressbooks that were selected on
        the command line
    :param input_from_stdin_or_file: the data for the new contact as a yaml
        formatted string
    :param open_editor: whether to open the new contact in the edior after
        creation
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
            print("Creation successful\n\n{}".format(new_contact.pretty()))
    else:
        create_new_contact(selected_address_book)


def add_email_to_contact(name: str, email_address: str,
                         abooks: AddressBookCollection) -> None:
    """Add a new email address to the given contact,
    creating the contact if necessary.

    :param name: name of the contact
    :param email_address: email address of the contact
    :param abooks: the addressbooks that were selected on the command line
    """
    print("Email address: {}".format(email_address))
    if not name:
        name = input("Contact's name: ")

    # search for an existing contact
    selected_vcard = choose_vcard_from_list(
        "Select contact for the found e-mail address",
        get_contact_list_by_user_selection(abooks, TermQuery(name)))

    if selected_vcard is None:
        if not name:
            return

        # create new contact
        if not confirm("Contact '{}' does not exist. Do you want to create it?"
                       .format(name)):
            print("Cancelled")
            return
        # ask for address book, in which to create the new contact
        selected_address_book = choose_address_book_from_list(
            "Select address book for new contact", config.abooks)
        if selected_address_book is None:
            sys.exit("Error: address book list is empty")

        name_parts = name.split()
        first = name_parts[0] if len(name_parts) > 0 else ""
        last = name_parts[-1] if len(name_parts) > 1 else ""

        # ask for name and organisation of new contact
        while True:
            if first:
                first_name = input("First name [empty for '{}']: ".format(first))
                if not first_name:
                    first_name = first
            else:
                first_name = input("First name: ")

            if last:
                last_name = input("Last name [empty for '{}']: ".format(last))
                if not last_name:
                    last_name = last
            else:
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
                return

    # ask for confirmation again
    if not confirm("Do you want to add the email address {} to the contact {}?"
                   .format(email_address, selected_vcard)):
        print("Cancelled")
        return

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
    print("Done.\n\n{}".format(selected_vcard.pretty()))


def find_email_addresses(text: str, fields: List[str]) -> List[Address]:
    """Search the text for email addresses in the given fields.

    :param text: the text to search for email addresses
    :param fields: the fields to look in for email addresses.
        The `all` field searches all headers.
    """
    message = message_from_string(text, policy=SMTP_POLICY)

    def extract_addresses(header) -> List[Address]:
        if header and isinstance(header, (AddressHeader, Group)):
            return list(header.addresses)
        return []

    email_addresses = []

    _all = any([f == "all" for f in fields])
    if _all:
        for _, value in message.items():
            email_addresses.extend(extract_addresses(value))
    else:
        for field in fields:
            email_addresses.extend(extract_addresses(message[field]))

    return email_addresses


def add_email_subcommand(
        text: str,
        abooks: AddressBookCollection,
        fields: List[str]) -> None:
    """Add a new email address to contacts, creating new contacts if necessary.

    :param text: the input text to search for the new email
    :param abooks: the addressbooks that were selected on the command line
    :param field: the header field to extract contacts from
    """
    email_addresses = find_email_addresses(text, fields)
    if not email_addresses:
        sys.exit("No email addresses found in fields {}".format(fields))

    print("Khard: Add email addresses to contacts")

    for email_address in email_addresses:
        name = email_address.display_name
        address = email_address.addr_spec

        add_email_to_contact(name, address, abooks)

        print()

    print("No more email addresses")


def birthdays_subcommand(vcard_list: List[CarddavObject], parsable: bool
                         ) -> None:
    """Print birthday contact table.

    :param vcard_list: the vcards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns devided by tabulator (\t)
    """
    # filter out contacts without a birthday date
    vcard_list = [vcard for vcard in vcard_list if vcard.birthday is not None]
    # sort by date (month and day)
    # The sort function should work for strings and datetime objects.  All
    # strings will besorted before any datetime objects.
    vcard_list.sort(key=lambda x: (x.birthday.month, x.birthday.day)
                    if isinstance(x.birthday, datetime.datetime)
                    else (0, 0, x.birthday))
    # add to string list
    birthday_list = []
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    for vcard in vcard_list:
        name = formatter.get_special_field(vcard, "name")
        if parsable:
            # We did filter out None above but the typechecker does not know
            # this.
            bday = cast(Union[str, datetime.datetime], vcard.birthday)
            if isinstance(bday, str):
                date = bday
            else:
                date = bday.strftime("%Y.%m.%d")
            birthday_list.append("{}\t{}".format(date, name))
        else:
            date = vcard.get_formatted_birthday()
            birthday_list.append("{}\t{}".format(name, date))
    if birthday_list:
        if parsable:
            print('\n'.join(birthday_list))
        else:
            list_with_headers(birthday_list, "Name", "Birthday")
    else:
        if not parsable:
            print("Found no birthdays")
        sys.exit(1)


def phone_subcommand(vcard_list: List[CarddavObject], parsable: bool) -> None:
    """Print a phone application friendly contact table.

    :param vcard_list: the vcards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns devided by tabulator (\t)
    """
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    numbers = []
    for vcard in vcard_list:
        for type, number_list in sorted(vcard.phone_numbers.items(),
                                        key=lambda k: k[0].lower()):
            for number in sorted(number_list):
                name = formatter.get_special_field(vcard, "name")
                if parsable:
                    # parsable option: start with phone number
                    fields = number, name, type
                else:
                    # else: start with name
                    fields = name, type, number
                numbers.append("\t".join(fields))
    if numbers:
        if parsable:
            print('\n'.join(numbers))
        else:
            list_with_headers(numbers, "Name", "Type", "Phone")
    else:
        if not parsable:
            print("Found no phone numbers")
        sys.exit(1)


def post_address_subcommand(vcard_list: List[CarddavObject], parsable: bool
                            ) -> None:
    """Print a contact table. with all postal / mailing addresses

    :param vcard_list: the vcards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns devided by tabulator (\t)
    """
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    addresses = []
    for vcard in vcard_list:
        name = formatter.get_special_field(vcard, "name")
        # create post address line list
        contact_addresses = []
        if parsable:
            for type, post_addresses in sorted(vcard.post_addresses.items(),
                                               key=lambda k: k[0].lower()):
                for post_address in post_addresses:
                    contact_addresses.append([str(post_address), name, type])
        else:
            for type, formatted_addresses in sorted(
                    vcard.get_formatted_post_addresses().items(),
                    key=lambda k: k[0].lower()):
                for address in sorted(formatted_addresses):
                    contact_addresses.append([name, type, address])
        for addr in contact_addresses:
            addresses.append("\t".join(addr))
    if addresses:
        if parsable:
            print('\n'.join(addresses))
        else:
            list_with_headers(addresses, "Name", "Type", "Post address")
    else:
        if not parsable:
            print("Found no post addresses")
        sys.exit(1)


def email_subcommand(search_terms: Query, vcard_list: List[CarddavObject],
                     parsable: bool, remove_first_line: bool) -> None:
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
    :param vcard_list: the vcards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns devided by tabulator (\t)
    :param remove_first_line: remove first line (searching for '' ...)
    """
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    emails = []
    for vcard in vcard_list:
        for type, email_list in sorted(vcard.emails.items(),
                                       key=lambda k: k[0].lower()):
            for email in sorted(email_list):
                name = formatter.get_special_field(vcard, "name")
                if parsable:
                    # parsable option: start with email address
                    fields = email, name, type
                else:
                    # else: start with name
                    fields = name, type, email
                emails.append("\t".join(fields))
    if emails:
        if parsable:
            if not remove_first_line:
                # at least mutt requires that line
                print("searching for '{}' ...".format(search_terms))
            print('\n'.join(emails))
        else:
            list_with_headers(emails, "Name", "Type", "E-Mail")
    else:
        if not parsable:
            print("Found no email addresses")
        elif not remove_first_line:
            print("searching for '{}' ...".format(search_terms))
        sys.exit(1)


def list_subcommand(vcard_list: List[CarddavObject], parsable: bool,
                    fields: List[str]) -> None:
    """Print a user friendly contacts table.

    :param vcard_list: the vcards to print
    :param parsable: machine readable output: columns devided by tabulator (\t)
    :param fields: list of strings for field evaluation
    """
    if not vcard_list:
        if not parsable:
            print("Found no contacts")
        sys.exit(1)
    else:
        list_contacts(vcard_list, fields, parsable)


def modify_subcommand(selected_vcard: CarddavObject,
                      input_from_stdin_or_file: str, open_editor: bool,
                      source: bool = False) -> None:
    """Modify a contact in an external editor.

    :param selected_vcard: the contact to modify
    :param input_from_stdin_or_file: new data from stdin (or a file) that
        should be incorperated into the contact, this should be a yaml
        formatted string
    :param open_editor: whether to open the new contact in the edior after
        creation
    :param source: edit the source file or a yaml version?
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
        if not confirm("Do you want to proceed anyway?"):
            print("Canceled")
            return
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
            print("Nothing changed\n\n{}".format(new_contact.pretty()))
        else:
            print("Modification\n\n{}\n".format(new_contact.pretty()))
            if confirm("Do you want to proceed?"):
                new_contact.write_to_file(overwrite=True)
                if open_editor:
                    modify_existing_contact(new_contact)
                else:
                    print("Done")
            else:
                print("Canceled")
    else:
        modify_existing_contact(selected_vcard)


def remove_subcommand(selected_vcard: CarddavObject, force: bool) -> None:
    """Remove a contact from the addressbook.

    :param selected_vcard: the contact to delete
    :param force: delete without confirmation
    """
    if not force and not confirm(
            "Deleting contact {} from address book {}. Are you sure?".format(
                selected_vcard, selected_vcard.address_book)):
        print("Canceled")
        return
    selected_vcard.delete_vcard_file()
    print("Contact {} deleted successfully".format(
        selected_vcard.formatted_name))


def merge_subcommand(vcard_list: List[CarddavObject],
                     abooks: AddressBookCollection, search_terms: Query
                     ) -> None:
    """Merge two contacts into one.

    :param vcard_list: the vcards from which to choose contacts for mergeing
    :param abooks: the addressbooks to use to find the target contact
    :param search_terms: the search terms to find the target contact
    """
    # Find possible target contacts.
    target_vcards = get_contact_list_by_user_selection(abooks, search_terms)
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


def copy_or_move_subcommand(action: str, vcard_list: List[CarddavObject],
                            target_address_books: AddressBookCollection
                            ) -> None:
    """Copy or move a contact to a different address book.

    :param action: the string "copy" or "move" to indicate what to do
    :param vcard_list: the contact list from which to select one for the action
    :param target_address_books: the target address books
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
        target_abook = choose_address_book_from_list(
            "Select target address book", available_address_books)
        if target_abook is None:
            sys.exit("Error: address book list is empty")

    # check if a contact already exists in the target address book
    target_vcard = choose_vcard_from_list(
        "Select target contact to overwrite (or None to add a new entry)",
        get_contact_list_by_user_selection(
            target_abook, TermQuery(source_vcard.formatted_name)), True)
    # If the target contact doesn't exist, move or copy the source contact into
    # the target address book without further questions.
    if target_vcard is None:
        copy_contact(source_vcard, target_abook, action == "move")
    elif source_vcard == target_vcard:
        # source and target contact are identical
        print("Target contact: {}".format(target_vcard))
        if action == "move":
            copy_contact(source_vcard, target_abook, True)
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
                                 source_vcard.pretty(), target_vcard.pretty(),
                                 action.title()))
        while True:
            input_string = input("Your choice: ")
            if input_string.lower() == "a":
                copy_contact(source_vcard, target_abook, action == "move")
                break
            if input_string.lower() == "o":
                copy_contact(source_vcard, target_abook, action == "move")
                target_vcard.delete_vcard_file()
                break
            if input_string.lower() == "m":
                merge_existing_contacts(source_vcard, target_vcard,
                                        action == "move")
                break
            if input_string.lower() in ["", "q"]:
                print("Canceled")
                break


def main(argv: List[str] = sys.argv[1:]) -> None:
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
        add_email_subcommand(input_from_stdin_or_file,
                             args.addressbook, args.fields)
    elif args.action == "birthdays":
        birthdays_subcommand(vcard_list, args.parsable)
    elif args.action == "phone":
        phone_subcommand(vcard_list, args.parsable)
    elif args.action == "postaddress":
        post_address_subcommand(vcard_list, args.parsable)
    elif args.action == "email":
        email_subcommand(args.search_terms, vcard_list,
                         args.parsable, args.remove_first_line)
    elif args.action == "list":
        list_subcommand(vcard_list, args.parsable, args.fields)
    elif args.action in ["show", "edit", "remove"]:
        selected_vcard = choose_vcard_from_list(
            "Select contact for {} action".format(args.action.title()),
            vcard_list)
        if selected_vcard is None:
            sys.exit("Found no contact")
        if args.action == "show":
            if args.format == "pretty":
                output = selected_vcard.pretty()
            elif args.format == "vcard":
                output = open(selected_vcard.filename).read()
            else:
                output = "# Contact template for khard version {}\n" \
                         "# Name: {}\n# Vcard version: {}\n\n{}".format(
                             khard_version, selected_vcard,
                             selected_vcard.version,
                             selected_vcard.to_yaml())
            args.output_file.write(output)
        elif args.action == "edit":
            modify_subcommand(selected_vcard, input_from_stdin_or_file,
                              args.open_editor, args.format == 'vcard')
        elif args.action == "remove":
            remove_subcommand(selected_vcard, args.force)
    elif args.action == "merge":
        merge_subcommand(vcard_list, args.target_addressbook,
                         args.target_contact)
    elif args.action in ["copy", "move"]:
        copy_or_move_subcommand(
            args.action, vcard_list, args.target_addressbook)
