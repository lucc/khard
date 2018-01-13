"""Tests for the address book classes."""

import unittest
from unittest import mock

from khard import address_book


class _AddressBook(address_book.AddressBook):
    """Class for testing the abstract AddressBook base class."""
    def load(self, query=None, private_objects=tuple(), localize_dates=True):
        pass


class AbstractAddressBookSearch(unittest.TestCase):
    """Tests for khard.address_book.AddressBook.search()"""

    def test_invalide_method_failes(self):
        with mock.patch('os.path.isdir', lambda _: True):
            with self.assertRaises(ValueError):
                abook = _AddressBook('test', "/this-doesn't-exist")
                abook.search('query', method='invalid_method')
