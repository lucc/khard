"""Tests for runtime type conversions"""

import unittest

from khard.helpers.typing import convert_to_vcard, ObjectType


class ConvertToVcard(unittest.TestCase):

    def test_returns_strings(self):
        value = "some text"
        actual = convert_to_vcard("test", value, ObjectType.str)
        self.assertEqual(value, actual)

    def test_returns_lists(self):
        value = ["some", "text"]
        actual = convert_to_vcard("test", value, ObjectType.list)
        self.assertListEqual(value, actual)

    def test_fail_if_not_string(self):
        value = ["some", "text"]
        with self.assertRaises(ValueError):
            convert_to_vcard("test", value, ObjectType.str)

    def test_upgrades_string_to_list(self):
        value = "some text"
        actual = convert_to_vcard("test", value, ObjectType.list)
        self.assertListEqual([value], actual)

    def test_fails_if_string_lists_are_not_homogenous(self):
        value = ["some", ["nested", "list"]]
        with self.assertRaises(ValueError):
            convert_to_vcard("test", value, ObjectType.list)

    def test_empty_list_items_are_filtered(self):
        value = ["some", "", "text", "", "more text"]
        actual = convert_to_vcard("test", value, ObjectType.list)
        self.assertListEqual(["some", "text", "more text"], actual)

    def test_strings_are_stripped(self):
        value = " some text "
        actual = convert_to_vcard("test", value, ObjectType.str)
        self.assertEqual("some text", actual)

    def test_strings_in_lists_are_stripped(self):
        value = [" some ", " text "]
        actual = convert_to_vcard("test", value, ObjectType.list)
        self.assertListEqual(["some", "text"], actual)
