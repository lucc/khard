"""Loading and validation of the configuration file"""

import locale
import logging
import os
import re
import shlex
import sys

import configobj
import validate

from .actions import Actions
from .address_book import AddressBookCollection, AddressBookNameError, \
    VdirAddressBook


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
                    'Error when parsing shell command "{}": {}'.format(
                        value, err))
        raise


def validate_action(value):
    """Check that the given value is a valid action.

    :param value: the config value to check
    :returns: the same value
    :rtype: str
    :raises: validate.ValidateError
    """
    return validate.is_option(value, *Actions.get_actions())


def validate_private_objects(value):
    """Check that the private objects are reasonable

    :param value: the config value to check
    :returns: the list of private objects
    :rtype: list(str)
    :raises: validate.ValidateError
    """
    value = validate.is_string_list(value)
    for obj in value:
        if re.search("[^a-z0-9-]", obj, re.IGNORECASE):
            raise validate.ValidateError(
                'Private objects may only contain letters, digits and the'
                ' \"-\" character.')
        if obj.startswith("-") or obj.endswith("-"):
            raise validate.ValidateError(
                "A \"-\" in a private object label must be at least "
                "surrounded by one letter or digit.")
    return value


class Config:
    """Parse and validate the config file with configobj."""

    supported_vcard_versions = ("3.0", "4.0")
    SPEC_FILE = os.path.join(os.path.dirname(__file__), 'data', 'config.spec')

    def __init__(self, config_file=None):
        self.config = None
        self.abooks = None
        locale.setlocale(locale.LC_ALL, '')
        config = self._load_config_file(config_file)
        self.config = self._validate(config)
        self._set_attributes()

    @classmethod
    def _load_config_file(cls, config_file):
        """Find and load the config file.

        :param str config_file: the path to the config file to load
        :returns: the loaded config file
        """
        if not config_file:
            xdg_config_home = os.getenv("XDG_CONFIG_HOME",
                                        os.path.expanduser("~/.config"))
            config_file = os.getenv("KHARD_CONFIG", os.path.join(
                xdg_config_home, "khard", "khard.conf"))
        try:
            return configobj.ConfigObj(
                infile=config_file, configspec=cls.SPEC_FILE,
                interpolation=False, file_error=True)
        except configobj.ConfigObjError as err:
            exit(str(err))

    @staticmethod
    def _validate(config):
        vdr = validate.Validator()
        vdr.functions.update({'command': validate_command,
                              'action': validate_action,
                              'private_objects': validate_private_objects})
        result = config.validate(vdr, preserve_errors=True)
        result = configobj.flatten_errors(config, result)
        if not config['addressbooks'].keys():
            result.append((['addressbooks'], '__any__',
                           'No address book entries available'))
        for path, key, exception in result:
            logging.error("Error in config file, %s: %s",
                          ".".join([*path, key]), exception)
        if result:
            sys.exit(3)
        return config

    def _set_attributes(self):
        """Set the attributes from the internal config instance on self.

        :returns: None
        """
        general = self.config["general"]
        self.debug = general["debug"]
        self.editor = general["editor"] or os.environ.get("EDITOR", "vim")
        self.merge_editor = general["merge_editor"] \
            or os.environ.get("MERGE_EDITOR", "vimdiff")
        self.default_action = general["default_action"]
        table = self.config["contact table"]
        vcard = self.config["vcard"]
        self.sort = table["sort"]
        # if display by name attribute is not present in the config file use
        # the sort attribute value for backwards compatibility
        self.display = table.get("display", self.sort)
        self.localize_dates = table['localize_dates']
        self.private_objects = vcard['private_objects']
        self.preferred_vcard_version = vcard['preferred_version']
        self.search_in_source_files = vcard['search_in_source_files']
        self.skip_unparsable = vcard['skip_unparsable']
        self.group_by_addressbook = table['group_by_addressbook']
        self.reverse = table['reverse']
        self.show_nicknames = table['show_nicknames']
        self.preferred_email_address_type = table['preferred_email_address_type']
        self.preferred_phone_number_type = table['preferred_phone_number_type']
        self.show_uids = table['show_uids']

    def init_address_books(self):
        """Initialize the internal address book collection.

        This method should only be called *after* merging in the command line
        options as they can hold some options that are relevant for the loading
        of the address books.

        :returns: None
        """
        section = self.config['addressbooks']
        kwargs = {'private_objects': self.private_objects,
                  'localize_dates': self.localize_dates,
                  'skip': self.skip_unparsable}
        try:
            self.abooks = AddressBookCollection(
                "tmp", [VdirAddressBook(name, section[name]['path'], **kwargs)
                        for name in section], **kwargs)
        except IOError as err:
            exit(str(err))

    def get_address_books(self, names, queries):
        """Load all address books with the given names.

        :param list(str) names: the address books to load
        :param dict queries: a mapping of address book names to search queries
        :yields: the loaded address books
        :ytype: addressbook.AddressBook
        """
        all_names = {str(book) for book in self.abooks}
        if not names:
            names = all_names
        elif not all_names.issuperset(names):
            raise AddressBookNameError(
                "The following address books are not defined: {}".format(
                    ', '.join(set(names) - all_names)))
        # load address books which are defined in the configuration file
        for name in names:
            address_book = self.abooks[name]
            address_book.load(
                queries[name],
                search_in_source_files=self.search_in_source_files)
            yield address_book

    def merge(self, other):
        """Merge the config with some other dict or ConfigObj

        :param other: the other dict or ConfigObj to merge into self
        :returns: None
        """
        self.config.merge(other)
        self._validate(self.config)
        self._set_attributes()

    def merge_args(self, args):
        """Merge options from a flat argparse object.

        :param argparse.Namespace args: the parsed arguments to incorperate
        :returns: None
        """
        merge = {'general': ['debug'],
                 'contact table': ['reverse', 'group_by_addressbook',
                                   'display', 'sort'],
                 'vcard': ['search_in_source_files', 'skip_unparsable',
                           'preferred_version'],
                 }
        merge = {sec: {key: getattr(args, key) for key in opts
                       if key in args and getattr(args, key) is not None}
                 for sec, opts in merge.items()}
        logging.debug('Merging in %s', merge)
        self.merge(merge)
        logging.debug('Merged: %s', vars(self))
