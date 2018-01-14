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
        with self.assertRaises(ValueError):
            abook = _AddressBook('test')
            abook.search('query', method='invalid_method')


class AddressBookCompareUids(unittest.TestCase):

    def test_different_strings(self):
        uid1 = 'abc'
        uid2 = 'xyz'
        expected = 0
        actual = address_book.AddressBook._compare_uids(uid1, uid2)
        self.assertEqual(actual, expected)

    def test_two_simple_strings(self):
        uid1 = 'abcdef'
        uid2 = 'abcxyz'
        expected = 3
        actual = address_book.AddressBook._compare_uids(uid1, uid2)
        self.assertEqual(actual, expected)

    def test_no_error_on_equal_strings(self):
        uid = 'abcdefghij'
        expected = len(uid)
        actual = address_book.AddressBook._compare_uids(uid, uid)
        self.assertEqual(actual, expected)

