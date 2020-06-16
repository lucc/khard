"""Unittests for the khard module"""

from argparse import Namespace
import unittest
from unittest import mock

from email.headerregistry import Address

from khard import khard, query, address_book
from khard.khard import find_email_addresses


class TestSearchQueryPreparation(unittest.TestCase):

    foo = query.TermQuery("foo")
    bar = query.TermQuery("bar")

    def setUp(self):
        # Set the uninitialized global variable in the khard module to make it
        # mockable. See https://stackoverflow.com/questions/61193676
        khard.config = mock.Mock()

    @staticmethod
    def _make_abook(name):
        abook = mock.Mock()
        abook.name = name
        return abook

    @classmethod
    def _run(cls, **kwargs):
        with mock.patch("khard.khard.config.abooks",
                        [cls._make_abook(name)
                         for name in ["foo", "bar", "baz"]]):
            return khard.prepare_search_queries(Namespace(**kwargs))

    def test_queries_for_the_same_address_book_are_joind_by_disjunction(self):
        expected = self.foo | self.bar
        prepared = self._run(addressbook=["foo"], target_addressbook=["foo"],
                             source_search_terms=self.foo,
                             target_contact=self.bar)
        self.assertEqual(expected, prepared["foo"])

    def test_no_search_terms_result_in_any_queries(self):
        expected = query.AnyQuery()
        prepared = self._run(addressbook=["foo"], target_addressbook=["foo"],
                             source_search_terms=query.AnyQuery(),
                             target_contact=query.AnyQuery())
        self.assertEqual(expected, prepared["foo"])


class TestAddEmail(unittest.TestCase):

    def test_find_email_addresses_empty_text_finds_none(self):
        text = ""
        addrs = find_email_addresses(text, ["from"])
        self.assertEqual([], addrs)

    def test_find_email_addresses_single_header_finds_one_address(self):
        text = """From: John Doe <jdoe@machine.example>"""
        addrs = find_email_addresses(text, ["from"])
        expected = [Address(display_name="John Doe",
                            username="jdoe", domain="machine.example")]
        self.assertEqual(expected, addrs)

    def test_find_email_addresses_single_header_finds_multiple_addresses(self):
        text = """From: John Doe <jdoe@machine.example>, \
                Mary Smith <mary@example.net>"""
        addrs = find_email_addresses(text, ["from"])
        expected = [
            Address(
                display_name="John Doe",
                username="jdoe",
                domain="machine.example"),
            Address(
                display_name="Mary Smith",
                username="mary",
                domain="example.net")]
        self.assertEqual(expected, addrs)

    def test_find_email_addresses_non_address_header_finds_none(self):
        text = """From: John Doe <jdoe@machine.example>, \
                Mary Smith <mary@example.net>
Other: test"""
        addrs = find_email_addresses(text, ["other"])
        expected = []
        self.assertEqual(expected, addrs)

    def test_find_email_addresses_multiple_headers_finds_some(self):
        text = """From: John Doe <jdoe@machine.example>, \
                Mary Smith <mary@example.net>
Other: test"""
        addrs = find_email_addresses(text, ["other", "from"])
        expected = [
            Address(
                display_name="John Doe",
                username="jdoe",
                domain="machine.example"),
            Address(
                display_name="Mary Smith",
                username="mary",
                domain="example.net")]
        self.assertEqual(expected, addrs)

    def test_find_email_addresses_multiple_headers_finds_all(self):
        text = """From: John Doe <jdoe@machine.example>, \
                Mary Smith <mary@example.net>
To: Michael Jones <mjones@machine.example>"""
        addrs = find_email_addresses(text, ["to", "FrOm"])
        expected = [
            Address(
                display_name="Michael Jones",
                username="mjones",
                domain="machine.example"),
            Address(
                display_name="John Doe",
                username="jdoe",
                domain="machine.example"),
            Address(
                display_name="Mary Smith",
                username="mary",
                domain="example.net")]
        self.assertEqual(expected, addrs)

    def test_find_email_addresses_finds_all_emails(self):
        text = """From: John Doe <jdoe@machine.example>, \
                Mary Smith <mary@example.net>
To: Michael Jones <mjones@machine.example>"""
        addrs = find_email_addresses(text, ["all"])
        expected = [
            Address(
                display_name="John Doe",
                username="jdoe",
                domain="machine.example"),
            Address(
                display_name="Mary Smith",
                username="mary",
                domain="example.net"),
            Address(
                display_name="Michael Jones",
                username="mjones",
                domain="machine.example")]
        self.assertEqual(expected, addrs)

    def test_find_email_addresses_finds_all_emails_with_other_headers_too(
            self):
        text = """From: John Doe <jdoe@machine.example>, \
                Mary Smith <mary@example.net>
To: Michael Jones <mjones@machine.example>"""
        addrs = find_email_addresses(text, ["other", "all", "from"])
        expected = [
            Address(
                display_name="John Doe",
                username="jdoe",
                domain="machine.example"),
            Address(
                display_name="Mary Smith",
                username="mary",
                domain="example.net"),
            Address(
                display_name="Michael Jones",
                username="mjones",
                domain="machine.example")]
        self.assertEqual(expected, addrs)

class TestSearchContacts(unittest.TestCase):

    def test_get_contact_list_by_user_selection(self):
        abook = address_book.VdirAddressBook('test', 'test/fixture/multiemail.abook')
        with mock.patch("khard.khard.config.sort", "last_name"):
            with mock.patch("khard.khard.config.group_by_addressbook", False):
                with mock.patch("khard.khard.config.reverse", False):
                    # copied from add_email_to_contact, notice it sets strict_search to True
                    l = khard.get_contact_list_by_user_selection(abook, query.TermQuery("searchme"), True)
                    self.assertEqual(len(l), 1)
