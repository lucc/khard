"""Unittests for the khard module"""

from argparse import Namespace
import unittest
from unittest import mock

from khard import khard
from khard import query


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
