"""Main application logic of khard including command line handling"""

from argparse import Namespace
import datetime
from email import message_from_string
from email.policy import SMTP as SMTP_POLICY
from email.headerregistry import Address, AddressHeader, Group
import logging
import operator
import os
import sys
import textwrap
from typing import cast, Callable, Dict, Iterable, List, Optional, Union

from unidecode import unidecode

from . import helpers
from .address_book import (AddressBookCollection, AddressBookNameError,
                           AddressBookParseError, VdirAddressBook)
from .carddav_object import CarddavObject
from . import cli
from .config import Config
from .formatter import Formatter
from .helpers import interactive
from .helpers.interactive import confirm
from .query import AndQuery, AnyQuery, OrQuery, Query, TermQuery
from .version import version as khard_version


logger = logging.getLogger(__name__)
config: Config


def version_check(contact: CarddavObject, description: str) -> bool:
    if contact.version not in config.supported_vcard_versions:
        print("Warning:\nThe {} is based on vcard version {} but khard only "
              "supports the modification of vcards with version 3.0 and 4.0.\n"
              "If you proceed, the contact will be converted to vcard version "
              "{} but beware: This could corrupt the contact file or cause "
              "data loss.".format(description, contact.version,
                                  config.preferred_vcard_version))
        if not confirm("Do you want to proceed anyway?"):
            print("Canceled")
            return False
    return True


def create_new_contact(address_book: VdirAddressBook) -> None:
    editor = interactive.Editor(config.editor, config.merge_editor)
    # create temp file
    template = "# create new contact\n# Address book: {}\n# Vcard version: " \
        "{}\n# if you want to cancel, exit without saving\n\n{}".format(
            address_book, config.preferred_vcard_version,
            helpers.get_new_contact_template(config.private_objects))
    new_contact = editor.edit_templates(lambda t: CarddavObject.from_yaml(
        address_book, t, config.private_objects,
        config.preferred_vcard_version, config.localize_dates), template)

    # create carddav object from temp file
    if new_contact is None:
        print("Canceled")
    else:
        new_contact.write_to_file()
        print("Creation successful\n\n{}".format(new_contact.pretty()))


def modify_existing_contact(old_contact: CarddavObject) -> None:
    editor = interactive.Editor(config.editor, config.merge_editor)
    # create temp file and open it with the specified text editor
    text = ("# Edit contact: {}\n# Address book: {}\n# Vcard version: {}\n"
            "# if you want to cancel, exit without saving\n\n{}".format(
                old_contact, old_contact.address_book, old_contact.version,
                old_contact.to_yaml()))
    new_contact = editor.edit_templates(
        lambda t: CarddavObject.clone_with_yaml_update(
            old_contact, t, config.localize_dates), text)

    # check if the user changed anything
    if new_contact is None or old_contact == new_contact:
        print("Nothing changed\n\n{}".format(old_contact.pretty()))
    else:
        new_contact.write_to_file(overwrite=True)
        print("Modification successful\n\n{}".format(new_contact.pretty()))


def merge_existing_contacts(source_contact: CarddavObject,
                            target_contact: CarddavObject,
                            delete_source_contact: bool) -> None:
    # show warning, if target vCard version is not 3.0 or 4.0
    if not version_check(target_contact, "target contact in which to merge"):
        return
    # create temp files for each vCard
    editor = interactive.Editor(config.editor, config.merge_editor)
    src_text = ("# merge from {}\n# Address book: {}\n# Vcard version: {}\n"
                "# if you want to cancel, exit without saving\n\n{}".format(
                    source_contact, source_contact.address_book,
                    source_contact.version, source_contact.to_yaml()))
    target_text = ("# merge into {}\n# Address book: {}\n# Vcard version: {}\n"
                   "# if you want to cancel, exit without saving\n\n{}".format(
                       target_contact, target_contact.address_book,
                       target_contact.version, target_contact.to_yaml()))
    merged_contact = editor.edit_templates(
        lambda t: CarddavObject.clone_with_yaml_update(
            target_contact, t, config.localize_dates), src_text, target_text)
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
    selected_kinds = set()
    for contact in vcard_list:
        if contact.address_book not in selected_address_books:
            selected_address_books.append(contact.address_book)
        if contact.kind not in selected_kinds:
            selected_kinds.add(contact.kind)
    table = []
    # default table header
    table_header = ["index", "name", "phone", "email"]
    plural = ""
    if config.show_kinds or len(selected_kinds) > 1 or CarddavObject._default_kind not in selected_kinds:
        table_header.append("kind")
    if len(selected_address_books) > 1:
        plural = "s"
        table_header.append("address_book")
    if not parsable:
        print("Address book{}: {}".format(plural, ', '.join(
                str(book) for book in selected_address_books)))
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
            elif field in ['name', 'phone', 'email', 'kind']:
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


def list_with_headers(the_list: List[str], *headers: str) -> None:
    table = [list(headers)]
    for row in the_list:
        table.append(row.split("\t"))
    print(helpers.pretty_print(table))


def choose_address_book_from_list(header: str, abooks: Union[
                                  AddressBookCollection, List[VdirAddressBook]]
                                  ) -> Optional[VdirAddressBook]:
    """Let the user select one of the given address books

    :param header: some text to print in front of the list
    :param abooks: the address books from which to select
    :returns: the selected address book
    :raises interactive.Canceled: when the user canceled the selection
    """
    if not abooks:
        return None
    if len(abooks) == 1:
        return abooks[0]
    print(header)
    list_address_books(abooks)
    return interactive.select(abooks)


def choose_vcard_from_list(header: str, vcards: List[CarddavObject],
                           include_none: bool = False
                           ) -> Optional[CarddavObject]:
    """Let the user select a contact from a list

    :param header: some text to print in front of the list
    :param vcards: the contacts from which to select
    :returns: the selected contact
    :raises interactive.Canceled: when the user canceled the selection
    """
    if not vcards:
        return None
    if len(vcards) == 1 and not include_none:
        return vcards[0]
    print(header)
    list_contacts(vcards)
    return interactive.select(vcards, True)


def get_contact_list(address_books: Union[VdirAddressBook,
                                          AddressBookCollection],
                     query: Query) -> List[CarddavObject]:
    """Find contacts in the given address book grouped, sorted and reversed
    according to the loaded configuration.

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
    keys: List[Callable] = []
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

    Each address book can get a search query string to filter vCards before
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
    return get_contact_list(args.addressbook, args.search_terms)


def new_subcommand(abooks: AddressBookCollection, data: str, open_editor: bool
                   ) -> None:
    """Create a new contact.

    :param abooks: a list of address books that were selected on the command
        line
    :param data: the data for the new contact as a yaml formatted string
    :param open_editor: whether to open the new contact in the editor after
        creation
    :raises interactive.Canceled: when the user canceled a selection
    """
    # ask for address book, in which to create the new contact
    abook = choose_address_book_from_list(
        "Select address book for new contact", abooks)
    if abook is None:
        sys.exit("Error: address book list is empty")
    # if there is some data in stdin/the input file
    if data:
        # create new contact from stdin/the input file
        try:
            new_contact = CarddavObject.from_yaml(
                abook, data, config.private_objects,
                config.preferred_vcard_version, config.localize_dates)
        except ValueError as err:
            sys.exit(str(err))
        else:
            new_contact.write_to_file()
        if open_editor:
            modify_existing_contact(new_contact)
        else:
            print("Creation successful\n\n{}".format(new_contact.pretty()))
    else:
        create_new_contact(abook)


def add_email_to_contact(name: str, email_address: str,
        abooks: AddressBookCollection, skip_already_added: bool) -> None:
    """Add a new email address to the given contact,
    creating the contact if necessary.

    :param name: name of the contact
    :param email_address: email address of the contact
    :param abooks: the address books that were selected on the command line
    :param skip_already_added: skip if email_address is part of one or more contacts
    :raises interactive.Canceled: when the user canceled a selection
    """

    # email address
    # search in contacts
    matching_contact_list = get_contact_list(abooks, TermQuery(email_address))
    if matching_contact_list:
        matching_contact_list_to_string = ', '.join(
                str(i) for i in matching_contact_list)
        if skip_already_added:
            print("Skipping email address {}: Is already part of {}"
                  .format(email_address, matching_contact_list_to_string))
            return
        if not confirm("Email address: {}, Found in contacts: {}. Select anyway?"
                       .format(email_address, matching_contact_list_to_string)):
            return
    else:
        if name:
            name_and_email = '"{}" <{}>'.format(name, email_address)
        else:
            name_and_email = email_address
        if not confirm("New address: {}. Select?".format(name_and_email)):
            return

    # name
    if not name:
        # ask for name
        name = input("Contact's name: ")
    else:
        # remove chars: " '
        name = name.replace('"', '').replace('\'', '')
    # backup name for the "create new contact" function part below
    original_name = name

    # select contact
    previous_name = name
    previous_selected_vcard = None
    manual_search = False
    while True:
        query: Query
        # search for an existing contact
        name_parts = name.replace(',', '').split()
        if len(name_parts) == 0:
            query = AnyQuery()
        elif len(name_parts) == 1:
            query = TermQuery(name)
        else:
            term_query_list = [TermQuery(part) for part in name_parts]
            query = AndQuery(
                    term_query_list[0], term_query_list[1], *term_query_list[2:])
        found_vcard_list = get_contact_list(abooks, query)

        # select contact from list
        if manual_search:
            selected_vcard = choose_vcard_from_list(
                    "Select contact for the search term: {}".format(name),
                    found_vcard_list, include_none=True)
            if found_vcard_list and not selected_vcard:
                # contact selection cancelled
                # restore previous data
                name = previous_name
                selected_vcard = previous_selected_vcard
            manual_search = False
        else:
            selected_vcard = choose_vcard_from_list(
                    "Select contact for the found e-mail address",
                    found_vcard_list)

        break_outer = False
        while True:
            if selected_vcard is None:
                if found_vcard_list:
                    message = "Contact selection cancelled"
                else:
                    message = "Nothing found for '{}'".format(name)
                answer = interactive.ask(message, ["create", "search", "quit"])
            else:
                answer = interactive.ask(
                    "Contact selected: {}".format(selected_vcard),
                    ["yes", "create", "details", "search", "quit"],
                    """You can enter one of these choices:

                      yes      proceed with selected contact
                      create   create a new contact
                      details  show details of selected contact
                      search   search for a different contact
                      quit     abort
                    """)

            if selected_vcard:
                if answer == 'yes':
                    break_outer = True
                    break
                if answer == 'details':
                    print("\n{}".format(selected_vcard.pretty()))
                    continue
            if answer == 'create':
                selected_vcard = None
                break_outer = True
                break
            if answer == 'search':
                # save data
                previous_name = name
                previous_selected_vcard = selected_vcard
                # enter search string
                if original_name:
                    name = input("Search for contact [ENTER='{}' or -='']: "
                                 .format(original_name)) or original_name
                    if name == "-":
                        name = ""
                else:
                    name = input("Search for contact: ")
                manual_search = True
                break
            if answer == 'quit':
                print("Cancelled")
                return

        if break_outer:
            # restore name
            name = original_name
            break

    # create new contact
    if selected_vcard is None:
        # first and last name variables
        name_parts = name.split()
        # detect format: last_name, first_name in name variable
        if name.count(",") == 1 \
                and len(name_parts) > 1 \
                and name_parts[0].endswith(","):
            # remove "," from presumed last name
            name_parts[0] = name_parts[0].replace(',', '')
            # put last_name to the list end
            name_parts.append(name_parts.pop(0))
        # fill variables
        first = name_parts[0] if len(name_parts) > 0 else name
        last = name_parts[-1] if len(name_parts) > 1 else ""

        # ask for address book, in which to create the new contact
        if not config.abooks:
            sys.exit("Error: address book list is empty")
        else:
            selected_address_book = choose_address_book_from_list(
                    "Select address book for new contact", config.abooks)
            if selected_address_book is None:
                print("No address book selected")
                return

        # ask for name and organisation of new contact
        while True:
            if first:
                first_name = input("First name [ENTER='{}' or -='']: "
                                   .format(first)) or first
                if first_name == "-":
                    first_name = ""
            else:
                first_name = input("First name: ")

            if last:
                last_name = input("Last name [ENTER='{}' or -='']: "
                                  .format(last)) or last
                if last_name == "-":
                    last_name = ""
            else:
                last_name = input("Last name: ")

            if name and not first_name and not last_name:
                # first and last names are empty, maybe it's an organisation
                organisation = input("Organisation [ENTER='{}' or -='']: "
                                     .format(name)) or name
                if organisation == "-":
                    organisation = ""
            else:
                organisation = input("Organisation: ")

            if not first_name and not last_name and not organisation:
                print("Error: All fields are empty.")
            else:
                print("")
                break

        # create contact
        #
        # build template
        template_data = list()
        if first_name:
            template_data.append("First name   : {}".format(first_name))
        if last_name:
            template_data.append("Last name    : {}".format(last_name))
        if organisation:
            template_data.append("Organisation : {}".format(organisation))
        # confirm contact creation
        print("Verify input data\n{}"
              .format(textwrap.indent('\n'.join(template_data), 2*' ')))
        if not confirm("Create contact?", False):
            print("Cancelled")
            return
        selected_vcard = CarddavObject.from_yaml(
                selected_address_book, '\n'.join(template_data),
                config.private_objects, config.preferred_vcard_version,
                config.localize_dates)
        if not selected_vcard:
            print("Could not create contact")
            return
        print("Contact created successfully")

    # check if the contact already contains the email address
    for _, email_list in sorted(selected_vcard.emails.items(),
                                key=lambda k: k[0].lower()):
        for email in email_list:
            if email == email_address:
                print("The contact {} already contains the email address {}"
                      .format(selected_vcard, email_address))
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
        fields: List[str],
        skip_already_added: bool) -> None:
    """Add a new email address to contacts, creating new contacts if necessary.

    :param text: the input text to search for the new email
    :param abooks: the address books that were selected on the command line
    :param field: the header field to extract contacts from
    :param skip_already_added: skip already known email addresses
    :raises interactive.Canceled: when the user canceled a selection
    """
    email_addresses = find_email_addresses(text, fields)
    if not email_addresses:
        sys.exit("No email addresses found in fields {}".format(fields))

    print("Khard: Add email addresses to contacts")

    for email_address in email_addresses:
        name = email_address.display_name
        address = email_address.addr_spec

        add_email_to_contact(name, address, abooks, skip_already_added)

        print()

    print("No more email addresses")


def birthdays_subcommand(vcard_list: List[CarddavObject], parsable: bool
                         ) -> None:
    """Print birthday contact table.

    :param vcard_list: the vCards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns divided by tabulator (\t)
    """
    # filter out contacts without a birthday date
    vcard_list = [vcard for vcard in vcard_list if vcard.birthday is not None]
    # sort by date (month and day)
    # The sort function should work for strings and datetime objects.  All
    # strings will be sorted before any datetime objects.
    vcard_list.sort(key=lambda x: (x.birthday.month, x.birthday.day)
                    if isinstance(x.birthday, datetime.datetime)
                    else (0, 0, x.birthday))
    # add to string list
    birthday_list: List[str] = []
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    for vcard in vcard_list:
        name = formatter.get_special_field(vcard, "name")
        if parsable:
            # We did filter out None above but the type checker does not know
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


def phone_subcommand(search_terms: Query, vcard_list: List[CarddavObject],
        parsable: bool) -> None:
    """Print a phone application friendly contact table.

    :param search_terms: used as search term to filter the contacts before
        printing
    :param vcard_list: the vCards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns divided by tabulator (\t)
    """
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    numbers: List[str] = []
    for vcard in vcard_list:
        field_line_list = []
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
                field_line_list.append("\t".join(fields))
        numbers += _filter_email_post_or_phone_number_results(
                search_terms, field_line_list)
    if numbers:
        if parsable:
            print('\n'.join(numbers))
        else:
            list_with_headers(numbers, "Name", "Type", "Phone")
    else:
        if not parsable:
            print("Found no phone numbers")
        sys.exit(1)


def post_address_subcommand(search_terms: Query,
        vcard_list: List[CarddavObject], parsable: bool
                            ) -> None:
    """Print a contact table with all postal / mailing addresses

    :param search_terms: used as search term to filter the contacts before
        printing
    :param vcard_list: the vCards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns divided by tabulator (\t)
    """
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    addresses: List[str] = []
    for vcard in vcard_list:
        name = formatter.get_special_field(vcard, "name")
        # create post address line list
        field_line_list = []
        if parsable:
            for type, post_addresses in sorted(vcard.post_addresses.items(),
                                               key=lambda k: k[0].lower()):
                for post_address in post_addresses:
                    field_line_list.append(
                            "\t".join([str(post_address), name, type]))
        else:
            for type, formatted_addresses in sorted(
                    vcard.get_formatted_post_addresses().items(),
                    key=lambda k: k[0].lower()):
                for address in sorted(formatted_addresses):
                    field_line_list.append(
                            "\t".join([name, type, address]))
        addresses += _filter_email_post_or_phone_number_results(
                search_terms, field_line_list)
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
    :param vcard_list: the vCards to search for matching entries which should
        be printed
    :param parsable: machine readable output: columns divided by tabulator (\t)
    :param remove_first_line: remove first line (searching for '' ...)
    """
    formatter = Formatter(config.display, config.preferred_email_address_type,
                          config.preferred_phone_number_type,
                          config.show_nicknames, parsable)
    emails: List[str] = []
    for vcard in vcard_list:
        field_line_list = []
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
                field_line_list.append("\t".join(fields))
        emails += _filter_email_post_or_phone_number_results(
                search_terms, field_line_list)
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


def _filter_email_post_or_phone_number_results(search_terms: Query,
        field_line_list: List[str]) -> List[str]:
    """Filter the created output of phone_subcommand, post_address_subcommand
    and email_subcommand by the given search term again.
    If no match is found, return the complete input list

    :param search_terms: used as search term to filter the contacts before
        printing
    :param field_line_list: The line-by-line output of the commands listed above
    """
    matched_line_list = []
    for line in field_line_list:
        if search_terms and search_terms.match(line):
            matched_line_list.append(line)
    return matched_line_list if matched_line_list else field_line_list


def list_subcommand(vcard_list: List[CarddavObject], parsable: bool,
                    fields: List[str]) -> None:
    """Print a user friendly contacts table.

    :param vcard_list: the vCards to print
    :param parsable: machine readable output: columns divided by tabulator (\t)
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
        should be incorporated into the contact, this should be a yaml
        formatted string
    :param open_editor: whether to open the new contact in the editor after
        creation
    :param source: edit the source file or a yaml version?
    """
    if source:
        editor = interactive.Editor(config.editor, config.merge_editor)
        editor.edit_files(selected_vcard.filename)
        return
    # show warning, if vCard version of selected contact is not 3.0 or 4.0
    if not version_check(selected_vcard, "selected contact"):
        return
    # if there is some data in stdin
    if input_from_stdin_or_file:
        # create new contact from stdin
        try:
            new_contact = CarddavObject.clone_with_yaml_update(
                selected_vcard, input_from_stdin_or_file,
                config.localize_dates)
        except ValueError as err:
            sys.exit(str(err))
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
    """Remove a contact from the address book.

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


def merge_subcommand(vcards: List[CarddavObject],
                     abooks: AddressBookCollection, search_terms: Query
                     ) -> None:
    """Merge two contacts into one.

    :param vcards: the vCards from which to choose contacts for merging
    :param abooks: the address books to use to find the target contact
    :param search_terms: the search terms to find the target contact
    :raises interactive.Canceled: when the user canceled a selection
    """
    # Find possible target contacts.
    target_vcards = get_contact_list(abooks, search_terms)
    # get the source vCard, from which to merge
    source_vcard = choose_vcard_from_list("Select contact from which to merge",
                                          vcards)
    if source_vcard is None:
        sys.exit("Found no source contact for merging")
    else:
        print("Merge from {} from address book {}\n\n".format(
            source_vcard, source_vcard.address_book))
    # get the target vCard, into which to merge
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


def copy_or_move_subcommand(action: str, vcards: List[CarddavObject],
                            target_address_books: AddressBookCollection
                            ) -> None:
    """Copy or move a contact to a different address book.

    :param action: the string "copy" or "move" to indicate what to do
    :param vcards: the contact list from which to select one for the action
    :param target_address_books: the target address books
    :raises interactive.Canceled: when the user canceled a selection
    """
    # get the source vCard, which to copy or move
    source_vcard = choose_vcard_from_list(
        "Select contact to {}".format(action.title()), vcards)
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
        get_contact_list(target_abook, TermQuery(source_vcard.formatted_name)),
        True)
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
              "Source\n\n{}\n\nTarget\n\n{}\n\n".format(
              target_vcard.address_book, source_vcard, source_vcard.pretty(),
              target_vcard.pretty()))
        while True:
            answer = interactive.ask(
                "Possible actions", [action, "merge", "overwrite", "quit"],
                "quit")
            if answer == action:
                copy_contact(source_vcard, target_abook, action == "move")
                break
            if answer == "overwrite":
                copy_contact(source_vcard, target_abook, action == "move")
                target_vcard.delete_vcard_file()
                break
            if answer == "merge":
                merge_existing_contacts(source_vcard, target_vcard,
                                        action == "move")
                break
            if answer == "quit":
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
        sys.exit(str(err))

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
            except OSError as err:
                sys.exit("Error: {}\n       File: {}".format(err.strerror,
                                                             err.filename))
        elif not sys.stdin.isatty():
            # try to read from stdin
            try:
                input_from_stdin_or_file = sys.stdin.read()
            except OSError:
                sys.exit("Error: Can't read from stdin")
            # try to reopen console
            # otherwise further user interaction is not possible (for example
            # selecting a contact from the contact table)
            try:
                sys.stdin = open('/dev/tty')
            except OSError:
                pass

    # these listing commands do not require any user interaction
    if args.action == "birthdays":
        birthdays_subcommand(vcard_list, args.parsable)
    elif args.action == "phone":
        phone_subcommand(args.search_terms, vcard_list, args.parsable)
    elif args.action == "postaddress":
        post_address_subcommand(args.search_terms, vcard_list, args.parsable)
    elif args.action == "email":
        email_subcommand(args.search_terms, vcard_list,
                         args.parsable, args.remove_first_line)
    elif args.action == "list":
        list_subcommand(vcard_list, args.parsable, args.fields)

    else:
        # these commands require user interaction
        try:
            if args.action == "new":
                new_subcommand(args.addressbook, input_from_stdin_or_file,
                               args.open_editor)
            elif args.action == "add-email":
                add_email_subcommand(input_from_stdin_or_file,
                                     args.addressbook, args.headers,
                                     args.skip_already_added)
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
        except interactive.Canceled as ex:
            sys.exit(str(ex))
