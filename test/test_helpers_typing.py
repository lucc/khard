"""Tests for runtime type conversions"""

import unittest

from khard.carddav_object import convert_to_vcard
from khard.object_type import ObjectType


class ConvertToVcard(unittest.TestCase):

    def test_returns_strings(self):
        value = "some text"
        actual = convert_to_vcard("test", value, ObjectType.string)
        self.assertEqual(value, actual)

    def test_returns_lists(self):
        value = ["some", "text"]
        actual = convert_to_vcard("test", value, ObjectType.list_with_strings)
        self.assertListEqual(value, actual)

    def test_fail_if_not_string(self):
        value = ["some", "text"]
        with self.assertRaises(ValueError):
            convert_to_vcard("test", value, ObjectType.string)

    def test_upgrades_string_to_list(self):
        value = "some text"
        actual = convert_to_vcard("test", value, ObjectType.list_with_strings)
        self.assertListEqual([value], actual)

    def test_fails_if_string_lists_are_not_homogenous(self):
        value = ["some", ["nested", "list"]]
        with self.assertRaises(ValueError):
            convert_to_vcard("test", value, ObjectType.list_with_strings)

    def test_empty_list_items_are_filtered(self):
        value = ["some", "", "text", "", "more text"]
        actual = convert_to_vcard("test", value, ObjectType.list_with_strings)
        self.assertListEqual(["some", "text", "more text"], actual)

    def test_strings_are_stripped(self):
        value = " some text "
        actual = convert_to_vcard("test", value, ObjectType.string)
        self.assertEqual("some text", actual)

    def test_strings_in_lists_are_stripped(self):
        value = [" some ", " text "]
        actual = convert_to_vcard("test", value, ObjectType.list_with_strings)
        self.assertListEqual(["some", "text"], actual)
