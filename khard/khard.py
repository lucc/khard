#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import tempfile, subprocess, os, sys, re
import argparse
import helpers
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


def main():
    # create the args parser
    parser = argparse.ArgumentParser(description="Khard is a carddav address book for the console")
    parser.add_argument("-a", "--addressbook", default="",
            help="Specify address book names as comma separated list")
    parser.add_argument("-r", "--reverse", action="store_true", help="Sort contacts in reverse order")
    parser.add_argument("-s", "--search", default="", help="Search for contacts")
    parser.add_argument("-t", "--sort", default="alphabetical", 
            help="Sort contacts list. Possible values: alphabetical, addressbook")
    parser.add_argument("-v", "--version", action="store_true", help="Get current program version")
    parser.add_argument("action", nargs="?", default="",
            help="Possible actions: list, details, mutt, alot, twinkle, new, modify, remove and source")
    args = parser.parse_args()

    # version
    if args.version == True:
        print "Khard version %s" % khard_version
        sys.exit(0)

    # validate value for action
    if args.action == "":
        args.action = Config().get_default_action()
    if args.action not in ["list", "details", "mutt", "alot", "twinkle", "new", "modify", "remove", "source"]:
        print "Unsupported action. Possible values are: list, details, mutt, alot, twinkle, new, modify, remove and source"
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

    # sort criteria
    if args.sort not in ["alphabetical", "addressbook"]:
        print "Unsupported sort criteria. Possible values: alphabetical, addressbook"
        sys.exit(1)

    # create a list of all found vcard objects
    vcard_list = Config().get_vcard_objects(selected_addressbooks, args.sort, args.reverse, args.search)
    
    # create new contact
    if args.action == "new":
        if selected_addressbooks.__len__() != 1:
            print "Error: You must specify an address book, in which the new \
                    contact should be added. Possible values are: %s" \
                    % ', '.join(addressbooks.keys())
            sys.exit(1)
        create_new_contact(addressbooks[selected_addressbooks[0]])
        sys.exit(0)

    # print mutt friendly contacts table
    if args.action == "mutt":
        address_list = ["searching for '%s' ..." % args.search]
        for vcard in vcard_list:
            for email_entry in vcard.get_email_addresses():
                address_list.append("%s\t%s\t%s" % (email_entry['value'],
                        vcard.get_full_name(), email_entry['type']))
        print '\n'.join(address_list)
        if vcard_list.__len__() == 0:
            sys.exit(1)
        sys.exit(0)

    # print alot friendly contacts table
    if args.action == "alot":
        address_list = []
        for vcard in vcard_list:
            for email_entry in vcard.get_email_addresses():
                full = "%s %s" % (vcard.get_full_name(), email_entry['type'])
                address_list.append("\"%s\" <%s>" % (full, email_entry['value']))
        print '\n'.join(address_list)
        sys.exit(0)

    # print twinkle  friendly contacts table
    if args.action == "twinkle":
        if args.search == "":
            print "Error: Please use the -s option to search for a phone number"
            sys.exit(1)
        if vcard_list.__len__() > 0:
            vcard = vcard_list[0]
            if vcard.get_phone_numbers().__len__() == 1:
                print vcard.get_full_name()
            elif vcard.get_phone_numbers().__len__() > 1:
                # search for the phone label, if the contact has more than one phone number
                type = ""
                regexp = re.compile(args.search.replace(" ", ".*"), re.IGNORECASE)
                for phone_entry in vcard.get_phone_numbers():
                    if regexp.search(phone_entry['value'].replace(" ","")) != None:
                        type = phone_entry['type']
                        break
                if type == "":
                    print vcard.get_full_name()
                else:
                    print "%s (%s)" % (vcard.get_full_name(), type)
        sys.exit(0)

    # cancel if we found no contacts
    if vcard_list.__len__() == 0:
        print "No contacts found"
        sys.exit(0)

    # print user friendly contacts table
    if args.action == "list":
        list_contacts(selected_addressbooks, vcard_list)
        sys.exit(0)

    # show source or details, modify or delete contact
    if args.action in ["details", "modify", "remove", "source"]:
        if vcard_list.__len__() == 1:
            selected_vcard = vcard_list[0]
        else:
            list_contacts(selected_addressbooks, vcard_list)
            while True:
                input_string = raw_input("Enter Id: ")
                if input_string == "":
                    sys.exit(0)
                try:
                    vcard_id = int(input_string)
                    if vcard_id > 0 and vcard_id <= vcard_list.__len__():
                        break
                except ValueError as e:
                    pass
                print "Please enter an Id between 1 and %d or nothing to exit." % vcard_list.__len__()
            print ""
            selected_vcard = vcard_list[vcard_id-1]
    
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

if __name__ == "__main__":
    main()
