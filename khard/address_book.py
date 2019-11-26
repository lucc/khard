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

    def __init__(self, filename, abook, reason, *args, **kwargs):
        """Store the filename that caused the error."""
        super().__init__(*args, **kwargs)
        self.filename = filename
        self.abook = abook
        self.reason = reason

    def __str__(self):
        return "Error when parsing {} in address book {}: {}".format(
            self.filename, self.abook, self.reason)


class AddressBookNameError(Exception):
    """Indicate an error with an address book name."""


class AddressBook(metaclass=abc.ABCMeta):
    """The base class of all address book implementations."""

    def __init__(self, name):
        """:param str name: the name to identify the address book"""
        self._loaded = False
        self.contacts = {}
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
        :returns: the length of the shortes unequal initial substrings
        :rtype: int
        """
        return len(os.path.commonprefix((uid1, uid2)))

    def _search_all(self, query):
        """Search in all fields for contacts matching query.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        regexp = re.compile(query, re.IGNORECASE | re.DOTALL)
        for contact in self.contacts.values():
            # search in all contact fields
            contact_details = contact.print_vcard()
            if regexp.search(contact_details) is not None:
                yield contact
            else:
                # find phone numbers with special chars like /
                clean_contact_details = re.sub("[^a-zA-Z0-9\n]", "",
                                               contact_details)
                if regexp.search(clean_contact_details) is not None \
                        and len(re.sub(r"\D", "", query)) >= 3:
                    yield contact

    def _search_category(self, query):
        """Search in all the fields for contacts containing words from the query.

        :param query: the words to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        categories = query.replace("\\", "").split(".*")
        for contact in self.contacts.values():
            if all(category in contact.categories for category in categories):
                yield contact

    def _search_names(self, query):
        """Search in the name field for contacts matching query.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        regexp = re.compile(query, re.IGNORECASE | re.DOTALL)
        for contact in self.contacts.values():
            # only search in contact name
            if regexp.search(contact.formatted_name) is not None:
                yield contact

    def _search_uid(self, query):
        """Search for contacts with a matching uid.

        :param query: the query to search for
        :type query: str
        :yields: all found contacts
        :rtype: generator(carddav_object.CarddavObject)

        """
        try:
            # First we treat the argument as a full UID and try to match it
            # exactly.
            yield self.contacts[query]
        except KeyError:
            # If that failed we look for all contacts whos UID start with the
            # given query.
            for uid in self.contacts:
                if uid.startswith(query):
                    yield self.contacts[uid]

    def search(self, query, method="all"):
        """Search this address book for contacts matching the query.

        The method can be one of "all", "name" and "uid".  The backend for this
        address book migth be load()ed if needed.

        :param query: the query to search for
        :type query: str
        :param method: the type of fileds to use when seaching
        :type method: str
        :returns: all found contacts
        :rtype: list(carddav_object.CarddavObject)

        """
        logging.debug('address book %s, searching %s with %s', self.name, method, query)
        if not self._loaded:
            self.load(query)
        if method == "all":
            return self._search_all(query)
        elif method == "category":
            return self._search_category(query)
        elif method == "name":
            return self._search_names(query)
        elif method == "uid":
            return self._search_uid(query)
        raise ValueError(
            'Only the search methods "all", "name", "category" and "uid" are supported.')

    def get_short_uid_dict(self, query=None):
        """Create a dictionary of shortend UIDs for all contacts.

        All arguments are only used if the address book is not yet initialized
        and will just be handed to self.load().

        :param query: see self.load()
        :type query: str
        :returns: the contacts mapped by the shortes unique prefix of their UID
        :rtype: dict(str: CarddavObject)
        """
        if self._short_uids is None:
            if not self._loaded:
                self.load(query)
            if not self.contacts:
                self._short_uids = {}
            elif len(self.contacts) == 1:
                self._short_uids = {uid[0:1]: contact
                                    for uid, contact in self.contacts.items()}
            else:
                self._short_uids = {}
                sorted_uids = sorted(self.contacts)
                # Prepare for the loop; the first and last items are handled
                # seperatly.
                item0, item1 = sorted_uids[:2]
                same1 = self._compare_uids(item0, item1)
                self._short_uids[item0[:same1 + 1]] = self.contacts[item0]
                for item_new in sorted_uids[2:]:
                    # shift the items and the common prefix lenght one further
                    item0, item1 = item1, item_new
                    same0, same1 = same1, self._compare_uids(item0, item1)
                    # compute the final prefix length for item1
                    same = max(same0, same1)
                    self._short_uids[item0[:same + 1]] = self.contacts[item0]
                # Save the last item.
                self._short_uids[item1[:same1 + 1]] = self.contacts[item1]
        return self._short_uids

    def get_short_uid(self, uid):
        """Get the shortend UID for the given UID.

        :param uid: the full UID to shorten
        :type uid: str
        :returns: the shortend uid or the empty string
        :rtype: str
        """
        if uid:
            short_uids = self.get_short_uid_dict()
            for length_of_uid in range(len(uid), 0, -1):
                if short_uids.get(uid[:length_of_uid]) is not None:
                    return uid[:length_of_uid]
        return ""

    @abc.abstractmethod
    def load(self, query=None):
        """Load the vCards from the backing store.

        If a query is given loading is limited to entries which match the
        query.  If the query is None all entries will be loaded.

        :param query: the query to limit loading to matching entries
        :type query: str
        :returns: the number of loaded contacts and the number of errors
        :rtype: (int, int)

        """


class VdirAddressBook(AddressBook):
    """An AddressBook implementation based on a vdir.

    This address book can load contacts from vcard files that reside in one
    direcotry on disk.
    """

    def __init__(self, name, path, private_objects=tuple(),
                 localize_dates=True, skip=False):
        """
        :param str name: the name to identify the address book
        :param str path: the path to the backing structure on disk
        :param iterable(str) private_objects: the names of private vCard
            extension fields to load
        :param bool localize_dates: wheater to display dates in the local
            format
        :param bool skip: skip unparsable vCard files
        """
        self.path = os.path.expanduser(path)
        if not os.path.isdir(self.path):
            raise FileNotFoundError("[Errno 2] The path {} to the address book"
                                    " {} does not exist.".format(path, name))
        self._private_objects = private_objects
        self._localize_dates = localize_dates
        self._skip = skip
        super().__init__(name)

    def load(self, query=None, search_in_source_files=False):
        """Load all vcard files in this address book from disk.

        If a search string is given only files which contents match that will
        be loaded.

        :param query: a regular expression to limit the results
        :type query: str
        :param search_in_source_files: apply search regexp directly on the .vcf
            files to speed up parsing (less accurate)
        :type search_in_source_files: bool
        :returns: the number of successfully loaded cards and the number of
            errors
        :rtype: int, int
        :throws: AddressBookParseError
        """
        if self._loaded:
            return
        logging.debug('Loading Vdir %s with query %s', self.name, query)
        errors = 0
        for filename in glob.glob(os.path.join(self.path, "*.vcf")):
            try:
                card = CarddavObject.from_file(
                    self, filename, query if search_in_source_files else None,
                    self._private_objects, self._localize_dates)
                if card is None:
                    continue
            except (IOError, vobject.base.ParseError) as err:
                verb = "open" if isinstance(err, IOError) else "parse"
                logging.debug("Error: Could not %s file %s\n%s", verb,
                              filename, err)
                if self._skip:
                    errors += 1
                else:
                    raise AddressBookParseError(filename, self.name, err)
            else:
                uid = card.uid
                if not uid:
                    logging.warning("Card %s from address book %s has no UID "
                                    "and will not be available.", card,
                                    self.name)
                elif uid in self.contacts:
                    logging.warning(
                        "Card %s and %s from address book %s have the same "
                        "UID. The former will not be available.", card,
                        self.contacts[uid], self.name)
                else:
                    self.contacts[uid] = card
        self._loaded = True
        if errors:
            logging.warning(
                "%d of %d vCard files of address book %s could not be parsed.",
                errors, len(self.contacts) + errors, self)
        logging.debug('Loded %s contacts from address book %s.',
                      len(self.contacts), self.name)


class AddressBookCollection(AddressBook):
    """A collection of several address books.

    This represents a temporary merege of the contact collections provided by
    the underlying adress books.  On load all contacts from all subadressbooks
    are copied into a dict in this address book.  This allow this class to use
    all other methods from the parent AddressBook class.
    """

    def __init__(self, name, abooks):
        """
        :param name: the name to identify the address book
        :type name: str
        :param abooks: a list of address books to combine in this collection
        :type abooks: list(AddressBook)
        :param **kwargs: further arguments for the parent constructor
        """
        super().__init__(name)
        self._abooks = {ab.name: ab for ab in abooks}

    def load(self, query=None, search_in_source_files=False):
        """Load the wrapped address books with the given parameters

        All parameters will be handed to VdirAddressBook.load.

        :param str query: a regular expression to limit the results
        :param bool search_in_source_files: apply search regexp directly on the
            .vcf files to speed up parsing (less accurate)
        :returns: None
        :throws: AddressBookParseError
        """
        if self._loaded:
            return
        logging.debug('Loading collection %s with query %s', self.name, query)
        for abook in self._abooks.values():
            abook.load(query)
            for uid in abook.contacts:
                if uid in self.contacts:
                    logging.warning(
                        "Card %s from address book %s will not be available "
                        "because there is already another card with the same "
                        "UID: %s", abook.contacts[uid], abook, uid)
                else:
                    self.contacts[uid] = abook.contacts[uid]
        self._loaded = True
        logging.debug('Loded %s contacts from address book %s.',
                      len(self.contacts), self.name)

    def __getitem__(self, key):
        """Get one of the backing address books by name or index

        :param str|int key: the name of the address book to get or its index
        :returns: the matching address book
        :rtype: AddressBook
        :throws: KeyError
        """
        try:
            return self._abooks[key]
        except KeyError:
            return list(self._abooks.values())[key]

    def __iter__(self):
        """:return: an iterator over the underlying address books"""
        return iter(self._abooks.values())

    def __len__(self):
        return len(self._abooks)
