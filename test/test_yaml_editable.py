"""Tests for the contacts.YAMLEditable class"""

import unittest

from .helpers import TestYAMLEditable


class ToYamlConversion(unittest.TestCase):
    def test_yaml_quoted_special_characters(self):
        yaml_editable = TestYAMLEditable()
        yaml_editable.supported_private_objects = ["Twitter"]
        yaml_repr = """
Formatted name: Test vCard
First name: Khard
Private       :
    Twitter: \"@khard\"
"""
        yaml_editable.update(yaml_repr)
        yaml_dump = yaml_editable.to_yaml()
        self.assertIn("'@khard'", yaml_dump)

    def test_dumping_multiple_home_addresses_to_yaml(self):
        yaml_editable = TestYAMLEditable()
        yaml_editable._add_post_address(
            "home", "", "", "street 1", "zip1", "city1", "", ""
        )
        yaml_editable._add_post_address(
            "home", "", "", "street 2", "zip2", "city2", "", ""
        )
        yaml_dump = yaml_editable.to_yaml()
        self.assertIn("zip1", yaml_dump)
        self.assertIn("zip2", yaml_dump)

    def test_dumping_multiple_home_phone_number_to_yaml(self):
        yaml_editable = TestYAMLEditable()
        yaml_editable._add_phone_number("home", "1234567890")
        yaml_editable._add_phone_number("home", "0987654321")
        yaml_dump = yaml_editable.to_yaml()
        self.assertIn("1234567890", yaml_dump)
        self.assertIn("0987654321", yaml_dump)

    def test_dumping_multiple_home_email_addresses_to_yaml(self):
        yaml_editable = TestYAMLEditable()
        yaml_editable.add_email("home", "home1@example.org")
        yaml_editable.add_email("home", "home2@example.org")
        yaml_dump = yaml_editable.to_yaml()
        self.assertIn("home1", yaml_dump)
        self.assertIn("home2", yaml_dump)

    def test_empty_kind_is_included_in_yaml_format(self):
        contact = TestYAMLEditable()
        yaml = contact.to_yaml()
        self.assertIn("Kind:", yaml)

    def test_kind_is_included_in_yaml_format(self):
        contact = TestYAMLEditable(version="4.0", kind="org")
        yaml = contact.to_yaml()
        self.assertIn("Kind: org", yaml)


class ExceptionHandling(unittest.TestCase):
    def test_duplicate_key_errors_are_translated_to_value_errors(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{key: value, key: again}")

    def test_parser_error_is_translated_to_value_error(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{[invalid yaml")


class PrivateObjects(unittest.TestCase):
    def test_can_add_strings(self) -> None:
        ye = TestYAMLEditable()
        ye.supported_private_objects = ["foo"]
        ye._add_private_object("foo", "bar")
        self.assertEqual(ye._get_private_objects(), {"foo": ["bar"]})

    def test_can_add_several_strings_under_the_same_label(self) -> None:
        ye = TestYAMLEditable()
        ye.supported_private_objects = ["foo"]
        ye._add_private_object("foo", "bar")
        ye._add_private_object("foo", "baz")
        self.assertEqual(ye._get_private_objects(), {"foo": ["bar", "baz"]})

    def test_unsupported_private_objects_can_be_added_but_not_retrieved(self) -> None:
        ye = TestYAMLEditable()
        ye.supported_private_objects = ["foo"]
        ye._add_private_object("foo", "bar")
        ye._add_private_object("bar", "foo")
        self.assertEqual(ye._get_private_objects(), {"foo": ["bar"]})
        self.assertIn("X-BAR:foo", ye.vcard.serialize())

    def test_private_objects_can_have_an_ablabel(self) -> None:
        ye = TestYAMLEditable()
        ye.supported_private_objects = ["foo"]
        foo = ye.vcard.add("X-FOO")
        foo.value = "bar"
        foo.group = "1"
        label = ye.vcard.add("X-ABLABEL")
        label.value = "baz"
        label.group = "1"
        result = ye._get_private_objects()
        self.assertEqual(result, {"foo": [{"baz": "bar"}]})

    def test_private_objects_with_ablabels_are_sorted_by_ablabel(self) -> None:
        ye = TestYAMLEditable()
        ye.supported_private_objects = ["foo"]
        foo1 = ye.vcard.add("X-FOO")
        foo1.value = "AAA"
        foo1.group = "1"
        label1 = ye.vcard.add("X-ABLABEL")
        label1.value = "yyy"
        label1.group = "1"
        foo2 = ye.vcard.add("X-FOO")
        foo2.value = "BBB"
        foo2.group = "2"
        label2 = ye.vcard.add("X-ABLABEL")
        label2.value = "xxx"
        label2.group = "2"
        result = ye._get_private_objects()
        self.assertEqual(result, {"foo": [{"xxx": "BBB"}, {"yyy": "AAA"}]})
