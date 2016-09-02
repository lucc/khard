"""Tests for the helpers module."""

import datetime
import unittest

from khard import helpers


class ListToString(unittest.TestCase):

    def test_empty_list_returns_empty_string(self):
        the_list = []
        delimiter = ' '
        expected = ''
        actual = helpers.list_to_string(the_list, delimiter)
        self.assertEqual(actual, expected)

    def test_simple_list(self):
        the_list = ['a', 'bc', 'def']
        delimiter = ' '
        expected = 'a bc def'
        actual = helpers.list_to_string(the_list, delimiter)
        self.assertEqual(actual, expected)

    def test_simple_nested_list(self):
        the_list = ['a', 'bc', ['x', 'y', 'z'], 'def']
        delimiter = ' '
        expected = 'a bc x y z def'
        actual = helpers.list_to_string(the_list, delimiter)
        self.assertEqual(actual, expected)

    def test_multi_level_nested_list(self):
        the_list = ['a', ['b', ['c', [[['x', 'y']]]]], 'z']
        delimiter = ' '
        expected = 'a b c x y z'
        actual = helpers.list_to_string(the_list, delimiter)
        self.assertEqual(actual, expected)

    def test_list_to_string_passes_through_other_objects(self):
        self.assertIs(helpers.list_to_string(None, "foo"), None)
        self.assertIs(helpers.list_to_string(42, "foo"), 42)
        self.assertIs(helpers.list_to_string("foo bar", "foo"), "foo bar")


class StringToDate(unittest.TestCase):

    date = datetime.datetime(year=1900, month=1, day=2)
    time = datetime.datetime(year=1900, month=1, day=2, hour=12, minute=42,
                             second=17)
    zone = datetime.datetime(year=1900, month=1, day=2, hour=12, minute=42,
                             second=17, tzinfo=datetime.timezone.utc)

    def test_mmdd_format(self):
        string = '--0102'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.date)

    def test_mm_dd_format(self):
        string = '--01-02'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.date)

    def test_yyyymmdd_format(self):
        string = '19000102'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.date)

    def test_yyyy_mm_dd_format(self):
        string = '1900-01-02'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.date)

    def test_yyyymmddThhmmss_format(self):
        string = '19000102T124217'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.time)

    def test_yyyy_mm_ddThh_mm_ss_format(self):
        string = '1900-01-02T12:42:17'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.time)

    def test_yyyymmddThhmmssZ_format(self):
        string = '19000102T124217Z'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.time)

    def test_yyyy_mm_ddThh_mm_ssZ_format(self):
        string = '1900-01-02T12:42:17Z'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.time)

    def test_yyyymmddThhmmssz_format(self):
        string = '19000102T064217-06:00'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.zone)

    def test_yyyy_mm_ddThh_mm_ssz_format(self):
        string = '1900-01-02T06:42:17-06:00'
        result = helpers.string_to_date(string)
        self.assertEqual(result, self.zone)


if __name__ == "__main__":
    unittest.main()
