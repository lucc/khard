# -*- coding: utf-8 -*-

from distutils.spawn import find_executable
import locale
import logging
import os
import re
import sys

import configobj

from .actions import Actions
from .address_book import AddressBookCollection, AddressBookParseError


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
    print(prefix + message)
    sys.exit(3)


class Config:

    supported_vcard_versions = ("3.0", "4.0")

    def __init__(self, config_file=""):
        self.config = None
        self.address_book_list = []
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
        elif self.default_action not in Actions.get_actions():
            exit("Invalid value for default_action parameter\n"
                 "Possible values: %s" % ', '.join(
                     sorted(Actions.get_actions())))

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
        section = self.config['addressbooks']
        try:
            self.abook = AddressBookCollection(
                "tmp", *[(name, section[name]['path']) for name in section])
        except KeyError as err:
            exit('Missing path to the "{}" address book.'.format(err.args[0]))
        except IOError as err:
            exit(str(err))
        self.address_book_list = [self.abook.get_abook(name)
                                  for name in section]

    @staticmethod
    def _convert_boolean_config_value(config, name, default=True):
        """Convert the named field to bool.

        The current value should be one of the strings "yes" or "no".  It will
        be replaced with its boolean counterpart.  If the field is not present
        in the config object, the default value is used.

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
        :rtype: list(address_book.AddressBook)
        """
        return self.address_book_list

    def get_address_book(self, name, search_queries=None):
        """
        return address book object or None, if the address book with the
        given name does not exist
        :rtype: address_book.AddressBook
        """
        if not self.search_in_source_files():
            search_queries = None
        address_book = self.abook.get_abook(name)
        if not address_book:
            # Return None if no address book did match the given name.
            return None
        if not address_book.loaded:
            try:
                # Load vcard files of the address book.
                contacts, errors = address_book.load(
                    search_queries, self.get_supported_private_objects(),
                    self.localize_dates(), self.skip_unparsable())
                # Check uniqueness of vcard uids and create short uid
                # dictionary. This can be disabled with the show_uids option in
                # the config file, if desired.
                if self.config['contact table']['show_uids']:
                    self.uid_dict = self.abook.get_short_uid_dict(
                        search_queries, self.get_supported_private_objects(),
                        self.localize_dates(), self.skip_unparsable())
            except AddressBookParseError as err:
                if not self.skip_unparsable():
                    logging.error(
                        "The vcard file %s of address book %s could not be "
                        "parsed\nUse --debug for more information or "
                        "--skip-unparsable to proceed", err.filename, name)
                    sys.exit(2)
        return address_book

    def has_uids(self):
        return bool(self.uid_dict)

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
