"""Tests for the cli module"""

import unittest

from khard import cli
from khard import query

from .helpers import mock_stream


class TestParseArgs(unittest.TestCase):

    foo = query.TermQuery("foo")
    bar = query.TermQuery("bar")
    baz = query.TermQuery("baz")
    uid = query.FieldQuery("uid", "foo")

    def test_normal_search_terms_create_term_queries(self):
        expected = self.foo
        args, _config = cli.parse_args(['list', 'foo'])
        actual = args.search_terms
        self.assertEqual(expected, actual)

    def test_uid_options_create_uid_queries(self):
        expected = self.uid
        args, _config = cli.parse_args(['list', '--uid=foo'])
        actual = args.search_terms
        self.assertEqual(expected, actual)

    def test_multible_search_terms_generate_and_queries(self):
        expected = query.AndQuery(self.foo, self.bar)
        args, _config = cli.parse_args(['list', 'foo', 'bar'])
        actual = args.search_terms
        self.assertEqual(expected, actual)

    def test_no_search_terms_create_an_any_query(self):
        expected = query.AnyQuery()
        args, _config = cli.parse_args(['list'])
        actual = args.search_terms
        self.assertEqual(expected, actual)

    def test_target_search_terms_are_typed(self):
        args, _config = cli.parse_args(['merge', '--target=foo', 'bar'])
        self.assertEqual(self.foo, args.target_contact)
        self.assertEqual(self.bar, args.source_search_terms)

    def test_second_target_search_term_overrides_first(self):
        args, _config = cli.parse_args(['merge', '--target=foo',
                                        '--target=bar', 'baz'])
        self.assertEqual(self.bar, args.target_contact)
        self.assertEqual(self.baz, args.source_search_terms)

    def test_target_uid_option_creates_uid_queries(self):
        args, _config = cli.parse_args(['merge', '--target-uid=foo', 'bar'])
        self.assertEqual(self.uid, args.target_contact)
        self.assertEqual(self.bar, args.source_search_terms)

    def test_uid_option_is_combined_with_search_terms_for_merge_command(self):
        args, _config = cli.parse_args(['merge', '--uid=foo', '--target=bar'])
        self.assertEqual(self.uid, args.source_search_terms)
        self.assertEqual(self.bar, args.target_contact)

    def test_uid_and_free_search_terms_produce_a_conflict(self):
        with self.assertRaises(SystemExit):
            with mock_stream("stderr"):  # just silence stderr
                cli.parse_args(['list', '--uid=foo', 'bar'])

    def test_target_uid_and_free_target_search_terms_produce_a_conflict(self):
        with self.assertRaises(SystemExit):
            with mock_stream("stderr"):  # just silence stderr
                cli.parse_args(['merge', '--target-uid=foo', '--target=bar'])

    def test_no_target_specification_results_in_an_any_query(self):
        expected = query.AnyQuery()
        args, _config = cli.parse_args(['merge'])
        actual = args.target_contact
        self.assertEqual(expected, actual)
