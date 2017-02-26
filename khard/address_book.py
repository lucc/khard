# -*- coding: utf-8 -*-
"""A simple class to load and manage the vcard files from disk."""

import abc
import glob
import logging
import os
import re

from .carddav_object import CarddavObject


class AddressBook(metaclass=abc.ABCMeta):

    """The base class of all address book implementations."""

    def __init__(self, name, path):
        """
        :param name: the name to identify the address book
        :type name: str
        :param path: the path to the backing structure on disk
        :type path: str
        """
        self.loaded = False
        self.contacts = []
        self._uids = set()
        self.name = name
        self.path = os.path.expanduser(path)
        if not os.path.isdir(self.path):
            raise FileNotFoundError("[Errno 2] The path {} to the address book"
                                    " {} does not exist.".format(path, name))

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.name == other.name

    def __ne__(self, other):
        return not self == other

    def _search_all(self, query):
        """Search in all fields for contacts matching query.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        regexp = re.compile(query, re.IGNORECASE | re.DOTALL)
        for contact in self.contacts:
            # search in all contact fields
            contact_details = contact.print_vcard()
            # find phone numbers with special chars like /
            clean_contact_details = re.sub("[^a-zA-Z0-9\n]", "",
                                           contact_details)
            if regexp.search(contact_details) is not None or regexp.search(
                    clean_contact_details) is not None:
                yield contact

    def _search_names(self, query):
        """Search in the name filed for contacts matching query.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        regexp = re.compile(query, re.IGNORECASE | re.DOTALL)
        for contact in self.contacts:
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
        contacts = []
        # Search for contacts with uid == query.
        for contact in self.contacts:
            if contact.get_uid() == query:
                yield contact
        # If that fails, search for contacts where uid starts with query.
        if not contacts:
            for contact in self.contacts:
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
        if not self.loaded:
            self.load(query)
        if method == "all":
            search_function = self._search_all
        elif method == "name":
            search_function = self._search_names
        elif method == "uid":
            search_function = self._search_uid
        else:
            raise ValueError('Only the search methods "all", "name" and "uid" '
                             'are supported.')
        return list(search_function(query))

    @abc.abstractmethod
    def load(self, query=None, private_objects=tuple(), localize_dates=True):
        """Load the vCards from the backing store.  If a query is given loading
        is limited to entries which match the query.  If the query is None all
        entries will be loaded.

        :param query: the query to limit loading to matching entries
        :type query: str
        :param private_objects: the names of private vCard extension fields to
            load
        :type private_objects: iterable(str)
        :param localize_dates: TODO
        :type localize_dates: bool
        :returns: the number of loaded contacts and the number of errors
        :rtype: (int, int)

        """
        pass


class VdirAddressBook(AddressBook):

    """Holds the contacts inside one address book folder.  On disk they are
    stored in vcard files."""

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
        for contact in self.contacts:
            uid = contact.get_uid()
            if uid in self._uids:
                duplicates.add(uid)
            else:
                self._uids.add(uid)
        return duplicates

    def load(self, query=None, private_objects=tuple(), localize_dates=True):
        """Load all vcard files in this address book from disk.  If a search
        string is given only files which contents match that will be loaded.

        :param query: a regular expression to limit the results
        :type query: str
        :param private_objects: the names of private vcard extension fields to
            load
        :type private_objects: list(str) or tuple(str)
        :param localize_dates: TODO
        :type localize_dates: bool
        :returns: the number of successfully loaded cards and the number of
            errors
        :rtype: int, int

        """
        if self.loaded:
            return len(self.contacts), 0
        contacts = 0
        errors = 0
        for filename in self._find_vcard_files(search=query):
            contacts += 1
            try:
                card = CarddavObject.from_file(self, filename, private_objects,
                                               localize_dates)
            except IOError as err:
                logging.debug("Error: Could not open file %s\n%s", filename,
                              err)
                errors += 1
            except Exception as err:
                logging.debug("Error: Could not parse file %s\n%s", filename,
                              err)
                errors += 1
            else:
                self.contacts.append(card)
        duplicates = self._check_uids()
        if duplicates:
            logging.warning(
                "There are duplicate UIDs in the address book %s: %s",
                self.name, duplicates)
        self.loaded = True
        return contacts, errors


class AddressBookCollection(AddressBook):

    """A collection of several address books.  This represents the a temporary
    merege of the contact collections provided by the underlying adress
    books."""

    def __init__(self, name, *args):
        """
        :param name: the name to identify the address book
        :type name: str
        :param *args: two-tuples, each holding the arguments for one AddressBook
            instance
        :type *args: tuple(str,str)
        """
        self.loaded = False
        self.contacts = []
        self._uids = set()
        self.name = name
        self._abooks = []
        for arguments in args:
            self._abooks.append(VdirAddressBook(*arguments))

    def load(self, query=None, private_objects=tuple()):
        if self.loaded:
            return len(self.contacts), 0
        errors = 0
        for abook in self._abooks:
            _, err = abook.load(query, private_objects)
            errors += err
        self.loaded = True
        self.contacts = [contact for contact in abook.contacts
                         for abook in self._abooks]
        return len(self.contacts), errors

    def get_abook(self, name):
        """Get one of the backing abdress books by its name,

        :param name: the name of the address book to get
        :type name: str
        :returns: the matching address book or None
        :rtype: AddressBook or NoneType

        """
        for abook in self._abooks:
            if abook.name == name:
                return abook
