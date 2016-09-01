# -*- coding: utf-8 -*-
"""A simple class to load and manage the vcard files from disk."""

import glob
import logging
import os
import re

from .carddav_object import CarddavObject


class AddressBook:

    """Holds the contacts inside one address book folder.  On disk they are
    stored in vcard files."""

    def __init__(self, name, path):
        self.loaded = False
        self.contact_list = []
        self.name = name
        self.path = os.path.expanduser(path)
        if not os.path.isdir(self.path):
            raise FileNotFoundError(
                "[Errno 2] The path %s to the address book %s does not exist."
                % (self.path, self.name))

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, AddressBook) and self.name == other.name

    def __ne__(self, other):
        return not self == other

    def _find_vcard_files(self, search=None):
        """Find all vcard files inside this address book.  If a search string
        is given only files which contents match that will be returned.

        :param search: a regular expression to limit the results
        :type search: str
        :returns: the paths of the vcard files
        :rtype: generator

        """
        for filename in glob.glob(os.path.join(self.path, "*.vcf")):
            if search:
                with open(filename, "r") as filehandle:
                    if re.search(search, filehandle.read(),
                                 re.IGNORECASE | re.DOTALL):
                        yield filename
            else:
                yield filename

    def load_all_vcards(self, private_objects=tuple(), search=None):
        """Load all vcard files in this address book from disk.  If a search
        string is given only files which contents match that will be loaded.

        :param private_objects: the names of private vcard extension fields to
            load
        :type private_objects: list(str) or tuple(str)
        :param search: a regular expression to limit the results
        :type search: str
        :returns: the number of successfully loaded cards and the number of
            errors
        :rtype: int, int

        """
        if self.loaded:
            return len(self.contact_list), 0
        contacts = 0
        errors = 0
        for filename in self._find_vcard_files(search=search):
            contacts += 1
            try:
                card = CarddavObject.from_file(self, filename, private_objects)
            except IOError as err:
                logging.debug("Error: Could not open file %s\n%s", filename,
                              err)
                errors += 1
            except Exception as err:
                logging.debug("Error: Could not parse file %s\n%s", filename,
                              err)
                errors += 1
            else:
                self.contact_list.append(card)
        self.loaded = True
        return contacts, errors
