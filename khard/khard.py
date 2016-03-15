# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import tempfile, subprocess, os, sys, re, argparse, datetime
from . import helpers
from email.header import decode_header
from .config import Config
from .carddav_object import CarddavObject
from .version import khard_version


def create_new_contact(address_book):
    # create temp file
    tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    temp_file_name = tf.name
    old_contact_template = "# create new contact\n%s" % helpers.get_new_contact_template(address_book.get_name())
    tf.write(old_contact_template)
    tf.close()

    temp_file_creation = helpers.file_modification_date(temp_file_name)
    while True:
        # start vim to edit contact template
        child = subprocess.Popen([Config().get_editor(), temp_file_name])
        streamdata = child.communicate()[0]
        if temp_file_creation == helpers.file_modification_date(temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        tf = open(temp_file_name, "r")
        new_contact_template = tf.read()
        tf.close()

        # try to create new contact
        try:
            new_contact = CarddavObject.from_user_input(address_book, new_contact_template)
        except ValueError as e:
            print("\n%s\n" % e)
            while True:
                input_string = raw_input("Do you want to open the editor again (y/n)? ")
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
    tf.write("# Edit contact: %s\n%s" \
            % (old_contact.get_full_name(), old_contact.get_template()))
    tf.close()

    temp_file_creation = helpers.file_modification_date(temp_file_name)
    while True:
        # start editor to edit contact template
        child = subprocess.Popen([Config().get_editor(), temp_file_name])
        streamdata = child.communicate()[0]
        if temp_file_creation == helpers.file_modification_date(temp_file_name):
            new_contact = None
            os.remove(temp_file_name)
            break

        # read temp file contents after editing
        tf = open(temp_file_name, "r")
        new_contact_template = tf.read()
        tf.close()

        # try to create contact from user input
        try:
            new_contact = CarddavObject.from_existing_contact_with_new_user_input(
                    old_contact, new_contact_template)
        except ValueError as e:
            print("\n%s\n" % e)
            while True:
                input_string = raw_input("Do you want to open the editor again (y/n)? ")
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


def merge_existing_contacts(source_contact, target_contact, delete_source_contact):
    # create temp files for each vcard
    # source vcard
    source_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    source_temp_file_name = source_tf.name
    source_tf.write("# merge from %s\n%s" \
            % (source_contact.get_full_name(), source_contact.get_template()))
    source_tf.close()

    # target vcard
    target_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    target_temp_file_name = target_tf.name
    target_tf.write("# merge into %s\n%s" \
            % (target_contact.get_full_name(), target_contact.get_template()))
    target_tf.close()

    target_temp_file_creation = helpers.file_modification_date(target_temp_file_name)
    while True:
        # start editor to edit contact template
        child = subprocess.Popen([Config().get_merge_editor(), source_temp_file_name, target_temp_file_name])
        streamdata = child.communicate()[0]
        if target_temp_file_creation == helpers.file_modification_date(target_temp_file_name):
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
            merged_contact = CarddavObject.from_existing_contact_with_new_user_input(
                    target_contact, merged_contact_template)
        except ValueError as e:
            print("\n%s\n" % e)
            while True:
                input_string = raw_input("Do you want to open the editor again (y/n)? ")
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
    if merged_contact is None \
            or target_contact == merged_contact:
        print("Target contact unmodified\n\n%s" % target_contact.print_vcard())
        sys.exit(0)

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
        # move contact to new address book and preserve uid
        source_contact.delete_vcard_file()
        source_contact.set_filename(
                os.path.join(
                    target_address_book.get_path(), "%s.vcf" % source_contact.get_uid())
                )
    else:
        # copy contact to new address book and create a new uid for the copied entry
        source_contact.delete_vcard_object("UID")
        new_uid = helpers.get_random_uid()
        source_contact.add_uid(new_uid)
        source_contact.set_filename(
                os.path.join(
                    target_address_book.get_path(), "%s.vcf" % new_uid)
                )
    source_contact.write_to_file()
    print("%s contact %s from address book %s to %s" \
            % ("Moved" if delete_source_contact else "Copied", source_contact.get_full_name(),
                source_contact.get_address_book().get_name(), target_address_book.get_name()))
 

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
        print("Address books: %s" % ', '.join([str(book) for book in selected_address_books]))
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
            if Config().sort_by_name() == "first_name":
                row.append("%s (Nickname: %s)" \
                        % (vcard.get_first_name_last_name(), vcard.get_nicknames()[0]))
            else:
                row.append("%s (Nickname: %s)" \
                        % (vcard.get_last_name_first_name(), vcard.get_nicknames()[0]))
        else:
            if Config().sort_by_name() == "first_name":
                row.append(vcard.get_first_name_last_name())
            else:
                row.append(vcard.get_last_name_first_name())
        if len(vcard.get_phone_numbers().keys()) > 0:
            phone_dict = vcard.get_phone_numbers()
            first_type = sorted(phone_dict.keys(), key=lambda k: k[0].lower())[0]
            row.append("%s: %s" % (first_type, sorted(phone_dict.get(first_type))[0]))
        else:
            row.append("")
        if len(vcard.get_email_addresses().keys()) > 0:
            email_dict = vcard.get_email_addresses()
            first_type = sorted(email_dict.keys(), key=lambda k: k[0].lower())[0]
            row.append("%s: %s" % (first_type, sorted(email_dict.get(first_type))[0]))
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


def choose_vcard_from_list(vcard_list):
    if vcard_list.__len__() == 0:
        return None
    elif vcard_list.__len__() == 1:
        return vcard_list[0]
    else:
        list_contacts(vcard_list)
        while True:
            input_string = raw_input("Enter Index: ")
            if input_string in ["", "q", "Q"]:
                print("Canceled")
                sys.exit(0)
            try:
                vcard_index = int(input_string)
                if vcard_index > 0 and vcard_index <= vcard_list.__len__():
                    break
            except ValueError as e:
                pass
            print("Please enter an index value between 1 and %d or nothing or q to exit." % len(vcard_list))
        print("")
        return vcard_list[vcard_index-1]


def get_contact_list_by_user_selection(address_books, reverse, search, strict_search):
    """returns a list of CarddavObject objects 
    :param address_books: list of selected address books
    :type address_books: list(AddressBook)
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
    regexp = re.compile(search.replace("*", ".*").replace(" ", ".*"), re.IGNORECASE | re.DOTALL)
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
                    for type, number_list in sorted(contact.get_phone_numbers().items()):
                        for number in number_list:
                            if regexp.search(re.sub("\D", "", number)) != None:
                                contact_list.append(contact)
                                break
    if Config().group_by_addressbook():
        if Config().sort_by_name() == "first_name":
            return sorted(contact_list,
                    key = lambda x: (
                        x.get_address_book().get_name().lower(),
                        x.get_first_name_last_name().lower()
                    ), reverse=reverse)
        else:
            return sorted(contact_list,
                    key = lambda x: (
                        x.get_address_book().get_name().lower(),
                        x.get_last_name_first_name().lower()
                    ), reverse=reverse)
    else:
        if Config().sort_by_name() == "first_name":
            return sorted(contact_list, key = lambda x: x.get_first_name_last_name().lower(), reverse=reverse)
        else:
            return sorted(contact_list, key = lambda x: x.get_last_name_first_name().lower(), reverse=reverse)


def main():
    # create the args parser
    parser = argparse.ArgumentParser(
            description = "Khard is a carddav address book for the console",
            formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument("-a", "--addressbook", default="",
            help="Specify address book names as comma separated list")
    parser.add_argument("-g", "--group-by-addressbook", action="store_true",
            help="Group contact table by address book")
    parser.add_argument("--open-editor", action="store_true",
            help="Open the default text editor after successful creation of new contact from stdin or template file")
    parser.add_argument("-r", "--reverse", action="store_true",
            help="Reverse order of contact table")
    parser.add_argument("-s", "--search", default="",
            help="Search in all contact data fields\n" \
                    "    default:   -s \"contact\"\n" \
                    "    merge:     -s \"source contact,target contact\"\n" \
                    "    copy/move: -s \"source contact,target address book\"")
    parser.add_argument("--sort", default="", 
            help="Sort contact table by first or last name\n" \
                    "    Possible values: first_name, last_name")
    parser.add_argument("-t", "--template-file", default="",
            help="Specify template file name\n" \
                    "    new:     khard -a addr_name -t input.yaml\n" \
                    "    modify:  khard -s anything -t input.yaml\n" \
                    "    export:  khard -s anything -t export.yaml")
    parser.add_argument("-u", "--uid", default="", help="Select contact by uid")
    parser.add_argument("-v", "--version", action="store_true", help="Get current program version")
    parser.add_argument("action", nargs="?", default="",
            help="Possible actions:\n" \
                    "    list, details, export, email, phone, source,\n" \
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

    # group by address book
    if args.group_by_addressbook:
        Config().set_group_by_addressbook()

    # sort criteria: first or last name
    if args.sort:
        if args.sort in ["first_name", "last_name"]:
            Config().set_sort_by_name(args.sort)
        else:
            print("Unsupported sort criteria. Possible values: first_name, last_name")
            sys.exit(1)

    # create a list of all found vcard objects
    if args.uid:
        vcard_list = []
        # check if contacts uid == args.uid
        for address_book in Config().get_all_address_books():
            for contact in address_book.get_contact_list():
                if contact.get_uid() == args.uid:
                    vcard_list.append(contact)
        # if that fails, check if contacts uid starts with args.uid
        if len(vcard_list) == 0:
            for address_book in Config().get_all_address_books():
                for contact in address_book.get_contact_list():
                    if contact.get_uid().startswith(args.uid):
                        vcard_list.append(contact)
        if len(vcard_list) != 1:
            if len(vcard_list) == 0:
                print("Found no contact for uid %s" % args.uid)
            else:
                print("Found multiple contacts for uid %s" % args.uid)
                for vcard in vcard_list:
                    print("    %s: %s" % (vcard.get_full_name(), vcard.get_uid()))
            sys.exit(1)
    else:
        vcard_list = get_contact_list_by_user_selection(
                selected_address_books, args.reverse, search_terms[0], False)

    # read from template file or stdin if available
    input_from_stdin_or_file = ""
    if args.action in ["add-email", "new", "modify"]:
        if args.template_file:
            with open(args.template_file, "r") as f:
                input_from_stdin_or_file = f.read()
        elif not sys.stdin.isatty():
            input_from_stdin_or_file = sys.stdin.read()
            sys.stdin = open('/dev/tty')

    # create new contact
    if args.action == "new":
        if len(selected_address_books) == 1:
            selected_address_book = selected_address_books[0]
        else:
            if args.addressbook == "":
                # ask for address book
                print("Create new contact\nEnter address book name")
                for book in Config().get_all_address_books():
                    print("  %s" % book.get_name())
                while True:
                    input_string = raw_input("Address book: ")
                    if input_string == "":
                        print("Canceled")
                        sys.exit(0)
                    if Config().get_address_book(input_string) in Config().get_all_address_books():
                        selected_address_book = Config().get_address_book(input_string)
                        print("")
                        break
            else:
                print("Please enter only a single address book name")
                sys.exit(1)
        # if there is some data in stdin
        if input_from_stdin_or_file:
            # create new contact from stdin
            try:
                new_contact = CarddavObject.from_user_input(
                        selected_address_book, input_from_stdin_or_file)
            except ValueError as e:
                print(e)
                sys.exit(1)
            else:
                new_contact.write_to_file()
            if args.open_editor:
                modify_existing_contact(new_contact)
            else:
                print("Creation successful\n\n%s" % new_contact.print_vcard())
        else:
            create_new_contact(selected_address_book)

    # add email address to contact or create a new one if necessary
    if args.action == "add-email":
        # get name and email address
        email_address = ""
        name = ""
        for line in input_from_stdin_or_file.splitlines():
            if line.startswith("From:"):
                try:
                    name = line[6:line.index("<")-1]
                    email_address = line[line.index("<")+1:line.index(">")]
                except ValueError as e:
                    email_address = line[6:].strip()
                break
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
                    selected_address_books, args.reverse, name, True))
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
                organisation = raw_input("Organisation: ")
                if not first_name and not last_name and not organisation:
                    print("Error: All fields are empty.")
                else:
                    break
            selected_vcard = CarddavObject.from_user_input(
                    Config().get_address_book(book_name),
                    "First name : %s\nLast name : %s\nOrganisation : %s" % (first_name, last_name, organisation))

        # check if the contact already contains the email address
        for type, email_list in sorted(selected_vcard.get_email_addresses().items(), key=lambda k: k[0].lower()):
            for email in email_list:
                if email == email_address:
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
        print("\nAdding email address %s to contact %s\n" \
                "Enter email label\n" \
                "    At least one of: home, internet, pref, uri, work, x400\n" \
                "    Or a custom label (only letters" % (email_address, selected_vcard))
        while True:
            label = raw_input("email label [internet]: ") or "internet"
            try:
                selected_vcard.add_email_address(label, email_address)
            except ValueError as e:
                print(e)
            else:
                break
        # save to disk
        selected_vcard.write_to_file(overwrite=True)
        print("Done.\n\n%s" % selected_vcard.print_vcard())

    # print phone application  friendly contacts table
    if args.action == "phone":
        all_phone_numbers_list = []
        matching_phone_number_list = []
        regexp = re.compile(search_terms[0].replace("*", ".*").replace(" ", ".*"), re.IGNORECASE)
        for vcard in vcard_list:
            for type, number_list in sorted(vcard.get_phone_numbers().items(), key=lambda k: k[0].lower()):
                for number in sorted(number_list):
                    phone_number_line = "%s\t%s\t%s" % (number, vcard.get_full_name(), type)
                    if len(re.sub("\D", "", search_terms[0])) >= 3:
                        # the user likely searches for a phone number cause the search string contains
                        # at least three digits
                        # so we remove all non-digit chars from the phone number field and match against that
                        if regexp.search(re.sub("\D", "", number)) != None:
                            matching_phone_number_list.append(phone_number_line)
                    else:
                        # the user doesn't search for a phone number so we can perform a standard search
                        # without removing all non-digit chars from the phone number string
                        if regexp.search(phone_number_line) != None:
                            matching_phone_number_list.append(phone_number_line)
                    # collect all phone numbers in a different list as fallback
                    all_phone_numbers_list.append(phone_number_line)
        if len(matching_phone_number_list) > 0:
            print('\n'.join(matching_phone_number_list))
        elif len(all_phone_numbers_list) > 0:
            print('\n'.join(all_phone_numbers_list))
        else:
            sys.exit(1)

    # print mail client friendly contacts table
    # compatible to mutt and alot
    # output format:
    #   single line of text
    #   email_address\tname\ttype
    #   email_address\tname\ttype
    #   [...]
    if args.action == "email":
        matching_email_address_list = []
        all_email_address_list = []
        regexp = re.compile(search_terms[0].replace("*", ".*").replace(" ", ".*"), re.IGNORECASE)
        for vcard in vcard_list:
            for type, email_list in sorted(vcard.get_email_addresses().items(), key=lambda k: k[0].lower()):
                for email in sorted(email_list):
                    email_address_line = "%s\t%s\t%s" \
                            % (email, vcard.get_full_name(), type)
                    if regexp.search(email_address_line) != None:
                        matching_email_address_list.append(email_address_line)
                    # collect all email addresses in a different list as fallback
                    all_email_address_list.append(email_address_line)
        print("searching for '%s' ..." % search_terms[0])
        if len(matching_email_address_list) > 0:
            print('\n'.join(matching_email_address_list))
        elif len(all_email_address_list) > 0:
            print('\n'.join(all_email_address_list))
        else:
            sys.exit(1)

    # print user friendly contacts table
    if args.action == "list":
        if len(vcard_list) == 0:
            print("Found no contacts")
            sys.exit(1)
        list_contacts(vcard_list)

    # show source or details, modify or remove contact
    if args.action in ["details", "modify", "remove", "source", "export"]:
        selected_vcard = choose_vcard_from_list(vcard_list)
        if selected_vcard is None:
            print("Found no contact")
            sys.exit(1)

        if args.action == "details":
            print(selected_vcard.print_vcard())

        elif args.action == "export":
            if args.template_file:
                with open(args.template_file, "w") as f:
                    f.write(selected_vcard.get_template())
            else:
                print(selected_vcard.get_template())

        elif args.action == "modify":
            # if there is some data in stdin
            if input_from_stdin_or_file:
                # create new contact from stdin
                try:
                    new_contact = CarddavObject.from_existing_contact_with_new_user_input(
                            selected_vcard, input_from_stdin_or_file)
                except ValueError as e:
                    print(e)
                    sys.exit(1)
                if selected_vcard == new_contact:
                    print("Nothing changed\n\n%s" % new_contact.print_vcard())
                else:
                    print("Modification\n\n%s\n" % new_contact.print_vcard())
                    while True:
                        input_string = raw_input("Do you want to proceed (y/n)? ")
                        if input_string.lower() in ["", "n", "q"]:
                            print("Canceled")
                            break
                        if input_string.lower() == "y":
                            new_contact.write_to_file(overwrite=True)
                            print("Done")
                            break
            else:
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
                    selected_address_books, args.reverse, search_terms[1], False))
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
                    [target_address_book], args.reverse, source_vcard.get_full_name(), True))

        # if the target contact doesn't exist, move or copy the source contact into the target
        # address book without further questions
        print(target_address_book)
        print(target_vcard)
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
                        "  a: %s anyway\n  m: Merge from source into target contact\n  o: Overwrite target contact\n  q: Quit" \
                        % (target_vcard.get_address_book().get_name(), source_vcard.get_full_name(),
                            source_vcard.print_vcard(), target_vcard.print_vcard(),
                            "Move" if args.action == "move" else "Copy"))
                while True:
                    input_string = raw_input("Your choice: ")
                    if input_string.lower() == "a":
                        copy_contact(source_vcard, target_address_book, args.action == "move")
                        break
                    if input_string.lower() == "o":
                        target_vcard.delete_vcard_file()
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
