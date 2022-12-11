"""Tests for the cli module"""

from argparse import ArgumentTypeError
import tempfile
import unittest
from unittest import mock

from khard import cli
from khard import query

from .helpers import mock_stream


class TestFieldsArgument(unittest.TestCase):

    def test_works_when_choices_match(self):
        t = cli.FieldsArgument("a", "b")
        actual = t("a,b")
        expected = ["a", "b"]
        self.assertListEqual(actual, expected)

    def test_raises_exception_when_choices_dont_match(self):
        t = cli.FieldsArgument("a", "b")
        with self.assertRaises(ArgumentTypeError):
            t("a,c")

    def test_case_does_not_matter(self):
        t = cli.FieldsArgument("a", "b")
        actual = t("a,B")
        expected = ["a", "b"]
        self.assertListEqual(actual, expected)

    def test_only_first_component_must_match_choices_with_nested(self):
        t = cli.FieldsArgument("a", "b", nested=True)
        actual = t("a.c,b")
        expected = ["a.c", "b"]
        self.assertListEqual(actual, expected)


@mock.patch.dict('os.environ', KHARD_CONFIG='test/fixture/minimal.conf')
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

    def test_add_email_defaults_to_from_lowercase(self):
        args, _config = cli.parse_args(["add-email"])
        actual = args.headers
        self.assertEqual(["from"], actual)

    def test_add_email_from_field(self):
        args, _config = cli.parse_args(["add-email", "-H", "from"])
        actual = args.headers
        self.assertEqual(["from"], actual)

    def test_add_email_another_field(self):
        args, _config = cli.parse_args(["add-email", "-H", "OtHer"])
        actual = args.headers
        self.assertEqual(["other"], actual)

    def test_add_email_multiple_headers_separate_args_takes_last(self):
        args, _config = cli.parse_args(
            ["add-email", "-H", "OtHer", "-H", "myfield"])
        actual = args.headers
        self.assertEqual(["myfield"], actual)

    def test_add_email_multiple_headers_comma_separated(self):
        args, _config = cli.parse_args(
            ["add-email", "-H", "OtHer,myfield,from"])
        actual = args.headers
        self.assertEqual(["other", "myfield", "from"], actual)

    def test_exit_user_friendly_without_config_file(self):
        with self.assertRaises(SystemExit):
            cli.parse_args(["-c", "/this file should hopefully never exist."])

    def test_exit_user_friendly_without_contacts_folder(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as config:
            config.write("""[general]
                            editor = editor
                            merge_editor = merge_editor
                            [addressbooks]
                            [[tmp]]
                            path = /this file should hopefully never exist.
                            """)
            config.flush()
            with self.assertRaises(SystemExit):
                cli.init(["-c", config.name, "ls"])
