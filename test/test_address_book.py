"""Tests for the address book classes."""

import sys
import unittest
from unittest import mock

from khard import address_book


def expectedFailureForVersion(major, minor):
    if sys.version_info.major == major and sys.version_info.minor == minor:
        return unittest.expectedFailure
    else:
        return lambda x: x


class _AddressBook(address_book.AddressBook):
    """Class for testing the abstract AddressBook base class."""
    def load(self, query=None, private_objects=tuple(), localize_dates=True):
        pass


class AbstractAddressBookSearch(unittest.TestCase):
    """Tests for khard.address_book.AddressBook.search()"""

    def test_invalide_method_failes(self):
        abook = _AddressBook('test')
        with self.assertRaises(ValueError):
            abook.search('query', method='invalid_method')

    # FIXME This breaks on travis *only* for python 3.5, assert_called_once
    # only exists in 3.6 and not in 3.4 but oddly it passes there.
    @expectedFailureForVersion(3, 5)
    def test_search_will_trigger_load_if_not_loaded(self):
        abook = _AddressBook('test')
        load_mock = mock.Mock()
        abook.load = load_mock
        abook.search('foo')
        load_mock.assert_called_once()

    def test_search_will_not_trigger_load_if_loaded(self):
        abook = _AddressBook('test')
        load_mock = mock.Mock()
        abook.load = load_mock
        abook.loaded = True
        abook.search('foo')
        load_mock.assert_not_called()

    def test_search_passes_query_to_load(self):
        abook = _AddressBook('test')
        load_mock = mock.Mock()
        abook.load = load_mock
        abook.search('foo')
        load_mock.assert_called_once_with('foo')


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


class VcardAdressBookLoad(unittest.TestCase):

    def test_loading_vcards_from_disk(self):
        abook = address_book.VdirAddressBook('test', 'test/fixture/foo.abook')
        # At this point we do not really care about the type of abook.contacts,
        # it could be a list or dict or set or whatever.
        self.assertEqual(len(abook.contacts), 0)
        with self.assertLogs(level='WARNING') as cm:
            abook.load()
        self.assertEqual(len(abook.contacts), 2)
        # TODO: There is also a warning about duplicate uids but that might be
        # a bug.
        self.assertIn('WARNING:root:The contact one contact with minimal Vcard'
                      ' from address book test has no UID', cm.output)

    def test_search_in_source_files_only_loads_matching_cards(self):
        abook = address_book.VdirAddressBook('test', 'test/fixture/foo.abook')
        abook.load(query='second')
        self.assertEqual(len(abook.contacts), 1)

    def test_loading_unparsable_vcard_fails(self):
        abook = address_book.VdirAddressBook('test',
                                             'test/fixture/broken.abook')
        with self.assertRaises(address_book.AddressBookParseError):
            abook.load()

    def test_unparsable_files_can_be_skipped(self):
        abook = address_book.VdirAddressBook('test',
                                             'test/fixture/broken.abook')
        with self.assertLogs(level='WARNING') as cm:
            abook.load(skip=True)
        self.assertEqual(cm.output, ['WARNING:root:1 of 1 vCard files of '
                                     'address book test could not be parsed.'])
