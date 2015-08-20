#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import tempfile, subprocess, os, sys, re
import argparse
import helpers
from email.header import decode_header
from config import Config
from carddav_object import CarddavObject
from version import khard_version


def create_new_contact(addressbook):
    # create temp file
    tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    temp_file_name = tf.name
    tf.write(helpers.get_new_contact_template(addressbook['name']))
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
    vcard = CarddavObject(addressbook['name'], addressbook['path'])
    vcard.process_user_input(new_contact_template)
    vcard.write_to_file()
    print "Creation successful\n\n%s" % vcard.print_vcard()


def modify_existing_contact(vcard):
    # get content template for contact
    old_contact_template = helpers.get_existing_contact_template(vcard)

    # create temp file and open it with the specified text editor
    tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    temp_file_name = tf.name
    tf.write(old_contact_template)
    tf.close()

    # start editor to edit contact template
    child = subprocess.Popen([Config().get_editor(), temp_file_name])
    streamdata = child.communicate()[0]

    # read temp file contents after editing
    tf = open(temp_file_name, "r")
    new_contact_template = tf.read()
    tf.close()
    os.remove(temp_file_name)

    # check if the user changed anything
    if old_contact_template != new_contact_template:
        vcard.process_user_input(new_contact_template)
        vcard.write_to_file(overwrite=True)
        print "Creation successful\n\n%s" % vcard.print_vcard()
    else:
        print "Nothing changed."


def merge_existing_contacts(first_vcard, second_vcard):
    # create temp files for each vcard

    # first
    old_first_contact_template = helpers.get_existing_contact_template(first_vcard)
    first_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    first_temp_file_name = first_tf.name
    first_tf.write(old_first_contact_template)
    first_tf.close()

    # second
    old_second_contact_template = helpers.get_existing_contact_template(second_vcard)
    second_tf = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    second_temp_file_name = second_tf.name
    second_tf.write(old_second_contact_template)
    second_tf.close()

    # start editor to edit contact template
    child = subprocess.Popen([Config().get_merge_editor(), first_temp_file_name, second_temp_file_name])
    streamdata = child.communicate()[0]

    # first
    first_tf = open(first_temp_file_name, "r")
    new_first_contact_template = first_tf.read()
    first_tf.close()
    os.remove(first_temp_file_name)

    # second
    second_tf = open(second_temp_file_name, "r")
    new_second_contact_template = second_tf.read()
    second_tf.close()
    os.remove(second_temp_file_name)

    # make sure at least one of them changed
    if new_first_contact_template == old_first_contact_template:
        print("Merge unsuccessfull, First contact unchanged")
        return
    if new_second_contact_template != old_second_contact_template:
        print("Merge unsuccessfull, please only modify the first contact");
        return

    first_vcard.process_user_input(new_first_contact_template)
    while True:
        input_string = raw_input("Merging contacts %s and %s\n\nMerged\n\n%s\n\nTo be removed\n\n%s\n\nAre you sure? (y/n): " \
                % (first_vcard.get_full_name(), second_vcard.get_full_name(),
                    first_vcard.print_vcard(), second_vcard.print_vcard()))
        if input_string.lower() in ["", "n", "q"]:
            print "Canceled"
            sys.exit(0)
        if input_string.lower() == "y":
            break

    first_vcard.write_to_file(overwrite=True)
    second_vcard.delete_vcard_file()
    print "Merge successful\n\n%s" % first_vcard.print_vcard()


def list_contacts(selected_addressbooks, vcard_list):
    if selected_addressbooks.__len__() == 1:
        print "Address book: %s" % selected_addressbooks[0]
        table = [["Id", "Name", "Phone", "E-Mail"]]
    else:
        print "Address books: %s" % ', '.join(selected_addressbooks)
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
        if selected_addressbooks.__len__() > 1:
            row.append(vcard.get_addressbook_name())
        table.append(row)
    print helpers.pretty_print(table)


def choose_vcard_from_list(selected_addressbooks, vcard_list):
    if vcard_list.__len__() == 0:
        return None
    elif vcard_list.__len__() == 1:
        return vcard_list[0]
    else:
        list_contacts(selected_addressbooks, vcard_list)
        while True:
            input_string = raw_input("Enter Id: ")
            if input_string in ["", "q", "Q"]:
                sys.exit(0)
            try:
                vcard_id = int(input_string)
                if vcard_id > 0 and vcard_id <= vcard_list.__len__():
                    break
            except ValueError as e:
                pass
            print "Please enter an Id between 1 and %d or nothing or q to exit." % vcard_list.__len__()
        print ""
        return vcard_list[vcard_id-1]
 

def main():
    # create the args parser
    parser = argparse.ArgumentParser(description="Khard is a carddav address book for the console")
    parser.add_argument("-a", "--addressbook", default="",
            help="Specify address book names as comma separated list")
    parser.add_argument("-r", "--reverse", action="store_true", help="Sort contacts in reverse order")
    parser.add_argument("-s", "--search", default="",
            help="Search for contacts. Special format for merge command: \"Contact 1|Contact 2\"")
    parser.add_argument("-t", "--sort", default="alphabetical", 
            help="Sort contacts list. Possible values: alphabetical, addressbook")
    parser.add_argument("-v", "--version", action="store_true", help="Get current program version")
    parser.add_argument("action", nargs="?", default="",
            help="Possible actions: list, details, mutt, alot, phone, new, add-email, modify, merge, remove and source")
    args = parser.parse_args()

    # version
    if args.version == True:
        print "Khard version %s" % khard_version
        sys.exit(0)

    # validate value for action
    if args.action == "":
        args.action = Config().get_default_action()
    if args.action not in Config().get_list_of_actions():
        print "Unsupported action. Possible values are: %s" % ', '.join(Config().get_list_of_actions())
        sys.exit(1)

    # load address books which are defined in the configuration file
    addressbooks = Config().get_all_addressbooks()
    if args.addressbook == "":
        args.addressbook = ','.join(addressbooks.keys())

    # given address book name
    selected_addressbooks = []
    for name in args.addressbook.split(","):
        if Config().has_addressbook(name) == False:
            print "Error: The entered address book \"%s\" does not exist. Possible values are: %s" \
                    % (name, ', '.join(addressbooks.keys()))
            sys.exit(1)
        selected_addressbooks.append(name)

    # search parameter
    # may either contain one search term for a standard search or two terms, devided by a "|" to
    # search for two contacts to merge them
    search_terms = args.search.split("|")
    if len(search_terms) == 1:
        search_terms.append("")

    # sort criteria
    if args.sort not in ["alphabetical", "addressbook"]:
        print "Unsupported sort criteria. Possible values: alphabetical, addressbook"
        sys.exit(1)

    # create new contact
    if args.action == "new":
        if selected_addressbooks.__len__() != 1:
            print "Error: You must specify an address book for the new contact\n" \
                    "Possible values are: %s" % ', '.join(addressbooks.keys())
            sys.exit(1)
        create_new_contact(addressbooks[selected_addressbooks[0]])
        sys.exit(0)

    # add email address to contact or create a new one if necessary
    if args.action == "add-email":
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
        print "Khard: Add email address to contact"
        if not email_address:
            print "Found no email address"
            sys.exit(1)
        print "Email address: %s" % email_address
        if not name:
            name = raw_input("Contact's name: ")
        else:
            # fix encoding of senders name
            name, encoding = decode_header(name)[0]
            if encoding:
                name = name.decode(encoding).encode("utf-8")
            # remove quotes from name string
            name = name.replace("\"", "")
            # query user input.
            user_input = raw_input("Contact's name [%s]: " % name)
            # if empty, use the extracted name from above
            name = user_input or name
        # search for an existing contact
        selected_vcard = choose_vcard_from_list(selected_addressbooks,
                Config().get_vcard_objects(selected_addressbooks, args.sort, args.reverse, name, True))
        if selected_vcard == None:
            # create new contact
            while True:
                input_string = raw_input("Contact %s does not exist. Do you want to create it (y/n)? " % name)
                if input_string.lower() in ["", "n", "q"]:
                    print "Canceled"
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
            print "Available address books: %s" % ', '.join(selected_addressbooks)
            while True:
                book_name = raw_input("Address book [%s]: " % selected_addressbooks[0]) or selected_addressbooks[0]
                if Config().has_addressbook(book_name):
                    break
            selected_vcard = CarddavObject(addressbooks[book_name]['name'], addressbooks[book_name]['path'])
            while True:
                first_name = raw_input("First name: ")
                last_name = raw_input("Last name: ")
                organization = raw_input("Organization: ")
                if not first_name and not last_name and not organization:
                    print "Error: All fields are empty."
                else:
                    break
            selected_vcard.set_name_and_organisation(first_name.decode("utf-8"),
                    last_name.decode("utf-8"), organization.decode("utf-8"))
        # check if the contact already contains the email address
        for email_entry in selected_vcard.get_email_addresses():
            if email_entry['value'] == email_address:
                print "The contact %s already contains the email address %s" % (selected_vcard, email_address)
                sys.exit(0)
        # ask for the email label
        print "\nAdding email address %s to contact %s" % (email_address, selected_vcard)
        label = raw_input("email label [home]: ") or "home"
        # add email address to vcard object
        selected_vcard.add_email_address(
                label.decode("utf-8"), email_address.decode("utf-8"))
        # save to disk
        selected_vcard.write_to_file(overwrite=True)
        print "Done.\n\n%s" % selected_vcard.print_vcard()
        sys.exit(0)

    # create a list of all found vcard objects
    vcard_list = Config().get_vcard_objects(selected_addressbooks, args.sort, args.reverse, search_terms[0], False)

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
        print '\n'.join(phone_list)
        if len(phone_list) == 0:
            sys.exit(1)
        sys.exit(0)

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
        print '\n'.join(address_list)
        if len(address_list) <= 1:
            sys.exit(1)
        sys.exit(0)

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
        print '\n'.join(address_list)
        if len(address_list) == 0:
            sys.exit(1)
        sys.exit(0)

    # cancel if we found no contacts
    if vcard_list.__len__() == 0:
        print "Found no contacts"
        sys.exit(0)

    # print user friendly contacts table
    if args.action == "list":
        list_contacts(selected_addressbooks, vcard_list)
        sys.exit(0)

    # show source or details, modify or delete contact
    if args.action in ["details", "modify", "remove", "source"]:
        selected_vcard = choose_vcard_from_list(selected_addressbooks, vcard_list)

        if args.action == "details":
            print selected_vcard.print_vcard()

        elif args.action == "modify":
            modify_existing_contact(selected_vcard)

        elif args.action == "remove":
            while True:
                input_string = raw_input("Deleting contact %s. Are you sure? (y/n): " \
                        % selected_vcard.get_full_name())
                if input_string.lower() in ["", "n", "q"]:
                    print "Canceled"
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
            selected_vcard.delete_vcard_file()
            print "Contact deleted successfully"

        elif args.action == "source":
            child = subprocess.Popen([Config().get_editor(),
                    selected_vcard.get_vcard_full_filename()])
            streamdata = child.communicate()[0]

    # merge two contacts
    if args.action == "merge":
        # get the first vcard, into which to merge
        # respect the users search query if available
        first_selected_vcard = choose_vcard_from_list(selected_addressbooks,
                Config().get_vcard_objects(selected_addressbooks, args.sort, args.reverse, search_terms[0], False))
        if first_selected_vcard == None:
            print("Found no contact to merge into")
            sys.exit(1)
        print("Merge into %s\n" % first_selected_vcard.get_full_name())

        # then get the second vcard, which to merge from
        # clear out the users potential serch query
        print("Now choose the vcard from which to merge:")
        second_selected_vcard = choose_vcard_from_list(selected_addressbooks,
                Config().get_vcard_objects(selected_addressbooks, args.sort, args.reverse, search_terms[1], False))
        if second_selected_vcard == None:
            print "Found no contact to merge from"
            sys.exit(1)

        # compare contacts
        if first_selected_vcard == second_selected_vcard:
            print("Selected same contact twice.")
            sys.exit(1)
        else:
            merge_existing_contacts(first_selected_vcard, second_selected_vcard)
            sys.exit(0)


if __name__ == "__main__":
    main()
