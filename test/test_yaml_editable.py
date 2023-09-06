"""Tests for the carddav_object.YAMLEditable class"""

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
        yaml_editable._add_post_address("home", "", "", "street 1", "zip1",
                                        "city1", "", "")
        yaml_editable._add_post_address("home", "", "", "street 2", "zip2",
                                        "city2", "", "")
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



class ExceptionHandling(unittest.TestCase):

    def test_duplicate_key_errors_are_translated_to_value_errors(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{key: value, key: again}")

    def test_parser_error_is_translated_to_value_error(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{[invalid yaml")
