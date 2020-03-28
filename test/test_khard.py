"""Test auxiliary functions from the main khard module"""

import unittest

from khard import khard


class FormatLabeledField(unittest.TestCase):

    def test_labels_are_selected_alphabetically_if_no_preferred_given(self):
        labeled_field = {'some': ['thing'], 'other': ['thing']}
        preferred = []
        expected = 'other: thing'
        self.assertEqual(expected,
                         khard.format_labeled_field(labeled_field, preferred))

    def test_labels_are_selected_alphabetically_if_no_preferred_matches(self):
        labeled_field = {'some': ['thing'], 'other': ['thing']}
        preferred = ['nonexistent']
        expected = 'other: thing'
        self.assertEqual(expected,
                         khard.format_labeled_field(labeled_field, preferred))

    def test_preferred_labels_are_used(self):
        labeled_field = {'some': ['thing'], 'other': ['thing']}
        preferred = ['some']
        expected = 'some: thing'
        self.assertEqual(expected,
                         khard.format_labeled_field(labeled_field, preferred))

    def test_alphabetically_first_value_is_used(self):
        labeled_field = {'some': ['thing', 'more']}
        preferred = []
        expected = 'some: more'
        self.assertEqual(expected,
                         khard.format_labeled_field(labeled_field, preferred))

    def test_not_only_first_char_of_label_is_used(self):
        preferred = []
        labeled_field = {'x-foo': ['foo'], 'x-bar': ['bar']}
        expected = 'x-bar: bar'
        self.assertEqual(expected,
                         khard.format_labeled_field(labeled_field, preferred))
        expected = 'bar: bar'
        labeled_field = {'foo': ['foo'], 'bar': ['bar']}
        self.assertEqual(expected,
                         khard.format_labeled_field(labeled_field, preferred))
