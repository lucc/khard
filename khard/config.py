# -*- coding: utf-8 -*-

# singleton code comes from:
# http://code.activestate.com/recipes/52558/#as_content

from distutils.spawn import find_executable
import locale
import logging
import os
import re
import sys

import configobj

from .actions import Actions
from .address_book import AddressBook
from . import helpers


def exit(message, prefix="Error in config file\n"):
    """Exit with a message and a return code indicating an error in the config
    file.

    This function doesn't return, it calls sys.exit.

    :param message: the message to print
    :type message: str
    :param prefix: the prefix to put in front of the message
    :type prefix: str
    :returns: does not return

    """
    print(prefix+message)
    sys.exit(3)


class Config:

    supported_vcard_versions = ("3.0", "4.0")

    def __init__(self, config_file=""):
        self.config = None
        self.address_book_list = []
        self.original_uid_dict = {}
        self.uid_dict = {}

        # set locale
        locale.setlocale(locale.LC_ALL, '')

        # load config file
        if config_file == "":
            xdg_config_home = os.getenv("XDG_CONFIG_HOME",
                                        os.path.expanduser("~/.config"))
            config_file = os.getenv("KHARD_CONFIG", os.path.join(
                xdg_config_home, "khard", "khard.conf"))
        if not os.path.exists(config_file):
            exit("Config file %s not available" % config_file, prefix="")

        # parse config file contents
        try:
            self.config = configobj.ConfigObj(config_file, interpolation=False)
        except configobj.ParseError as err:
            exit(str(err))

        # general settings
        if "general" not in self.config:
            self.config['general'] = {}

        # debug
        self._convert_boolean_config_value(self.config["general"],
                                           "debug", False)
        self.debug = self.config["general"]["debug"]

        # editor
        self.editor = self.config["general"].get("editor") \
            or os.environ.get("EDITOR")
        if self.editor is None:
            exit("Set path to your preferred text editor in khard's config "
                 "file or the $EDITOR shell variable\n"
                 "Example for khard.conf: editor = vim")
        self.editor = find_executable(os.path.expanduser(self.editor))
        if self.editor is None:
            exit("Invalid editor path or executable not found.")

        # merge editor
        self.merge_editor = self.config['general'].get("merge_editor") \
            or os.environ.get("MERGE_EDITOR")
        if self.merge_editor is None:
            exit("Set path to your preferred text merge editor in khard's "
                 "config file or the $MERGE_EDITOR shell variable\n"
                 "Example for khard.conf: merge_editor = vimdiff")
        self.merge_editor = find_executable(os.path.expanduser(
            self.merge_editor))
        if self.merge_editor is None:
            exit("Invalid merge editor path or executable not found.")

        # default action
        self.default_action = self.config["general"].get("default_action", "list")
        if self.default_action is None:
            exit("Missing default action parameter.")
        elif self.default_action not in Actions.get_list_of_all_actions():
            exit("Invalid value for default_action parameter\n"
                 "Possible values: %s" % ', '.join(
                     sorted(Actions.get_list_of_all_actions())))

        # contact table settings
        if "contact table" not in self.config:
            self.config['contact table'] = {}

        # sort contact table by first or last name
        self.sort = self.config["contact table"].get("sort", "first_name")
        if self.sort not in ["first_name", "last_name"]:
            exit("Invalid value for sort parameter\n"
                 "Possible values: first_name, last_name")

        # display names in contact table by first or last name
        if "display" not in self.config['contact table']:
            # if display by name attribute is not present in the config file
            # use the sort attribute value for backwards compatibility
            self.config['contact table']['display'] = self.sort
        elif self.config['contact table']['display'] not in ["first_name",
                                                             "last_name"]:
            exit("Invalid value for display parameter\n"
                 "Possible values: first_name, last_name")

        # reverse contact table
        self._convert_boolean_config_value(self.config["contact table"],
                                           "reverse", False)
        # group contact table by address book
        self._convert_boolean_config_value(self.config["contact table"],
                                           "group_by_addressbook", False)
        # nickname
        self._convert_boolean_config_value(self.config["contact table"],
                                           "show_nicknames", False)
        # show uids
        self._convert_boolean_config_value(self.config["contact table"],
                                           "show_uids", True)
        # localize dates
        self._convert_boolean_config_value(self.config["contact table"],
                                           "localize_dates", True)

        # vcard settings
        if "vcard" not in self.config:
            self.config['vcard'] = {}

        # get supported private objects
        if "private_objects" not in self.config['vcard'] \
                or not self.config['vcard']['private_objects']:
            self.config['vcard']['private_objects'] = []
        else:
            if not isinstance(self.config['vcard']['private_objects'], list):
                self.config['vcard']['private_objects'] = [
                    self.config['vcard']['private_objects']]
            # check if object only contains letters, digits or -
            for object in self.config['vcard']['private_objects']:
                if object != re.sub("[^a-zA-Z0-9-]", "", object):
                    exit("private object %s may only contain letters, digits "
                         "and the \"-\" character." % object)
                if object == re.sub("[^-]", "", object) \
                        or object.startswith("-") or object.endswith("-"):
                    exit("A \"-\" in a private object label must be at least "
                         "surrounded by one letter or digit.")

        # preferred vcard version
        if "preferred_version" not in self.config['vcard']:
            self.config['vcard']['preferred_version'] = "3.0"
        elif self.config['vcard']['preferred_version'] not in \
                self.supported_vcard_versions:
            exit("Invalid value for preferred_version parameter\n"
                 "Possible values: %s" % self.supported_vcard_versions)

        # speed up program by pre-searching in the vcard source files
        self._convert_boolean_config_value(self.config["vcard"],
                                           "search_in_source_files", False)
        # skip unparsable vcards
        self._convert_boolean_config_value(self.config["vcard"],
                                           "skip_unparsable", False)

        # load address books
        if "addressbooks" not in self.config:
            exit('Missing main section "[addressbooks]".')
        if not self.config['addressbooks'].keys():
            exit("No address book entries available.")
        for name in self.config['addressbooks'].keys():
            # create address book object
            try:
                address_book = AddressBook(
                    name, self.config['addressbooks'][name]['path'])
            except KeyError:
                exit("Missing path to the \"%s\" address book." % name)
            except IOError as err:
                exit(str(err))
            else:
                # add address book to list
                self.address_book_list.append(address_book)

    @staticmethod
    def _convert_boolean_config_value(config, name, default=True):
        """Convert the named field to a bool represented by its previous string
        value.  If no such field was present use the default.

        :param config: the config section where to set the option
        :type config: configobj.ConfigObj
        :param name: the name of the option to convert
        :type name: str
        :param default: the default value to use if the option was not
            previously set
        :type default: bool
        :returns: None

        """
        if name not in config:
            config[name] = default
        elif config[name] == "yes":
            config[name] = True
        elif config[name] == "no":
            config[name] = False
        else:
            raise ValueError("Error in config file\nInvalid value for %s "
                             "parameter\nPossible values: yes, no" % name)

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
        if not self.search_in_source_files():
            search_queries = None
        for address_book in self.address_book_list:
            if name == address_book.name:
                if not address_book.loaded:
                    # load vcard files of address book
                    contacts, errors = address_book.load_all_vcards(
                        self.get_supported_private_objects(),
                        self.localize_dates(), search_queries)

                    # check if one or more contacts could not be parsed
                    if errors > 0:
                        if not self.skip_unparsable():
                            logging.error(
                                "%d of %d vcard files of address book %s "
                                "could not be parsed\nUse --debug for more "
                                "information or --skip-unparsable to proceed",
                                errors, contacts, name)
                            sys.exit(2)
                        else:
                            logging.debug(
                                "\n%d of %d vcard files of address book %s "
                                "could not be parsed\n", errors, contacts, name)

                    # Check uniqueness of vcard uids and create short uid
                    # dictionary that can be disabled with the show_uids option
                    # in the config file, if desired.
                    if self.config['contact table']['show_uids']:
                        # check, if multiple contacts have the same uid
                        for contact in address_book.contact_list:
                            uid = contact.get_uid()
                            if uid:
                                matching_contact = self.original_uid_dict.get(
                                    uid)
                                if matching_contact is None:
                                    self.original_uid_dict[uid] = contact
                                else:
                                    exit("The contact %s from address book %s "
                                         "and the contact %s from address book "
                                         "%s have the same uid %s" % (
                                             matching_contact.get_full_name(),
                                             matching_contact.address_book.name,
                                             contact.get_full_name(),
                                             contact.address_book.name,
                                             contact.get_uid()), prefix="")
                        # rebuild shortened uid dictionary
                        self._create_shortened_uid_dictionary()
                return address_book
        # Return None if no address book did match the given name.
        return None

    def has_uids(self):
        return len(self.uid_dict.keys()) > 0

    def _create_shortened_uid_dictionary(self):
        # uniqueness of uids is guaranteed but they are much to long for the -u
        # / --uid command line option
        #
        # Therefore clear previously filled uid_dict and recreate with the
        # shortest possible uids, so they are still unique but much handier
        #
        # with around 100 contacts that short id should not be longer then two
        # or three characters
        self.uid_dict.clear()
        flat_contact_list = sorted(self.original_uid_dict.values(),
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
        if uid:
            for length_of_uid in range(len(uid), 0, -1):
                if self.uid_dict.get(uid[:length_of_uid]) is not None:
                    return uid[:length_of_uid]
        return ""

    def localize_dates(self):
        return self.config['contact table']['localize_dates']

    def get_supported_private_objects(self):
        return self.config['vcard']['private_objects']

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
