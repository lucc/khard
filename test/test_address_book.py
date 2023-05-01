"""Tests for the address book classes."""
# pylint: disable=missing-docstring

import os
import unittest
from unittest import mock

from khard import address_book, query

from .helpers import TmpAbook


class _AddressBook(address_book.AddressBook):
    """Class for testing the abstract AddressBook base class."""

    def load(self, query=None):
        pass


class AbstractAddressBookSearch(unittest.TestCase):
    """Tests for khard.address_book.AddressBook.search()"""

    def test_search_will_trigger_load_if_not_loaded(self):
        abook = _AddressBook('test')
        load_mock = mock.Mock()
        abook.load = load_mock
        list(abook.search(query.AnyQuery()))
        load_mock.assert_called_once()

    def test_search_will_not_trigger_load_if_loaded(self):
        abook = _AddressBook('test')
        load_mock = mock.Mock()
        abook.load = load_mock
        abook._loaded = True
        list(abook.search(query.AnyQuery()))
        load_mock.assert_not_called()

    def test_search_passes_query_to_load(self):
        abook = _AddressBook('test')
        self.assertFalse(abook._loaded)
        load_mock = mock.Mock()
        abook.load = load_mock
        list(abook.search(query.AnyQuery()))
        load_mock.assert_called_once_with(query.AnyQuery())


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


class VcardAddressBookLoad(unittest.TestCase):

    def test_vcards_without_uid_generate_a_warning(self):
        abook = address_book.VdirAddressBook('test',
                                             'test/fixture/minimal.abook')
        with self.assertLogs(level='WARNING') as cm:
            abook.load()
            messages = ['WARNING:khard.address_book:Card minimal contact from '
                        'address book test has no UID and will not be '
                        'available.']
        self.assertListEqual(cm.output, messages)

    def test_loading_vcards_from_disk(self):
        abook = address_book.VdirAddressBook('test', 'test/fixture/test.abook')
        # At this point we do not really care about the type of abook.contacts,
        # it could be a list or dict or set or whatever.
        self.assertEqual(len(abook.contacts), 0)
        abook.load()
        self.assertEqual(len(abook.contacts), 3)

    def test_search_in_source_files_only_loads_matching_cards(self):
        abook = address_book.VdirAddressBook('test', 'test/fixture/test.abook')
        abook.load(query=query.TermQuery('second'), search_in_source_files=True)
        self.assertEqual(len(abook.contacts), 1)

    def test_loading_unparsable_vcard_fails(self):
        abook = address_book.VdirAddressBook('test',
                                             'test/fixture/broken.abook')
        with self.assertRaises(address_book.AddressBookParseError):
            with self.assertLogs(level='ERROR'):
                abook.load()

    def test_unparsable_files_can_be_skipped(self):
        abook = address_book.VdirAddressBook(
            'test', 'test/fixture/broken.abook', skip=True)
        with self.assertLogs(level='WARNING') as cm:
            abook.load()
        self.assertEqual(cm.output[0],
            'WARNING:khard.carddav_object:Filtering some problematic tags '
            'from test/fixture/broken.abook/unparsable.vcf')
        # FIXME Remove this regex assert when either
        # https://github.com/eventable/vobject/issues/156 is closed or we drop
        # support for python 3.6
        self.assertRegex(cm.output[1],
            'ERROR:khard.address_book:Error: Could not parse file '
            'test/fixture/broken.abook/unparsable.vcf\n'
            'At line [35]: Component VCARD was never closed')
        self.assertEqual(cm.output[2],
            'WARNING:khard.address_book:1 of 1 vCard files of address book '
            'test could not be parsed.')

    @mock.patch.dict("os.environ", clear=True)
    def test_do_not_expand_env_var_that_is_unset(self):
        # Unset env vars shouldn't expand.
        with self.assertRaises(NotADirectoryError):
            address_book.VdirAddressBook(
                "test", "test/fixture/test.abook${}".format("KHARD_FOO"))

    @mock.patch.dict("os.environ", KHARD_FOO="")
    def test_expand_env_var_that_is_empty(self):
        # Env vars set to empty string should expand to empty string.
        abook = address_book.VdirAddressBook(
            "test", "test/fixture/test.abook${}".format("KHARD_FOO"))
        self.assertEqual(abook.path, "test/fixture/test.abook")

    @mock.patch.dict("os.environ", KHARD_FOO="test/fixture")
    def test_expand_env_var_that_is_nonempty(self):
        # Env vars set to nonempty string should expand appropriately.
        abook = address_book.VdirAddressBook(
            "test", "${}/test.abook".format("KHARD_FOO"))
        self.assertEqual(abook.path, "test/fixture/test.abook")


class VcardAddressBookSearch(unittest.TestCase):

    @staticmethod
    def _search(query):
        with TmpAbook(["contact1.vcf", "contact2.vcf"]) as abook:
            return list(abook.search(query))

    def test_uid_query(self):
        q = query.FieldQuery("uid", "testuid1")
        l = self._search(q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid1')

    def test_term_query(self):
        q = query.TermQuery("testuid1")
        l = self._search(q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid1')

    def test_term_query_matching(self):
        q = query.TermQuery("second contact")
        l = self._search(q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid1')

    def test_term_query_failing(self):
        q = query.TermQuery("this does not match")
        l = self._search(q)
        self.assertEqual(len(l), 0)

    def test_copied_from_merge_test_1(self):
        q = query.TermQuery("second")
        l = self._search(q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid1')

    def test_copied_from_merge_test_2(self):
        q = query.TermQuery("third")
        l = self._search(q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid2')


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
        abook = address_book.VdirAddressBook('test', 'test/fixture/test.abook')
        c = abook.search(query.TermQuery('testuid1'))
        self.assertEqual(len(list(c)), 1)
