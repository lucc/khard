# -*- coding: utf-8 -*-
"""A simple class to load and manage the vcard files from disk."""

import abc
import glob
import logging
import os
import re

import vobject.base

from .carddav_object import CarddavObject


class AddressBookParseError(Exception):
    """Indicate an error while parsing data from an address book backend."""
    pass


class AddressBook(metaclass=abc.ABCMeta):

    """The base class of all address book implementations."""

    def __init__(self, name):
        """
        :param name: the name to identify the address book
        :type name: str
        """
        self.loaded = False
        self.contacts = []
        self._uids = None
        self._short_uids = None
        self.name = name

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.name == other.name

    def __ne__(self, other):
        return not self == other

    @staticmethod
    def _compare_uids(uid1, uid2):
        """Calculate the minimum length of initial substrings of uid1 and uid2
        for them to be different.

        :param uid1: first uid to compare
        :type uid1: str
        :param uid2: second uid to compare
        :type uid2: str
        :returns: the length of the shortes unequal inital substrings
        :rtype: int
        """
        sum = 0
        for c1, c2 in zip(uid1, uid2):
            if c1 == c2:
                sum += 1
            else:
                break
        return sum

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
        found = False
        # Search for contacts with uid == query.
        for contact in self.contacts:
            if contact.get_uid() == query:
                found = True
                yield contact
        # If that fails, search for contacts where uid starts with query.
        if not found:
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

    def get_uids_dict(self):
        """Create a dictionary of UIDs for all contacts.

        :returns: all contacts mapped by their UID
        :rtype: dict(str: CarddavObject)

        """
        if self._uids is None:
            if not self.loaded:
                self.load()
            self._uids = dict()
            for contact in self.contacts:
                uid = contact.get_uid()
                if uid:
                    if uid in self._uids:
                        logging.warning("The contacts %s and %s from address "
                                        "book %s have the same UID %s",
                                        contact, self._uids[uid], self, uid)
                    else:
                        self._uids[uid] = contact
                else:
                    logging.warning("The contact %s from address book %s has "
                                    "no UID", contact, self)
        return self._uids

    def get_short_uid_dict(self):
        """Create a dictionary of shortend UIDs for all contacts.

        :returns: the contacts mapped by the shortes unique prefix of their UID
        :rtype: dict(str: CarddavObject)

        """
        if self._short_uids is None:
            self.get_uids_dict()
            if not self._uids:
                self._short_uids = {}
            elif len(self._uids) == 1:
                self._short_uids = {key[:1]: value
                                    for key, value in self._uids.items()}
            else:
                self._short_uids = {}
                sorted_uids = sorted(self._uids)
                # Prepare for the loop; the first and last items are handled
                # seperatly.
                item0, item1 = sorted_uids[:2]
                same1 = self._compare_uids(item0, item1)
                self._short_uids[item0[:same1 + 1]] = self._uids[item0]
                for item_new in sorted_uids[2:]:
                    # shift the items and the common prefix lenght one further
                    item0, item1 = item1, item_new
                    same0, same1 = same1, self._compare_uids(item0, item1)
                    # compute the final prefix length for item1
                    same = max(same0, same1)
                    self._short_uids[item0[:same + 1]] = self._uids[item0]
                # Save the last item.
                self._short_uids[item1[:same1 + 1]] = self._uids[item1]
        return self._short_uids

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

    def __init__(self, name, path):
        """
        :param name: the name to identify the address book
        :type name: str
        :param path: the path to the backing structure on disk
        :type path: str
        """
        self.path = os.path.expanduser(path)
        if not os.path.isdir(self.path):
            raise FileNotFoundError("[Errno 2] The path {} to the address book"
                                    " {} does not exist.".format(path, name))
        super().__init__(name)

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

    def load(self, query=None, private_objects=tuple(), localize_dates=True,
             skip=False):
        """Load all vcard files in this address book from disk.  If a search
        string is given only files which contents match that will be loaded.

        :param query: a regular expression to limit the results
        :type query: str
        :param private_objects: the names of private vcard extension fields to
            load
        :type private_objects: list(str) or tuple(str)
        :param localize_dates: TODO
        :type localize_dates: bool
        :param skip: skip unparsable vCard files
        :type skip: bool
        :returns: the number of successfully loaded cards and the number of
            errors
        :rtype: int, int

        """
        if self.loaded:
            return len(self.contacts), 0
        errors = 0
        for filename in self._find_vcard_files(search=query):
            try:
                card = CarddavObject.from_file(self, filename, private_objects,
                                               localize_dates)
            except (IOError, vobject.base.ParseError) as err:
                if skip:
                    verb = "open" if isinstance(err, IOError) else "parse"
                    logging.debug("Error: Could not %s file %s\n%s", verb,
                                  filename, err)
                    errors += 1
                else:
                    raise AddressBookParseError()
            else:
                self.contacts.append(card)
        self.loaded = True
        if skip:
            logging.warning(
                "%d of %d vCard files of address book %s could not be parsed.",
                errors, len(self.contacts) + errors, self)
        if len(self.contacts) != len(self.get_uids_dict()):
            logging.warning("There are duplicate UIDs in the address book %s.",
                            self)
        return len(self.contacts), errors


class AddressBookCollection(AddressBook):

    """A collection of several address books.  This represents the a temporary
    merege of the contact collections provided by the underlying adress
    books."""

    def __init__(self, name, *args):
        """
        :param name: the name to identify the address book
        :type name: str
        :param *args: two-tuples, each holding the arguments for one
            AddressBook instance
        :type *args: tuple(str,str)
        """
        super().__init__(name)
        self._abooks = []
        for arguments in args:
            self._abooks.append(VdirAddressBook(*arguments))

    def load(self, query=None, private_objects=tuple(), localize_dates=True,
             skip=False):
        if self.loaded:
            return len(self.contacts), 0
        errors = 0
        for abook in self._abooks:
            _, err = abook.load(query, private_objects, localize_dates, skip)
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

    def get_uids_dict(self):
        """Create a dictionary of UIDs for all contacts.

        :returns: all contacts mapped by their UID
        :rtype: dict(str: CarddavObject)

        """
        if self._uids is None:
            if not self.loaded:
                self.load()
            self._uids = dict()
            for abook in self._abooks:
                uids = abook.get_uids_dict()
                for uid in uids:
                    if uid in self._uids:
                        logging.warning("The contacts %s and %s from address "
                                        "book %s have the same UID %s",
                                        self._uids[uid], uids[uid], self, uid)
                    else:
                        self._uids[uid] = uids[uid]
        return self._uids
