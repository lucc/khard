"""A simple class to load and manage the vcard files from disk."""

import abc
import binascii
from collections.abc import Mapping, Sequence
import glob
import logging
import os
from typing import Dict, Generator, Iterator, List, Optional, Union, overload

import vobject.base

from . import carddav_object
from .query import AnyQuery, Query


logger = logging.getLogger(__name__)


class AddressBookParseError(Exception):
    """Indicate an error while parsing data from an address book backend."""

    def __init__(self, filename: str, abook: str, reason: Exception) -> None:
        """Store the filename that caused the error."""
        super().__init__()
        self.filename = filename
        self.abook = abook
        self.reason = reason

    def __str__(self) -> str:
        return "Error when parsing {} in address book {}: {}".format(
            self.filename, self.abook, self.reason)


class AddressBookNameError(Exception):
    """Indicate an error with an address book name."""


class AddressBook(metaclass=abc.ABCMeta):
    """The base class of all address book implementations."""

    def __init__(self, name: str) -> None:
        """:param str name: the name to identify the address book"""
        self._loaded = False
        self.contacts: Dict[str, "carddav_object.CarddavObject"] = {}
        self._short_uids: Optional[Dict[str,
                                        "carddav_object.CarddavObject"]] = None
        self.name = name

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self.name == other.name

    def __ne__(self, other: object) -> bool:
        return not self == other

    @staticmethod
    def _compare_uids(uid1: str, uid2: str) -> int:
        """Calculate the minimum length of initial substrings of uid1 and uid2
        for them to be different.

        :param uid1: first uid to compare
        :param uid2: second uid to compare
        :returns: the length of the shortest unequal initial substrings
        """
        return len(os.path.commonprefix((uid1, uid2)))

    def search(self, query: Query) -> Generator["carddav_object.CarddavObject",
                                                None, None]:
        """Search this address book for contacts matching the query.

        The backend for this address book might be load()ed if needed.

        :param query: the query to search for
        :yields: all found contacts
        """
        logger.debug('address book %s, searching with %s', self.name, query)
        if not self._loaded:
            self.load(query)
        for contact in self.contacts.values():
            if query.match(contact):
                yield contact

    def get_short_uid_dict(self, query: Query = AnyQuery()) -> Dict[
            str, "carddav_object.CarddavObject"]:
        """Create a dictionary of shortened UIDs for all contacts.

        All arguments are only used if the address book is not yet initialized
        and will just be handed to self.load().

        :param query: see self.load()
        :returns: the contacts mapped by the shortest unique prefix of their
            UID
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
                # separately.
                item0, item1 = sorted_uids[:2]
                same1 = self._compare_uids(item0, item1)
                self._short_uids[item0[:same1 + 1]] = self.contacts[item0]
                for item_new in sorted_uids[2:]:
                    # shift the items and the common prefix length one further
                    item0, item1 = item1, item_new
                    same0, same1 = same1, self._compare_uids(item0, item1)
                    # compute the final prefix length for item1
                    same = max(same0, same1)
                    self._short_uids[item0[:same + 1]] = self.contacts[item0]
                # Save the last item.
                self._short_uids[item1[:same1 + 1]] = self.contacts[item1]
        return self._short_uids

    def get_short_uid(self, uid: str) -> str:
        """Get the shortened UID for the given UID.

        :param uid: the full UID to shorten
        :returns: the shortened uid or the empty string
        """
        if uid:
            short_uids = self.get_short_uid_dict()
            for length_of_uid in range(len(uid), 0, -1):
                if short_uids.get(uid[:length_of_uid]) is not None:
                    return uid[:length_of_uid]
        return ""

    @abc.abstractmethod
    def load(self, query: Query = AnyQuery()) -> None:
        """Load the vCards from the backing store.

        If a query is given loading is limited to entries which match the
        query.  If the query is None all entries will be loaded.

        :param query: the query to limit loading to matching entries
        :returns: the number of loaded contacts and the number of errors
        """


class VdirAddressBook(AddressBook):
    """An AddressBook implementation based on a vdir.

    This address book can load contacts from vcard files that reside in one
    directory on disk.
    """

    def __init__(self, name: str, path: str,
                 private_objects: Optional[List[str]] = None,
                 localize_dates: bool = True, skip: bool = False) -> None:
        """
        :param name: the name to identify the address book
        :param path: the path to the backing structure on disk
        :param private_objects: the names of private vCard extension fields to
            load
        :param localize_dates: whether to display dates in the local format
        :param skip: skip unparsable vCard files
        """
        self.path = os.path.expanduser(os.path.expandvars(path))
        if not os.path.isdir(self.path):
            raise NotADirectoryError("The path {} to the address book {} is "
                                     "not a directory".format(path, name))
        self._private_objects = private_objects or []
        self._localize_dates = localize_dates
        self._skip = skip
        super().__init__(name)

    def load(self, query: Query = AnyQuery(),
             search_in_source_files: bool = False) -> None:
        """Load all vcard files in this address book from disk.

        If a search string is given only files which contents match that will
        be loaded.

        :param query: query to limit the vcards that should be parsed
        :param search_in_source_files: apply search regexp directly on the .vcf
            files to speed up parsing (less accurate)
        :throws: AddressBookParseError
        """
        if self._loaded:
            return
        logger.debug('Loading Vdir %s with query %s', self.name, query)
        errors = 0
        for filename in glob.glob(os.path.join(self.path, "*.vcf")):
            try:
                card = carddav_object.CarddavObject.from_file(
                    self, filename,
                    query if search_in_source_files else AnyQuery(),
                    self._private_objects, self._localize_dates)
                if card is None:
                    continue
            except (OSError, vobject.base.ParseError, binascii.Error) as err:
                verb = "open" if isinstance(err, OSError) else "parse"
                logger.error("Error: Could not %s file %s\n%s", verb, filename,
                             err)
                if self._skip:
                    errors += 1
                else:
                    raise AddressBookParseError(filename, self.name, err)
            else:
                uid = card.uid
                if not uid:
                    logger.warning("Card %s from address book %s has no UID "
                                   "and will not be available.", card,
                                   self.name)
                elif uid in self.contacts:
                    logger.warning(
                        "Card %s and %s from address book %s have the same "
                        "UID. The former will not be available.", card,
                        self.contacts[uid], self.name)
                else:
                    self.contacts[uid] = card
        self._loaded = True
        if errors:
            logger.warning(
                "%d of %d vCard files of address book %s could not be parsed.",
                errors, len(self.contacts) + errors, self)
        logger.debug('Loaded %s contacts from address book %s.',
                     len(self.contacts), self.name)


class AddressBookCollection(AddressBook, Mapping, Sequence):
    """A collection of several address books.

    This represents a temporary merge of the contact collections provided by
    the underlying address books.  On load, all contacts from all
    subaddressbooks are copied into a dict in this address book.  This allows
    this class to use all other methods from the parent AddressBook class.
    """

    def __init__(self, name: str, abooks: List[VdirAddressBook]) -> None:
        """
        :param name: the name to identify the address book
        :param abooks: a list of address books to combine in this collection
        """
        super().__init__(name)
        self._abooks = {ab.name: ab for ab in abooks}

    def load(self, query: Query = AnyQuery()) -> None:
        """Load the wrapped address books with the given parameters

        All parameters will be handed to VdirAddressBook.load.

        :param query: a query to limit the vcards that should be parsed
        :throws: AddressBookParseError
        """
        if self._loaded:
            return
        logger.debug('Loading collection %s with query %s', self.name, query)
        for abook in self._abooks.values():
            abook.load(query)
            for uid in abook.contacts:
                if uid in self.contacts:
                    logger.warning(
                        "Card %s from address book %s will not be available "
                        "because there is already another card with the same "
                        "UID: %s", abook.contacts[uid], abook, uid)
                else:
                    self.contacts[uid] = abook.contacts[uid]
        self._loaded = True
        logger.debug('Loaded %s contacts from address book %s.',
                     len(self.contacts), self.name)

    @overload
    def __getitem__(self, key: Union[int, str]) -> VdirAddressBook: ...
    @overload
    def __getitem__(self, key: slice) -> List[VdirAddressBook]: ...
    def __getitem__(self, key: Union[int, str, slice]
                    ) -> Union[VdirAddressBook, List[VdirAddressBook]]:
        """Get one or more of the backing address books by name or index

        :param key: the name of the address book to get or its index
        :returns: the matching address book(s)
        :throws: KeyError
        """
        if isinstance(key, str):
            return self._abooks[key]
        return list(self._abooks.values())[key]

    def __iter__(self) -> Iterator[VdirAddressBook]:
        """:return: an iterator over the underlying address books"""
        return iter(self._abooks.values())

    def __len__(self) -> int:
        return len(self._abooks)
