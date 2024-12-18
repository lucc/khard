"""Unittests for the khard module"""

from argparse import Namespace
from email.headerregistry import Address
import unittest
from unittest import mock

from khard import khard, query, config
from khard.khard import find_email_addresses

from .helpers import TmpAbook, load_contact


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


class TestFindEmailAddress(unittest.TestCase):

    def test_empty_text_finds_none(self):
        text = ""
        addrs = find_email_addresses(text, ["from"])
        self.assertEqual([], addrs)

    def test_single_header_finds_one_address(self):
        text = """From: John Doe <jdoe@machine.example>"""
        addrs = find_email_addresses(text, ["from"])
        expected = [Address(display_name="John Doe",
                            username="jdoe", domain="machine.example")]
        self.assertEqual(expected, addrs)

    def test_single_header_finds_multiple_addresses(self):
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

    def test_non_address_header_finds_none(self):
        text = "From: John Doe <jdoe@machine.example>, " \
            "Mary Smith <mary@example.net>\nOther: test"
        addrs = find_email_addresses(text, ["other"])
        expected = []
        self.assertEqual(expected, addrs)

    def test_multiple_headers_finds_some(self):
        text = "From: John Doe <jdoe@machine.example>, " \
            "Mary Smith <mary@example.net>\nOther: test"
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

    def test_multiple_headers_finds_all(self):
        text = "From: John Doe <jdoe@machine.example>, " \
            "Mary Smith <mary@example.net>\n" \
            "To: Michael Jones <mjones@machine.example>"
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

    def test_finds_all_emails(self):
        text = "From: John Doe <jdoe@machine.example>, " \
            "Mary Smith <mary@example.net>\n" \
            "To: Michael Jones <mjones@machine.example>"
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

    def test_finds_all_emails_with_other_headers_too(
            self):
        text = "From: John Doe <jdoe@machine.example>, " \
            "Mary Smith <mary@example.net>\n" \
            "To: Michael Jones <mjones@machine.example>"
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


class TestGetContactListByUserSelection(unittest.TestCase):

    def setUp(self):
        """initialize the global config object with a mock"""
        khard.config = mock.Mock(spec=config.Config)
        khard.config.group_by_addressbook = False
        khard.config.reverse = False
        khard.config.sort = "last_name"

    def tearDown(self):
        del khard.config

    def test_uid_query_without_strict_search(self):
        q = query.FieldQuery("uid", "testuid1")
        with TmpAbook(["contact1.vcf", "contact2.vcf"]) as abook:
            l = khard.get_contact_list(abook, q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid1')

    def test_name_query_with_uid_text_and_strict_search(self):
        q = query.NameQuery("testuid1")
        with TmpAbook(["contact1.vcf", "contact2.vcf"]) as abook:
            l = khard.get_contact_list(abook, q)
        self.assertEqual(len(l), 0)

    def test_name_query_with_uid_text_and_without_strict_search(self):
        q = query.NameQuery("testuid1")
        with TmpAbook(["contact1.vcf", "contact2.vcf"]) as abook:
            l = khard.get_contact_list(abook, q)
        self.assertEqual(len(l), 0)

    def test_term_query_without_strict_search(self):
        q = query.TermQuery("testuid1")
        with TmpAbook(["contact1.vcf", "contact2.vcf"]) as abook:
            l = khard.get_contact_list(abook, q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid1')

    def test_term_query_with_strict_search_matching(self):
        q = query.TermQuery("second contact")
        with TmpAbook(["contact1.vcf", "contact2.vcf"]) as abook:
            l = khard.get_contact_list(abook, q)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].uid, 'testuid1')


class TestSortContacts(unittest.TestCase):

    contact1 = load_contact("contact1.vcf")
    contact2 = load_contact("contact2.vcf")
    nickname = load_contact("nickname.vcf")
    no_nickname = load_contact("no-nickname.vcf")

    def _test(self, first, second, **kwargs):
        """Run the sort_contacts function and assert the result

        The two contacts first and second are expected to come out in that
        order and are deliberatly put into the function in the reverse order.
        """
        actual = khard.sort_contacts([second, first], **kwargs)
        self.assertListEqual(actual, [first, second])

    def test_sorts_by_first_name_by_default(self):
        self._test(self.nickname, self.no_nickname)

    def test_reverses_sort_order(self):
        self._test(self.no_nickname, self.nickname, reverse=True)

    def test_can_sort_by_last_name(self):
        self._test(self.no_nickname, self.nickname, sort="last_name")

    def test_can_sort_by_formatted_name(self):
        self._test(self.contact1, self.contact2, sort="formatted_name")

    def test_group_by_addressbook(self):
        with TmpAbook(["contact1.vcf", "category.vcf"], name="one") as abook1:
            with TmpAbook(["contact2.vcf", "labels.vcf"],
                          name="two") as abook2:
                contact1 = next(abook1.search(query.FieldQuery("uid",
                                                               "testuid1")))
                category = next(abook1.search(query.NameQuery("category")))
                contact2 = next(abook2.search(query.FieldQuery("uid",
                                                               "testuid2")))
                labels = next(abook2.search(query.NameQuery("labeled guy")))
        expected = [category, contact1, labels, contact2]
        actual = khard.sort_contacts([contact1, contact2, category, labels],
                                     group=True)
        self.assertListEqual(actual, expected)
