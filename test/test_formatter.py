"""Tests for the vcard formatting functions"""

import unittest

from vobject.vcard import Name

from khard.carddav_object import CarddavObject
from khard.formatter import Formatter

from .helpers import vCard


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
    _vcard = CarddavObject(vCard(fn="Formatted Name", n=_name,
                                 nickname="Nickname"), None, "")

    def _test_name(self, fmt, nick, parsable, expected):
        f = Formatter(fmt, [], [], nick, parsable)
        actual = f.get_special_field(self._vcard, "name")
        self.assertEqual(expected, actual)

    def test_name_formatted_as_first_name_last_name(self):
        self._test_name(Formatter.FIRST, False, False,
                        "Given Additional Family")

    def test_name_formatted_as_first_name_last_name_with_nickname(self):
        self._test_name(Formatter.FIRST, True, False,
                        "Given Additional Family (Nickname: Nickname)")

    def test_name_formatted_as_last_name_first_name(self):
        self._test_name(Formatter.LAST, False, False,
                        "Family, Given Additional")

    def test_name_formatted_as_last_name_first_name_with_nickname(self):
        self._test_name(Formatter.LAST, True, False,
                        "Family, Given Additional (Nickname: Nickname)")

    def test_name_formatted_as_formatted_name(self):
        self._test_name(Formatter.FORMAT, False, False, "Formatted Name")

    def test_name_formatted_as_formatted_name_with_nickname(self):
        self._test_name(Formatter.FORMAT, True, False,
                        "Formatted Name (Nickname: Nickname)")

    def test_parsable_overrides_nickname_with_first_formatting(self):
        self._test_name(Formatter.FIRST, True, True, "Given Additional Family")

    def test_parsable_overrides_nickname_with_last_formatting(self):
        self._test_name(Formatter.LAST, True, True, "Family, Given Additional")

    def test_parsable_overrides_nickname_with_formatted_name(self):
        self._test_name(Formatter.FORMAT, True, True, "Formatted Name")
