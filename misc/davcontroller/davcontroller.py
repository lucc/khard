#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import argparse
from caldavclientlibrary.client.account import CalDAVAccount
from caldavclientlibrary.protocol.url import URL


def main():
    # create the args parser
    parser = argparse.ArgumentParser(
            description="Davcontroller creates, lists and removes caldav "
            "calendars and carddav address books from server")
    parser.add_argument("-v", "--version", action="store_true",
                        help="Get current program version")
    parser.add_argument("-H", "--hostname", default="")
    parser.add_argument("-p", "--port", default="")
    parser.add_argument("-u", "--username", default="")
    parser.add_argument("-P", "--password", default="")
    parser.add_argument("action", nargs="?", default="",
                        help="Actions: new-addressbook, new-calendar, list, "
                        "and remove")
    args = parser.parse_args()

    # version
    if args.version is True:
        print("davcontroller version 0.1")
        sys.exit(0)

    # check the server's parameter
    if args.hostname == "":
        print("Missing host name")
        sys.exit(1)
    if args.port == "":
        print("Missing host port")
        sys.exit(1)
    if args.username == "":
        print("Missing user name")
        sys.exit(1)
    if args.password == "":
        print("Missing password")
        sys.exit(1)

    if args.action == "":
        print("Please specify an action. Possible values are: "
              "new-addressbook, new-calendar, list and remove")
        sys.exit(1)
    elif args.action not in ["new-addressbook", "new-calendar", "list",
                             "remove"]:
        print("The specified action \"%s\" is not supported. Possible values "
              "are: new-addressbook, new-calendar, list and remove" %
              args.action)
        sys.exit(1)

    # try to connect to the caldav server
    account = CalDAVAccount(args.hostname, args.port, ssl=True,
                            user=args.username, pswd=args.password, root="/",
                            principal="")
    if account.getPrincipal() is None:
        print("Error: Connection refused")
        sys.exit(2)

    if args.action in ["list", "remove"]:
        # address books
        print("Available address books")
        addressbook_list = account.getPrincipal().listAddressBooks()
        if addressbook_list.__len__() == 0:
            print("No address books found")
        else:
            for index, addressbook in enumerate(addressbook_list):
                print("%d. %s" % (index+1, addressbook.getDisplayName()))
        print
        # calendars
        print("Available calendars")
        calendar_list = account.getPrincipal().listCalendars()
        if calendar_list.__len__() == 0:
            print("No calendars found")
        else:
            for index, calendar in enumerate(calendar_list):
                print("%d. %s" % (addressbook_list.__len__() + index + 1,
                      calendar.getDisplayName()))
        item_list = addressbook_list + calendar_list
        if item_list.__len__() == 0:
            sys.exit(2)

        if args.action == "remove":
            print
            while True:
                input_string = input("Enter Id: ")
                if input_string == "":
                    sys.exit(0)
                try:
                    id = int(input_string)
                    if id > 0 and id <= item_list.__len__():
                        break
                except ValueError:
                    pass
                print("Please enter an Id between 1 and %d or nothing to exit."
                      % item_list.__len__())
            item = item_list[id-1]
            while True:
                input_string = input("Deleting %s. Are you sure? (y/n): " %
                                     item.getDisplayName())
                if input_string.lower() in ["", "n", "q"]:
                    print("Canceled")
                    sys.exit(0)
                if input_string.lower() == "y":
                    break
            account.session.deleteResource(URL(url=item.path))

    if args.action.startswith("new-"):
        # get full host url
        host_url = "https://%s:%s" % (account.session.server,
                                      account.session.port)
        # enter new name
        if args.action == "new-addressbook":
            input_string = input("Enter new address book name or nothing to "
                                 "cancel: ")
        else:
            input_string = input("Enter new calendar name or nothing to "
                                 "cancel: ")
        if input_string == "":
            sys.exit(0)
        res_name = input_string
        res_path = input_string.replace(" ", "_").lower()
        # create new resource
        if args.action == "new-addressbook":
            u = URL(url=host_url + account.principal.adbkhomeset[0].path +
                    res_path + "/")
            account.session.makeAddressBook(u, res_name)
        else:
            u = URL(url=host_url + account.principal.homeset[0].path +
                    res_path + "/")
            account.session.makeCalendar(u, res_name)
        print("Creation successful")


if __name__ == "__main__":
    main()
