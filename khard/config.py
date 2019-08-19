# -*- coding: utf-8 -*-

import locale
import logging
import os
import re
import sys

import configobj

from .actions import Actions
from .address_book import AddressBookCollection, VdirAddressBook


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
        self.abooks = []

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
        except configobj.ConfigObjError as err:
            exit(str(err))

        # general settings
        if "general" not in self.config:
            self.config['general'] = {}

        # debug
        self._convert_boolean_config_value(self.config["general"], "debug")
        self.debug = self.config["general"]["debug"]

        # editor
        self.editor = self.config["general"].get("editor") \
            or os.environ.get("EDITOR", "vim")
        # merge editor
        self.merge_editor = self.config['general'].get("merge_editor") \
            or os.environ.get("MERGE_EDITOR", "vimdiff")

        # default action
        self.default_action = self.config["general"].get("default_action")
        if self.default_action is None:
            # When these two lines are replaced with "pass" khard requires a
            # subcommand on the command line as long as no default_action is
            # explicitly given in the config file.
            logging.warning(
                "No default_action was set in the config.  Currently this "
                "will default to default_action='list' but will require the "
                "use of a subcommand on the command line in a future version "
                "of khard.")
            self.default_action = "list"
        elif self.default_action not in Actions.get_actions():
            exit("Invalid value for default_action parameter\n"
                 "Possible values: %s" % ', '.join(
                     sorted(Actions.get_actions())))

        # contact table settings
        if "contact table" not in self.config:
            self.config['contact table'] = {}

        # sort contact table by first or last name
        self.sort = self.config["contact table"].get("sort", "first_name")
        if self.sort not in ["first_name", "last_name", "formatted_name"]:
            exit("Invalid value for sort parameter\n"
                 "Possible values: first_name, last_name, formatted_name")

        # display names in contact table by first or last name
        if "display" not in self.config['contact table']:
            # if display by name attribute is not present in the config file
            # use the sort attribute value for backwards compatibility
            self.config['contact table']['display'] = self.sort
        elif self.config['contact table']['display'] not in [
                "first_name", "last_name", "formatted_name"]:
            exit("Invalid value for display parameter\n"
                 "Possible values: first_name, last_name, formatted_name")

        # reverse contact table
        self._convert_boolean_config_value(self.config["contact table"],
                                           "reverse")
        # group contact table by address book
        self._convert_boolean_config_value(self.config["contact table"],
                                           "group_by_addressbook")
        # nickname
        self._convert_boolean_config_value(self.config["contact table"],
                                           "show_nicknames")
        # show uids
        self._convert_boolean_config_value(self.config["contact table"],
                                           "show_uids", True)
        # localize dates
        self._convert_boolean_config_value(self.config["contact table"],
                                           "localize_dates", True)

        # preferred phone number and email address types in contact table
        # phone type
        if "preferred_phone_number_type" in self.config['contact table']:
            if isinstance(self.config['contact table']['preferred_phone_number_type'], str):
                self.config['contact table']['preferred_phone_number_type'] = \
                    [self.config['contact table']['preferred_phone_number_type']]
        else:
            # default phone number type: pref
            self.config['contact table']['preferred_phone_number_type'] = ["pref"]
        # email type
        if "preferred_email_address_type" in self.config['contact table']:
            if isinstance(self.config['contact table']['preferred_email_address_type'], str):
                self.config['contact table']['preferred_email_address_type'] = \
                    [self.config['contact table']['preferred_email_address_type']]
        else:
            # default email address  type: pref
            self.config['contact table']['preferred_email_address_type'] = ["pref"]

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
                                           "search_in_source_files")
        # skip unparsable vcards
        self._convert_boolean_config_value(self.config["vcard"],
                                           "skip_unparsable")

        if "addressbooks" not in self.config:
            exit('Missing main section "[addressbooks]".')
        if not self.config['addressbooks'].keys():
            exit("No address book entries available.")

    def load_address_books(self):
        section = self.config['addressbooks']
        kwargs = {'private_objects': self.get_supported_private_objects(),
                  'localize_dates': self.localize_dates(),
                  'skip': self.skip_unparsable()}
        try:
            self.abook = AddressBookCollection(
                "tmp", [VdirAddressBook(name, section[name]['path'], **kwargs)
                        for name in section], **kwargs)
        except KeyError as err:
            exit('Missing path to the "{}" address book.'.format(err.args[0]))
        except IOError as err:
            exit(str(err))
        self.abooks = [self.abook.get_abook(name) for name in section]

    @staticmethod
    def _convert_boolean_config_value(config, name, default=False):
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

    def has_uids(self):
        return self.config['contact table']['show_uids']

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

    def preferred_phone_number_type(self):
        return self.config['contact table']['preferred_phone_number_type']

    def preferred_email_address_type(self):
        return self.config['contact table']['preferred_email_address_type']
