"""Tests for the vcard formatting functions"""

import unittest

from vobject.vcard import Name

from khard.carddav_object import CarddavObject
from khard.formatter import Formatter

from .helpers import create_test_vcard


class FormatLabeledField(unittest.TestCase):

    def test_labels_are_selected_alphabetically_if_no_preferred_given(self):
        labeled_field = {'some': ['thing'], 'other': ['thing']}
        preferred = []
        expected = 'other: thing'
        self.assertEqual(expected, Formatter.format_labeled_field(
            labeled_field, preferred))

    def test_labels_are_selected_alphabetically_if_no_preferred_matches(self):
        labeled_field = {'some': ['thing'], 'other': ['thing']}
        preferred = ['nonexistent']
        expected = 'other: thing'
        self.assertEqual(expected, Formatter.format_labeled_field(
            labeled_field, preferred))

    def test_preferred_labels_are_used(self):
        labeled_field = {'some': ['thing'], 'other': ['thing']}
        preferred = ['some']
        expected = 'some: thing'
        self.assertEqual(expected, Formatter.format_labeled_field(
            labeled_field, preferred))

    def test_alphabetically_first_value_is_used(self):
        labeled_field = {'some': ['thing', 'more']}
        preferred = []
        expected = 'some: more'
        self.assertEqual(expected, Formatter.format_labeled_field(
            labeled_field, preferred))

    def test_not_only_first_char_of_label_is_used(self):
        preferred = []
        labeled_field = {'x-foo': ['foo'], 'x-bar': ['bar']}
        expected = 'x-bar: bar'
        self.assertEqual(expected, Formatter.format_labeled_field(
            labeled_field, preferred))
        expected = 'bar: bar'
        labeled_field = {'foo': ['foo'], 'bar': ['bar']}
        self.assertEqual(expected, Formatter.format_labeled_field(
            labeled_field, preferred))


class GetSpecialField(unittest.TestCase):

    _name = Name(family='Family', given='Given', additional='Additional',
                 prefix='Prefix', suffix='Suffix')
    _vcard = CarddavObject(create_test_vcard(fn="Formatted Name", n=_name,
                                             nickname="Nickname"), None, "")

    def _test_name(self, fmt, nick, expected):
        f = Formatter(fmt, [], [], nick)
        actual = f.get_special_field(self._vcard, "name")
        self.assertEqual(expected, actual)

    def test_name_formatted_as_first_name_last_name(self):
        self._test_name(Formatter.FIRST, False, "Given Additional Family")

    def test_name_formatted_as_first_name_last_name_with_nickname(self):
        self._test_name(Formatter.FIRST, True,
                        "Given Additional Family (Nickname: Nickname)")

    def test_name_formatted_as_last_name_first_name(self):
        self._test_name(Formatter.LAST, False, "Family, Given Additional")

    def test_name_formatted_as_last_name_first_name_with_nickname(self):
        self._test_name(Formatter.LAST, True,
                        "Family, Given Additional (Nickname: Nickname)")

    def test_name_formatted_as_formatted_name(self):
        self._test_name(Formatter.FORMAT, False, "Formatted Name")

    def test_name_formatted_as_formatted_name_with_nickname(self):
        self._test_name(Formatter.FORMAT, True,
                        "Formatted Name (Nickname: Nickname)")
