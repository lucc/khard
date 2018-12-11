"""Tests for the address book classes."""

import sys
import unittest
from unittest import mock

from khard import address_book

from .helpers import expectedFailureForVersion


class _AddressBook(address_book.AddressBook):
    """Class for testing the abstract AddressBook base class."""
    def load(self, query=None):
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
        abook._loaded = True
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

    def test_vcards_without_uid_generate_a_warning(self):
        abook = address_book.VdirAddressBook('test',
                                             'test/fixture/minimal.abook')
        with self.assertLogs(level='WARNING') as cm:
            abook.load()
        messages = ['WARNING:root:Card minimal contact from address book test '
                    'has no UID and will not be availbale.']
        self.assertListEqual(cm.output, messages)

    def test_loading_vcards_from_disk(self):
        abook = address_book.VdirAddressBook('test', 'test/fixture/foo.abook')
        # At this point we do not really care about the type of abook.contacts,
        # it could be a list or dict or set or whatever.
        self.assertEqual(len(abook.contacts), 0)
        abook.load()
        self.assertEqual(len(abook.contacts), 3)

    def test_search_in_source_files_only_loads_matching_cards(self):
        abook = address_book.VdirAddressBook('test', 'test/fixture/foo.abook')
        abook.load(query='second', search_in_source_files=True)
        self.assertEqual(len(abook.contacts), 1)

    def test_loading_unparsable_vcard_fails(self):
        abook = address_book.VdirAddressBook('test',
                                             'test/fixture/broken.abook')
        with self.assertRaises(SystemExit):
            with self.assertLogs(level='ERROR'):
                abook.load()

    def test_unparsable_files_can_be_skipped(self):
        abook = address_book.VdirAddressBook(
            'test', 'test/fixture/broken.abook', skip=True)
        with self.assertLogs(level='WARNING') as cm:
            abook.load()
        self.assertEqual(cm.output, ['WARNING:root:1 of 1 vCard files of '
                                     'address book test could not be parsed.'])


class AddressBookGetShortUidDict(unittest.TestCase):

    def test_uniqe_uid_also_reslts_in_shortend_uid_in_short_uid_dict(self):
        contacts = {'uid123': None}
        abook = _AddressBook('test')
        abook.contacts = contacts
        abook._loaded = True
        short_uids = abook.get_short_uid_dict()
        self.assertEqual(len(short_uids), 1)
        short_uid, contact = short_uids.popitem()
        self.assertEqual(short_uid, 'u')


class ReportedBugs(unittest.TestCase):

    def test_issue_159_uid_search_doesnt_return_items_twice(self):
        # This was the first half of bug report #159.
        abook = address_book.VdirAddressBook('test', 'test/fixture/foo.abook')
        c = abook.search('testuid1', method='uid')
        self.assertEqual(len(c), 1)
