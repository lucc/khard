# -*- coding: utf-8 -*-

# singleton code comes from:
# http://code.activestate.com/recipes/52558/#as_content

from distutils.spawn import find_executable
import glob
import locale
import os
import re
import sys

import configobj
import vobject

from .actions import Actions
from .carddav_object import CarddavObject
from . import helpers
from .address_book import AddressBook


class Config:
    """ A python singleton """

    class __impl:
        """ Implementation of the singleton interface """

        def __init__(self):
            self.config = None
            self.address_book_list = []
            self.original_uid_dict = {}
            self.uid_dict = {}

            # set locale
            locale.setlocale(locale.LC_ALL, '')

            # load config file
            xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or \
                os.path.expanduser("~/.config")
            config_file = os.environ.get("KHARD_CONFIG") or \
                os.path.join(xdg_config_home, "khard", "khard.conf")
            if not os.path.exists(config_file):
                print("Config file %s not available" % config_file)
                sys.exit(2)

            # parse config file contents
            try:
                self.config = configobj.ConfigObj(
                    config_file, interpolation=False)
            except configobj.ParseError as err:
                print("Error in config file\n%s" % err)
                sys.exit(2)

            # general settings
            if "general" not in self.config:
                print('Error in config file\n'
                      'Missing main section "[general]".')
                sys.exit(2)

            # debug
            if 'debug' not in self.config['general']:
                self.config['general']['debug'] = False
            elif self.config['general']['debug'] == "yes":
                self.config['general']['debug'] = True
            elif self.config['general']['debug'] == "no":
                self.config['general']['debug'] = False
            else:
                print("Error in config file\n"
                      "Invalid value for debug parameter\n"
                      "Possible values: yes, no")
                sys.exit(2)

            # editor
            self.config['general']['editor'] = \
                self.config['general'].get("editor") \
                or os.environ.get("EDITOR")
            if self.config['general']['editor'] is None:
                print("Error in config file\n"
                      "Set path to your preferred text editor in khard's "
                      "config file or the $EDITOR shell variable\n"
                      "Example for khard.conf: editor = vim")
                sys.exit(2)
            self.config['general']['editor'] = find_executable(
                os.path.expanduser(self.config['general']['editor']))
            if self.config['general']['editor'] is None:
                print("Error in config file\n"
                      "Invalid editor path or executable not found.")
                sys.exit(2)

            # merge editor
            self.config['general']['merge_editor'] = \
                self.config['general'].get("merge_editor") \
                or os.environ.get("MERGE_EDITOR")
            if self.config['general']['merge_editor'] is None:
                print("Error in config file\nSet path to your preferred text "
                      "merge editor in khard's config file or the "
                      "$MERGE_EDITOR shell variable\n"
                      "Example for khard.conf: merge_editor = vimdiff")
                sys.exit(2)
            self.config['general']['merge_editor'] = find_executable(
                os.path.expanduser(self.config['general']['merge_editor']))
            if self.config['general']['merge_editor'] is None:
                print("Error in config file\n"
                      "Invalid merge editor path or executable not found.")
                sys.exit(2)

            # default action
            if "default_action" not in self.config['general']:
                print("Error in config file\n"
                      "Missing default action parameter.")
                sys.exit(2)
            elif self.config['general']['default_action'] not in \
                    Actions.get_list_of_all_actions():
                print("Error in config file\nInvalid value for default_action "
                      "parameter\nPossible values: %s" % ', '.join(
                          sorted(Actions.get_list_of_all_actions())))
                sys.exit(2)

            # contact table settings
            if "contact table" not in self.config:
                self.config['contact table'] = {}

            # sort contact table by first or last name
            if "sort" not in self.config['contact table']:
                self.config['contact table']['sort'] = "first_name"
            elif self.config['contact table']['sort'] not in \
                    ["first_name", "last_name"]:
                print("Error in config file\n"
                      "Invalid value for sort parameter\n"
                      "Possible values: first_name, last_name")
                sys.exit(2)

            # display names in contact table by first or last name
            if "display" not in self.config['contact table']:
                # if display by name attribute is not present in the config
                # file use the sort attribute value for backwards compatibility
                self.config['contact table']['display'] = \
                        self.config['contact table']['sort']
            elif self.config['contact table']['display'] not in \
                    ["first_name", "last_name"]:
                print("Error in config file\n"
                      "Invalid value for display parameter\n"
                      "Possible values: first_name, last_name")
                sys.exit(2)

            # reverse contact table
            if 'reverse' not in self.config['contact table']:
                self.config['contact table']['reverse'] = False
            elif self.config['contact table']['reverse'] == "yes":
                self.config['contact table']['reverse'] = True
            elif self.config['contact table']['reverse'] == "no":
                self.config['contact table']['reverse'] = False
            else:
                print("Error in config file\n"
                      "Invalid value for reverse parameter\n"
                      "Possible values: yes, no")
                sys.exit(2)

            # group contact table by address book
            if "group_by_addressbook" not in self.config['contact table']:
                self.config['contact table']['group_by_addressbook'] = False
            elif self.config['contact table']['group_by_addressbook'] == "yes":
                self.config['contact table']['group_by_addressbook'] = True
            elif self.config['contact table']['group_by_addressbook'] == "no":
                self.config['contact table']['group_by_addressbook'] = False
            else:
                print("Error in config file\n"
                      "Invalid value for group_by_addressbook parameter\n"
                      "Possible values: yes, no")
                sys.exit(2)

            # nickname
            if "show_nicknames" not in self.config['contact table']:
                self.config['contact table']['show_nicknames'] = False
            elif self.config['contact table']['show_nicknames'] == "yes":
                self.config['contact table']['show_nicknames'] = True
            elif self.config['contact table']['show_nicknames'] == "no":
                self.config['contact table']['show_nicknames'] = False
            else:
                print("Error in config file\n"
                      "Invalid value for show_nicknames parameter\n"
                      "Possible values: yes, no")
                sys.exit(2)

            # show uids
            if "show_uids" not in self.config['contact table']:
                self.config['contact table']['show_uids'] = True
            elif self.config['contact table']['show_uids'] == "yes":
                self.config['contact table']['show_uids'] = True
            elif self.config['contact table']['show_uids'] == "no":
                self.config['contact table']['show_uids'] = False
            else:
                print("Error in config file\n"
                      "Invalid value for show_uids parameter\n"
                      "Possible values: yes, no")
                sys.exit(2)

            # vcard settings
            if "vcard" not in self.config:
                self.config['vcard'] = {}

            # get supported private objects
            if "private_objects" not in self.config['vcard']:
                self.config['vcard']['private_objects'] = []
            else:
                # check if object only contains letters, digits or -
                for object in self.config['vcard']['private_objects']:
                    if object != re.sub("[^a-zA-Z0-9-]", "", object):
                        print("Error in config file\n"
                              "private object %s may only contain letters, "
                              "digits and the \"-\" character." % object)
                        sys.exit(2)
                    if object == re.sub("[^-]", "", object) \
                            or object.startswith("-") \
                            or object.endswith("-"):
                        print("Error in config file\n"
                              "A \"-\" in a private object label must be "
                              "at least surrounded by one letter or digit.")
                        sys.exit(2)

            # preferred vcard version
            if "preferred_version" not in self.config['vcard']:
                self.config['vcard']['preferred_version'] = "3.0"
            elif self.config['vcard']['preferred_version'] not in \
                    self.get_supported_vcard_versions():
                print("Error in config file\n"
                      "Invalid value for preferred_version parameter\n"
                      "Possible values: %s"
                      % self.get_supported_vcard_versions())
                sys.exit(2)

            # speed up program by pre-searching in the vcard source files
            if 'search_in_source_files' not in self.config['vcard']:
                self.config['vcard']['search_in_source_files'] = False
            elif self.config['vcard']['search_in_source_files'] == "yes":
                self.config['vcard']['search_in_source_files'] = True
            elif self.config['vcard']['search_in_source_files'] == "no":
                self.config['vcard']['search_in_source_files'] = False
            else:
                print("Error in config file\n"
                      "Invalid value for search_in_source_files parameter\n"
                      "Possible values: yes, no")
                sys.exit(2)

            # skip unparsable vcards
            if 'skip_unparsable' not in self.config['vcard']:
                self.config['vcard']['skip_unparsable'] = False
            elif self.config['vcard']['skip_unparsable'] == "yes":
                self.config['vcard']['skip_unparsable'] = True
            elif self.config['vcard']['skip_unparsable'] == "no":
                self.config['vcard']['skip_unparsable'] = False
            else:
                print("Error in config file\n"
                      "Invalid value for skip_unparsable parameter\n"
                      "Possible values: yes, no")
                sys.exit(2)

            # load address books
            if "addressbooks" not in self.config:
                print('Error in config file\n'
                      'Missing main section "[addressbooks]".')
                sys.exit(2)
            if len(self.config['addressbooks'].keys()) == 0:
                print("Error in config file\n"
                      "No address book entries available.")
                sys.exit(2)
            for name in self.config['addressbooks'].keys():
                # create address book object
                try:
                    address_book = AddressBook(
                        name, self.config['addressbooks'][name]['path'])
                except KeyError as e:
                    print("Error in config file\n"
                          "Missing path to the \"%s\" address book." % name)
                    sys.exit(2)
                except IOError as e:
                    print("Error in config file\n%s" % e)
                    sys.exit(2)
                else:
                    # add address book to list
                    self.address_book_list.append(address_book)

        def get_all_address_books(self):
            """
            return a list of all address books from config file
            But due to performance optimizations its not guaranteed, that the
            address books already contain their contact objects
            if you must be sure, get every address book individually with the
            get_address_book() function below
            :rtype: list(AddressBook)
            """
            return self.address_book_list

        def get_address_book(self, name, search_queries=None):
            """
            return address book object or None, if the address book with the
            given name does not exist
            :rtype: AddressBook
            """
            for address_book in self.address_book_list:
                if name == address_book.get_name():
                    if not address_book.loaded:
                        number_of_contacts = 0
                        error_counter = 0
                        # load vcard files of address book
                        filename_list = []
                        for filename in glob.glob(os.path.join(
                                address_book.get_path(), "*.vcf")):
                            if search_queries \
                                    and self.search_in_source_files():
                                with open(filename, "r") as f:
                                    if re.search(search_queries, f.read(),
                                                 re.IGNORECASE | re.DOTALL):
                                        filename_list.append(filename)
                            else:
                                filename_list.append(filename)

                        # create CarddavObject
                        for filename in filename_list:
                            number_of_contacts += 1
                            try:
                                address_book.add_contact(
                                    CarddavObject.from_file(
                                        address_book, filename,
                                        self.get_supported_private_objects()))
                            except IOError as e:
                                if self.debug():
                                    print("Error: Could not open file %s\n%s"
                                          % (filename, e))
                                error_counter += 1
                            except Exception as e:
                                if self.debug():
                                    print("Error: Could not parse file %s\n%s"
                                            % (filename, e))
                                error_counter += 1

                        # check if one or more contacts could not be parsed
                        if error_counter > 0:
                            if self.debug():
                                print("\n%d of %d vcard files of address book "
                                        "%s could not be parsed"
                                        % (error_counter, number_of_contacts,
                                            name))
                            elif not self.skip_unparsable():
                                print("%d of %d vcard files of address book "
                                        "%s could not be parsed\nUse "
                                        "--debug for more information "
                                        "or --skip-unparsable to proceed"
                                        % (error_counter, number_of_contacts,
                                            name))
                            if self.skip_unparsable():
                                if self.debug():
                                    print("")
                            else:
                                sys.exit(2)

                        # check uniqueness of vcard uids and create short uid
                        # dictionary that can be disabled with the show_uids
                        # option in the config file, if desired
                        if self.config['contact table']['show_uids']:
                            # check, if multiple contacts have the same uid
                            for contact in address_book.get_contact_list():
                                uid = contact.get_uid()
                                if bool(uid):
                                    matching_contact = \
                                            self.original_uid_dict.get(uid)
                                    if matching_contact is None:
                                        self.original_uid_dict[uid] = contact
                                    else:
                                        print(
                                            "The contact %s from address book "
                                            "%s and the contact %s from "
                                            "address book %s have the same "
                                            "uid %s" % (
                                                matching_contact.get_full_name(),
                                                matching_contact.get_address_book().get_name(),
                                                contact.get_full_name(),
                                                contact.get_address_book().get_name(),
                                                contact.get_uid())
                                            )
                                        sys.exit(2)
                            # rebuild shortened uid dictionary
                            self.create_shortened_uid_dictionary()
                        address_book.loaded = True
                    return address_book
            return None

        def has_uids(self):
            return len(self.uid_dict.keys()) > 0

        def create_shortened_uid_dictionary(self):
            # uniqueness of uids is guaranteed but they are much to long for
            # the -u / --uid command line option
            #
            # Therefore clear previously filled uid_dict and recreate with the
            # shortest possible uids, so they are still unique but much handier
            #
            # with around 100 contacts that short id should not be longer
            # then two or three characters
            self.uid_dict.clear()
            flat_contact_list = sorted(
                self.original_uid_dict.values(),
                key=lambda x: x.get_uid())
            if len(flat_contact_list) == 1:
                current = flat_contact_list[0]
                self.uid_dict[current.get_uid()[:1]] = current
            elif len(flat_contact_list) > 1:
                # first list element
                current = flat_contact_list[0]
                next = flat_contact_list[1]
                same = helpers.compare_uids(current.get_uid(), next.get_uid())
                self.uid_dict[current.get_uid()[:same+1]] = current
                # list elements 1 to len(flat_contact_list)-1
                for index in range(1, len(flat_contact_list)-1):
                    prev = flat_contact_list[index-1]
                    current = flat_contact_list[index]
                    next = flat_contact_list[index+1]
                    same = max(helpers.compare_uids(prev.get_uid(),
                                                    current.get_uid()),
                               helpers.compare_uids(current.get_uid(),
                                                    next.get_uid()))
                    self.uid_dict[current.get_uid()[:same+1]] = current
                # last list element
                prev = flat_contact_list[-2]
                current = flat_contact_list[-1]
                same = helpers.compare_uids(prev.get_uid(), current.get_uid())
                self.uid_dict[current.get_uid()[:same+1]] = current

        def get_shortened_uid(self, uid):
            if bool(uid):
                for length_of_uid in range(len(uid), 0, -1):
                    if self.uid_dict.get(uid[:length_of_uid]) is not None:
                        return uid[:length_of_uid]
            return ""

        def debug(self):
            return self.config['general']['debug']

        def set_debug(self, bool):
            self.config['general']['debug'] = bool

        def get_editor(self):
            return self.config['general']['editor']

        def get_merge_editor(self):
            return self.config['general']['merge_editor']

        def get_default_action(self):
            return self.config['general']['default_action']

        def get_supported_private_objects(self):
            return self.config['vcard']['private_objects']

        def get_supported_vcard_versions(self):
            return ["3.0", "4.0"]

        def get_preferred_vcard_version(self):
            return self.config['vcard']['preferred_version']

        def set_preferred_vcard_version(self, vcard_version):
            self.config['vcard']['preferred_version'] = vcard_version

        def search_in_source_files(self):
            return self.config['vcard']['search_in_source_files']

        def set_search_in_source_files(self, bool):
            self.config['vcard']['search_in_source_files'] = bool

        def skip_unparsable(self):
            return self.config['vcard']['skip_unparsable']

        def set_skip_unparsable(self, bool):
            self.config['vcard']['skip_unparsable'] = bool

        def display_by_name(self):
            return self.config['contact table']['display']

        def set_display_by_name(self, criteria):
            self.config['contact table']['display'] = criteria

        def sort_by_name(self):
            return self.config['contact table']['sort']

        def set_sort_by_name(self, criteria):
            self.config['contact table']['sort'] = criteria

        def group_by_addressbook(self):
            return self.config['contact table']['group_by_addressbook']

        def set_group_by_addressbook(self, bool):
            self.config['contact table']['group_by_addressbook'] = bool

        def reverse(self):
            return self.config['contact table']['reverse']

        def set_reverse(self, bool):
            self.config['contact table']['reverse'] = bool

        def show_nicknames(self):
            return self.config['contact table']['show_nicknames']

    ####################################
    # storage for the instance reference
    ####################################
    __instance = None

    def __init__(self):
        """ Create singleton instance """
        # Check whether we already have an instance
        if Config.__instance is None:
            # Create and remember instance
            Config.__instance = Config.__impl()
        # Store instance reference as the only member in the handle
        self.__dict__['_Config__instance'] = Config.__instance

    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """ Delegate access to implementation """
        return setattr(self.__instance, attr, value)
