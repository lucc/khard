"""Tests for the cli module"""

import unittest

from khard import cli
from khard import query


class TestParseArgs(unittest.TestCase):

    foo = query.TermQuery("foo")
    bar = query.TermQuery("bar")
    uid = query.FieldQuery("uid", "foo")

    def test_normal_search_terms_create_term_queries(self):
        expected = self.foo
        args, _config = cli.parse_args(['list', 'foo'])
        actual = args.search_terms
        self.assertEqual(expected, actual)

    def test_uid_options_create_uid_queries(self):
        expected = self.uid
        args, _config = cli.parse_args(['list', '--uid=foo'])
        actual = args.uid
        self.assertEqual(expected, actual)

    def test_multible_search_terms_generate_and_queries(self):
        expected = query.AndQuery(self.foo, self.bar)
        args, _config = cli.parse_args(['list', 'foo', 'bar'])
        actual = args.search_terms
        self.assertEqual(expected, actual)
