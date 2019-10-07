# -*- coding: utf-8 -*-

import locale
import logging
import os
import re
import shlex
import sys

import configobj
import validate

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


def validate_command(value):
    """Special validator to check shell commands

    The input must either be a list of strings or a string that shlex.split can
    parse into such.

    :param value: the config value to validate
    :returns: the command after validation
    :rtype: list(str)
    :raises: validate.ValidateError
    """
    logging.debug("validating %s", value)
    try:
        return validate.is_string_list(value)
    except validate.VdtTypeError:
        logging.debug('continue with %s', value)
        if isinstance(value, str):
            try:
                return shlex.split(value)
            except ValueError as err:
                raise validate.ValidateError(
                    'Error when parsing shell command {}\n{}'.format(
                        value, err))
        raise


class Config:

    supported_vcard_versions = ("3.0", "4.0")

    def __init__(self, config_file=""):
        self.config = None
        self.abooks = []

        # set locale
        locale.setlocale(locale.LC_ALL, '')

        self.config = self._load_config_file(config_file)

        self.debug = self.config["general"]["debug"]
        self.editor = self.config["general"]["editor"] \
            or os.environ.get("EDITOR", "vim")
        self.merge_editor = self.config['general']["merge_editor"] \
            or os.environ.get("MERGE_EDITOR", "vimdiff")

        # default action
        self.default_action = self.config["general"]["default_action"]
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

        self.sort = self.config["contact table"]["sort"]
        if "display" not in self.config['contact table']:
            # if display by name attribute is not present in the config file
            # use the sort attribute value for backwards compatibility
            self.config['contact table']['display'] = self.sort

        # check if object only contains letters, digits or -
        for object in self.config['vcard']['private_objects']:
            if object != re.sub("[^a-zA-Z0-9-]", "", object):
                exit("private object %s may only contain letters, digits and "
                     "the \"-\" character." % object)
            if object == re.sub("[^-]", "", object) or object.startswith("-") \
                    or object.endswith("-"):
                exit("A \"-\" in a private object label must be at least "
                     "surrounded by one letter or digit.")

        if not self.config['addressbooks'].keys():
            exit("No address book entries available.")

    def _load_config_file(self, config_file):
        """Find, load and validate the config file.

        :param str config_file: the path to the config file to load
        :returns: the validated config file
        """
        # find config file
        if config_file == "":
            xdg_config_home = os.getenv("XDG_CONFIG_HOME",
                                        os.path.expanduser("~/.config"))
            config_file = os.getenv("KHARD_CONFIG", os.path.join(
                xdg_config_home, "khard", "khard.conf"))
        if not os.path.exists(config_file):
            exit("Config file %s not available" % config_file, prefix="")

        spec_file = os.path.join(os.path.dirname(__file__), 'data',
                                 'config.spec')
        # parse config file contents
        try:
            config = configobj.ConfigObj(
                infile=config_file, configspec=spec_file, interpolation=False)
        except configobj.ConfigObjError as err:
            exit(str(err))
        return self._validate(config)

    def _validate(self, config):
        vdr = validate.Validator()
        vdr.functions.update({'command': validate_command})
        result = config.validate(vdr, preserve_errors=True)
        result = configobj.flatten_errors(config, result)
        for path, key, exception in result:
            logging.error("Error in config file, %s: %s",
                          ".".join([*path, key]), exception)
        if result:
            sys.exit(3)
        return config

    def load_address_books(self):
        section = self.config['addressbooks']
        kwargs = {'private_objects': self.get_supported_private_objects(),
                  'localize_dates': self.localize_dates(),
                  'skip': self.skip_unparsable()}
        try:
            self.abook = AddressBookCollection(
                "tmp", [VdirAddressBook(name, section[name]['path'], **kwargs)
                        for name in section], **kwargs)
        except IOError as err:
            exit(str(err))
        self.abooks = [self.abook.get_abook(name) for name in section]

    def merge(self, other):
        """Merge the config with some other dict or ConfigObj

        :param other: the other dict or ConfigObj to merge into self
        :returns: None
        """
        self.config.merge(other)
        self._validate(self.config)

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
