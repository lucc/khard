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
        self._uids = set()
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

    def _check_uids(self):
        """Check that the uids of all cards are unique across this address
        book.

        :returns: the set of duplicate uids
        :rtype: set(str)

        """
        duplicates = set()
        for contact in self.contact_list:
            uid = contact.get_uid()
            if uid in self._uids:
                duplicates.add(uid)
            else:
                self._uids.add(uid)
        return duplicates

    def load_all_vcards(self, private_objects=tuple(), localize_dates=True,
            search=None):
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
                card = CarddavObject.from_file(self, filename,
                        private_objects, localize_dates)
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
        duplicates = self._check_uids()
        if duplicates:
            logging.warning(
                "There are duplicate UIDs in the address book %s: %s",
                self.name, duplicates)
        self.loaded = True
        return contacts, errors

    def _search_all(self, query):
        """Search in all fields for contacts matching query.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        regexp = re.compile(query, re.IGNORECASE | re.DOTALL)
        for contact in self.contact_list:
            # search in all contact fields
            contact_details = contact.print_vcard()
            if regexp.search(contact_details) is not None:
                yield contact
            else:
                # find phone numbers with special chars like /
                contact_details_without_special_chars = re.sub("[^a-zA-Z0-9\n]",
                                                               "", contact_details)
                if regexp.search(contact_details_without_special_chars) is not None \
                        and len(re.sub("\D", "", query)) >= 3:
                    yield contact

    def _search_names(self, query):
        """Search in the name filed for contacts matching query.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        regexp = re.compile(query, re.IGNORECASE | re.DOTALL)
        for contact in self.contact_list:
            # only search in contact name
            if regexp.search(contact.get_full_name()) is not None:
                yield contact

    def _search_uid(self, query):
        """Search for contacts with a matching uid.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        found = False
        # Search for contacts with uid == query.
        for contact in self.contact_list:
            if contact.get_uid() == query:
                found = True
                yield contact
        # If that fails, search for contacts where uid starts with query.
        if not found:
            for contact in self.contact_list:
                if contact.get_uid().startswith(query):
                    yield contact

    def search(self, query, method="all"):
        """Search this address book for contacts matching the query.  The
        method can be one of "all", "name" and "uid".

        :param query: the query to search for
        :type query: str
        :param method: the type of fileds to use when seaching
        :type method: str
        :returns: all found contacts
        :rtype: list(carddav_object.CarddavObject)

        """
        if method == "all" or method == "name":
            if method == "all":
                search_function = self._search_all
            else:
                search_function = self._search_names
            # check if query is already an regexp, else escape it
            if not (query.startswith(".*") and query.endswith(".*")):
                query = re.escape(query)
            return list(search_function(query))
        elif method == "uid":
            # always escape uids
            return list(self._search_uid(re.escape(query)))
        else:
            raise ValueError('Only the search methods "all", "name" and "uid" '
                             'are supported.')
