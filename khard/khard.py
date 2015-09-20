#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import tempfile, subprocess, os, sys, re, argparse
import helpers
from email.header import decode_header
from config import Config
from carddav_object import CarddavObject
from version import khard_version


def create_new_contact(address_book):
    # create temp file
    tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    temp_file_name = tf.name
    old_contact_template = "# create new contact\n%s" % helpers.get_new_contact_template(address_book.get_name())
    tf.write(old_contact_template)
    tf.close()

    # start vim to edit contact template
    child = subprocess.Popen([Config().get_editor(), temp_file_name])
    streamdata = child.communicate()[0]

    # read temp file contents after editing
    tf = open(temp_file_name, "r")
    new_contact_template = tf.read()
    tf.close()
    os.remove(temp_file_name)

    # create carddav object from temp file
    if old_contact_template == new_contact_template:
        print("Canceled")
    else:
        new_contact = CarddavObject.from_user_input(address_book, new_contact_template)
        new_contact.write_to_file()
        print("Creation successful\n\n%s" % new_contact.print_vcard())


def modify_existing_contact(old_contact):
    # create temp file and open it with the specified text editor
    tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    temp_file_name = tf.name
    tf.write("# Edit contact: %s\n%s" \
            % (old_contact.get_full_name(), helpers.get_existing_contact_template(old_contact)))
    tf.close()

    # start editor to edit contact template
    child = subprocess.Popen([Config().get_editor(), temp_file_name])
    streamdata = child.communicate()[0]

    # read temp file contents after editing
    tf = open(temp_file_name, "r")
    new_contact = CarddavObject.from_existing_contact_with_new_user_input(old_contact, tf.read())
    tf.close()
    os.remove(temp_file_name)

    # check if the user changed anything
    if old_contact == new_contact:
        print("Nothing changed.")
    else:
        new_contact.write_to_file(overwrite=True)
        print("Modification successful\n\n%s" % new_contact.print_vcard())


def merge_existing_contacts(source_contact, target_contact, delete_source_contact):
    # create temp files for each vcard
    # source vcard
    source_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    source_temp_file_name = source_tf.name
    source_tf.write("# merge from %s\n%s" \
            % (source_contact.get_full_name(), helpers.get_existing_contact_template(source_contact)))
    source_tf.close()

    # target vcard
    target_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    target_temp_file_name = target_tf.name
    target_tf.write("# merge into %s\n%s" \
            % (target_contact.get_full_name(), helpers.get_existing_contact_template(target_contact)))
    target_tf.close()

    # start editor to edit contact template
    child = subprocess.Popen([Config().get_merge_editor(), source_temp_file_name, target_temp_file_name])
    streamdata = child.communicate()[0]

    # template of source vcard is not required anymore
    os.remove(source_temp_file_name)

    # instead we are interested in the target template contents
    target_tf = open(target_temp_file_name, "r")
    merged_contact = CarddavObject.from_existing_contact_with_new_user_input(target_contact, target_tf.read())
    target_tf.close()
    os.remove(target_temp_file_name)

    # compare them
    if target_contact == merged_contact:
        print("Merge unsuccessfull: Target contact was not modified")
        return

    while True:
        if delete_source_contact:
            input_string = raw_input(
                    "Merge contact %s from address book %s into contact %s from address book %s\n\n" \
                        "To be removed\n\n%s\n\nMerged\n\n%s\n\nAre you sure? (y/n): " \
                    % (source_contact.get_full_name(), source_contact.get_address_book().get_name(),
                        merged_contact.get_full_name(), merged_contact.get_address_book().get_name(),
                        source_contact.print_vcard(), merged_contact.print_vcard()))
        else:
            input_string = raw_input(
                    "Merge contact %s from address book %s into contact %s from address book %s\n\n" \
                        "Keep unchanged\n\n%s\n\nMerged:\n\n%s\n\nAre you sure? (y/n): " \
                    % (source_contact.get_full_name(), source_contact.get_address_book().get_name(),
                        merged_contact.get_full_name(), merged_contact.get_address_book().get_name(),
                        source_contact.print_vcard(), merged_contact.print_vcard()))
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


def copy_contact(source_contact, target_address_book, delete_source_contact):
    if delete_source_contact:
        source_contact.delete_vcard_file()
    source_contact.set_filename(
            os.path.join(
                target_address_book.get_path(), os.path.basename(source_contact.get_filename()))
            )
    source_contact.write_to_file(overwrite=True)
    print("%s contact %s from address book %s to %s" \
            % ("Moved" if delete_source_contact else "Copied", source_contact.get_full_name(),
                source_contact.get_address_book().get_name(), target_address_book.get_name()))
 

def list_contacts(vcard_list):
    selected_address_books = []
    for contact in vcard_list:
        if contact.get_address_book() not in selected_address_books:
            selected_address_books.append(contact.get_address_book())
    if len(selected_address_books) == 1:
        print("Address book: %s" % str(selected_address_books[0]))
        table = [["Id", "Name", "Phone", "E-Mail"]]
    else:
        print("Address books: %s" % ', '.join([str(book) for book in selected_address_books]))
        table = [["Id", "Name", "Phone", "E-Mail", "Address book"]]
    for index, vcard in enumerate(vcard_list):
        row = []
        row.append(index+1)
        if vcard.get_nickname() != "" \
                and Config().show_nicknames():
            row.append("%s (Nickname: %s)" % (vcard.get_full_name(), vcard.get_nickname()))
        else:
            row.append(vcard.get_full_name())
        if vcard.get_phone_numbers().__len__() > 0:
            phone1 = vcard.get_phone_numbers()[0]
            row.append("%s: %s" % (phone1['type'], phone1['value']))
        else:
            row.append("")
        if vcard.get_email_addresses().__len__() > 0:
            email1 = vcard.get_email_addresses()[0]
            row.append("%s: %s" % (email1['type'], email1['value']))
        else:
            row.append("")
        if selected_address_books.__len__() > 1:
            row.append(vcard.get_address_book().get_name())
        table.append(row)
    print(helpers.pretty_print(table))


def choose_vcard_from_list(vcard_list):
    if vcard_list.__len__() == 0:
        return None
    elif vcard_list.__len__() == 1:
        return vcard_list[0]
    else:
        list_contacts(vcard_list)
        while True:
            input_string = raw_input("Enter Id: ")
            if input_string in ["", "q", "Q"]:
                print("Canceled")
                sys.exit(0)
            try:
                vcard_id = int(input_string)
                if vcard_id > 0 and vcard_id <= vcard_list.__len__():
                    break
            except ValueError as e:
                pass
            print("Please enter an Id between 1 and %d or nothing or q to exit." % len(vcard_list))
        print("")
        return vcard_list[vcard_id-1]


def get_contact_list_by_user_selection(address_books, sort_criteria, reverse, search, strict_search):
    """returns a list of CarddavObject objects 
    :param address_books: list of selected address books
    :type address_books: list(AddressBook)
    :param sort_criteria: sort list by given criteria
    :type sort_criteria: str
    :param reverse: reverse ordering
    :type reverse: bool
    :param search: filter contact list
    :type search: str
    :param strict_search: if True, search only in full name field
    :type strict_search: bool
    :returns: list of CarddavObject objects
    :rtype: list(CarddavObject)
    """
    contact_list = []
    regexp = re.compile(search.replace(" ", ".*"), re.IGNORECASE | re.DOTALL)
    for address_book in address_books:
        for contact in address_book.get_contact_list():
            if strict_search:
                if regexp.search(contact.get_full_name()) != None:
                    contact_list.append(contact)
            else:
                if regexp.search(contact.print_vcard()) != None:
                    contact_list.append(contact)
                else:
                    # special case for phone numbers without a space between prefix and number
                    for phone_entry in contact.get_phone_numbers():
                        if regexp.search(re.sub("\D", "", phone_entry['value'])) != None:
                            contact_list.append(contact)
                            break
    if sort_criteria == "addressbook":
        return sorted(contact_list,
                key = lambda x: (x.get_address_book().get_name().lower(),
                    x.get_full_name().lower()),
                reverse=reverse)
    else:
        return sorted(contact_list, key = lambda x: x.get_full_name().lower(), reverse=reverse)


def main():
    # create the args parser
    parser = argparse.ArgumentParser(
            description = "Khard is a carddav address book for the console",
            formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-a", "--addressbook", default="",
            help="Specify address book names as comma separated list")
    parser.add_argument("-r", "--reverse", action="store_true", help="Sort contacts in reverse order")
    parser.add_argument("-s", "--search", default="",
            help="Search in all contact data fields\n" \
                    "    default:   -s \"contact\"\n" \
                    "    merge:     -s \"source contact,target contact\"\n" \
                    "    copy/move: -s \"source contact,target address book\"")
    parser.add_argument("-t", "--sort", default="alphabetical", 
            help="Sort contacts list. Possible values: alphabetical, addressbook")
    parser.add_argument("-v", "--version", action="store_true", help="Get current program version")
    parser.add_argument("action", nargs="?", default="",
            help="Possible actions:\n" \
                    "    list, details, source, mutt, alot, phone,\n" \
                    "    new, add-email, merge, modify, copy, move and remove")
    args = parser.parse_args()

    # version
    if args.version == True:
        print("Khard version %s" % khard_version)
        sys.exit(0)

    # validate value for action
    if args.action == "":
        args.action = Config().get_default_action()
    if args.action not in Config().get_list_of_actions():
        print("Unsupported action. Possible values are: %s" % ', '.join(Config().get_list_of_actions()))
        sys.exit(1)

    # load address books which are defined in the configuration file
    selected_address_books = []
    if args.addressbook == "":
        selected_address_books = Config().get_all_address_books()
    else:
        for name in args.addressbook.split(","):
            if Config().get_address_book(name) is None:
                print("Error: The entered address book \"%s\" does not exist.\nPossible values are: %s" \
                        % (name, ', '.join([ str(book) for book in Config().get_all_address_books() ])))
                sys.exit(1)
            else:
                selected_address_books.append(Config().get_address_book(name))

    # search parameter
    # may either contain one search term for a standard search or two terms, devided by a "," to
    # search for two contacts to merge them
    search_terms = args.search.split(",")
    if len(search_terms) == 1:
        search_terms.append("")

    # sort criteria
    if args.sort not in ["alphabetical", "addressbook"]:
        print("Unsupported sort criteria. Possible values: alphabetical, addressbook")
        sys.exit(1)

    # create a list of all found vcard objects
    vcard_list = get_contact_list_by_user_selection(
            selected_address_books, args.sort, args.reverse, search_terms[0], False)

    # create new contact
    if args.action == "new":
        if len(selected_address_books) != 1:
            if args.addressbook == "":
                print("Error: You must specify an address book for the new contact\nPossible values are: %s" \
                        % ', '.join([ str(book) for book in Config().get_all_address_books() ]))
            else:
                print("Please enter only one address book name")
            sys.exit(1)
        create_new_contact(selected_address_books[0])

    # add email address to contact or create a new one if necessary
    if args.action == "add-email":
        # get name and email address
        email_address = ""
        name = ""
        for line in sys.stdin:
            if line.startswith("From:"):
                try:
                    name = line[6:line.index("<")-1]
                    email_address = line[line.index("<")+1:line.index(">")]
                except ValueError as e:
                    email_address = line[6:].strip()
                break
        # reopen stdin to get user input
        sys.stdin = open('/dev/tty')
        print("Khard: Add email address to contact")
        if not email_address:
            print("Found no email address")
            sys.exit(1)
        print("Email address: %s" % email_address)
        if not name:
            name = raw_input("Contact's name: ")
        else:
            # remove quotes from name string, otherwise decoding fails
            name = name.replace("\"", "")
            # fix encoding of senders name
            name, encoding = decode_header(name)[0]
            if encoding:
                name = name.decode(encoding).encode("utf-8").replace("\"", "")
            # query user input.
            user_input = raw_input("Contact's name [%s]: " % name)
            # if empty, use the extracted name from above
            name = user_input or name

        # search for an existing contact
        selected_vcard = choose_vcard_from_list(
                get_contact_list_by_user_selection(
                    selected_address_books, args.sort, args.reverse, name, True))
        if selected_vcard is None:
            # create new contact
            while True:
                input_string = raw_input("Contact %s does not exist. Do you want to create it (y/n)? " % name)
                if input_string.lower() in ["", "n", "q"]:
                    print("Canceled")
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
            # ask for address book, in which to create the new contact
            print("Available address books: %s" \
                    % ', '.join([ str(book) for book in Config().get_all_address_books() ]))
            while True:
                book_name = raw_input("Address book [%s]: " % selected_address_books[0].get_name()) \
                        or selected_address_books[0].get_name()
                if Config().get_address_book(book_name) is not None:
                    break
            # ask for name and organisation of new contact
            while True:
                first_name = raw_input("First name: ")
                last_name = raw_input("Last name: ")
                organization = raw_input("Organization: ")
                if not first_name and not last_name and not organization:
                    print("Error: All fields are empty.")
                else:
                    break
            selected_vcard = CarddavObject.new_contact(Config().get_address_book(book_name))
            selected_vcard.set_name_and_organisation(first_name.decode("utf-8"),
                    last_name.decode("utf-8"), organization.decode("utf-8"))

        # check if the contact already contains the email address
        for email_entry in selected_vcard.get_email_addresses():
            if email_entry['value'] == email_address:
                print("The contact %s already contains the email address %s" % (selected_vcard, email_address))
                sys.exit(0)

        # ask for confirmation again
        while True:
            input_string = raw_input("Do you want to add the email address %s to the contact %s (y/n)? " \
                    % (email_address, selected_vcard.get_full_name()))
            if input_string.lower() in ["", "n", "q"]:
                print("Canceled")
                sys.exit(0)
            if input_string.lower() == "y":
                break

        # ask for the email label
        print("\nAdding email address %s to contact %s" % (email_address, selected_vcard))
        label = raw_input("email label [home]: ") or "home"
        # add email address to vcard object
        selected_vcard.add_email_address(
                label.decode("utf-8"), email_address.decode("utf-8"))
        # save to disk
        selected_vcard.write_to_file(overwrite=True)
        print("Done.\n\n%s" % selected_vcard.print_vcard())

    # print phone application  friendly contacts table
    if args.action == "phone":
        phone_list = []
        regexp = re.compile(search_terms[0].replace(" ", ".*"), re.IGNORECASE)
        for vcard in vcard_list:
            for tel_entry in vcard.get_phone_numbers():
                phone_number_line = "%s\t%s\t%s" \
                        % (tel_entry['value'], vcard.get_full_name(), tel_entry['type'])
                if len(re.sub("\D", "", search_terms[0])) >= 3:
                    # the user likely searches for a phone number cause the search string contains
                    # at least three digits
                    # so we remove all non-digit chars from the phone number field and match against that
                    if regexp.search(re.sub("\D", "", tel_entry['value'])) != None:
                        phone_list.append(phone_number_line)
                else:
                    # the user doesn't search for a phone number so we can perform a standard search
                    # without removing all non-digit chars from the phone number string
                    if regexp.search(phone_number_line) != None:
                        phone_list.append(phone_number_line)
        print('\n'.join(phone_list))
        if len(phone_list) == 0:
            sys.exit(1)

    # print mutt friendly contacts table
    if args.action == "mutt":
        address_list = ["searching for '%s' ..." % search_terms[0]]
        regexp = re.compile(search_terms[0].replace(" ", ".*"), re.IGNORECASE)
        for vcard in vcard_list:
            for email_entry in vcard.get_email_addresses():
                email_address_line = "%s\t%s\t%s" \
                        % (email_entry['value'], vcard.get_full_name(), email_entry['type'])
                if regexp.search(email_address_line) != None:
                    address_list.append(email_address_line)
        print('\n'.join(address_list))
        if len(address_list) <= 1:
            sys.exit(1)

    # print alot friendly contacts table
    if args.action == "alot":
        address_list = []
        regexp = re.compile(search_terms[0].replace(" ", ".*"), re.IGNORECASE)
        for vcard in vcard_list:
            for email_entry in vcard.get_email_addresses():
                email_address_line = "\"%s %s\" <%s>" \
                        % (vcard.get_full_name(), email_entry['type'], email_entry['value'])
                if regexp.search(email_address_line) != None:
                    address_list.append(email_address_line)
        print('\n'.join(address_list))
        if len(address_list) == 0:
            sys.exit(1)

    # print user friendly contacts table
    if args.action == "list":
        if len(vcard_list) == 0:
            print("Found no contacts")
            sys.exit(1)
        list_contacts(vcard_list)

    # show source or details, modify or remove contact
    if args.action in ["details", "modify", "remove", "source"]:
        selected_vcard = choose_vcard_from_list(vcard_list)
        if selected_vcard is None:
            print("Found no contact")
            sys.exit(1)

        if args.action == "details":
            print selected_vcard.print_vcard()

        elif args.action == "modify":
            modify_existing_contact(selected_vcard)

        elif args.action == "remove":
            while True:
                input_string = raw_input("Deleting contact %s from address book %s. Are you sure? (y/n): " \
                        % (selected_vcard.get_full_name(), selected_vcard.get_address_book().get_name()))
                if input_string.lower() in ["", "n", "q"]:
                    print("Canceled")
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
            selected_vcard.delete_vcard_file()
            print("Contact deleted successfully")

        elif args.action == "source":
            child = subprocess.Popen([Config().get_editor(),
                    selected_vcard.get_filename()])
            streamdata = child.communicate()[0]

    # merge contacts
    if args.action == "merge":
        # get the source vcard, from which to merge
        source_vcard = choose_vcard_from_list(vcard_list)
        if source_vcard is None:
            print("Found no source contact for merging")
            sys.exit(1)

        # get the target vcard, into which to merge
        print("Merge from %s from address book %s\n\nNow choose the contact into which to merge:" \
                % (source_vcard.get_full_name(), source_vcard.get_address_book().get_name()))
        target_vcard = choose_vcard_from_list(
                get_contact_list_by_user_selection(
                    selected_address_books, args.sort, args.reverse, search_terms[1], False))
        if target_vcard is None:
            print("Found no target contact for merging")
            sys.exit(1)

        # merging
        if source_vcard == target_vcard:
            print("The selected contacts are already identical")
        else:
            merge_existing_contacts(source_vcard, target_vcard, True)

    # copy or move contact
    if args.action in ["copy", "move"]:
        # get the source vcard, which to copy or move
        source_vcard = choose_vcard_from_list(vcard_list)
        if source_vcard is None:
            print("Found no contact")
            sys.exit(1)

        # get target address book from search query if provided
        available_address_books = [ book for book in Config().get_all_address_books() if book != source_vcard.get_address_book() ]
        target_address_book = None
        if search_terms[1] != "":
            target_address_book = Config().get_address_book(search_terms[1])
            if target_address_book == None:
                print("The given target address book %s does not exist\n" % search_terms[1])
            elif target_address_book not in available_address_books:
                print("The contact %s is already in the address book %s" \
                        % (source_vcard.get_full_name(), target_address_book.get_name()))
                sys.exit(1)

        # otherwise query the target address book name from user
        if target_address_book == None:
            print("%s contact %s from address book %s\n\nAvailable address books:\n  %s" % (args.action.title(),
                    source_vcard.get_full_name(), source_vcard.get_address_book().get_name(),
                    '\n  '.join([ str(book) for book in available_address_books ])))
        while target_address_book is None:
            input_string = raw_input("Into address book: ")
            if input_string == "":
                print("Canceled")
                sys.exit(0)
            if Config().get_address_book(input_string) in available_address_books:
                print("")
                target_address_book = Config().get_address_book(input_string)

        # check if a contact already exists in the target address book
        target_vcard = choose_vcard_from_list(
                get_contact_list_by_user_selection(
                    [target_address_book], args.sort, args.reverse, source_vcard.get_full_name(), True))

        # if the target contact doesn't exist, move or copy the source contact into the target
        # address book without further questions
        if target_vcard is None:
            copy_contact(source_vcard, target_address_book, args.action == "move")
        else:
            if source_vcard == target_vcard:
                # source and target contact are identical
                if args.action == "move":
                    copy_contact(source_vcard, target_address_book, True)
                else:
                    print("The selected contacts are already identical")
            else:
                # source and target contacts are different
                # either overwrite the target one or merge into target contact
                print("The address book %s already contains the contact %s\n\n" \
                        "Source\n\n%s\n\nTarget\n\n%s\n\n" \
                        "Possible actions:\n" \
                        "  o: Overwrite target contact\n  m: merge from source into target contact\n  q: quit" \
                        % (target_vcard.get_address_book().get_name(), source_vcard.get_full_name(),
                            source_vcard.print_vcard(), target_vcard.print_vcard()))
                while True:
                    input_string = raw_input("Your choice: ")
                    if input_string.lower() == "o":
                        copy_contact(source_vcard, target_address_book, args.action == "move")
                        break
                    if input_string.lower() == "m":
                        merge_existing_contacts(source_vcard, target_vcard, args.action == "move")
                        break
                    if input_string.lower() in ["", "q"]:
                        print("Canceled")
                        break


if __name__ == "__main__":
    main()
