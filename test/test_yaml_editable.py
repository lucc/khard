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


class ExceptionHandling(unittest.TestCase):

    def test_duplicate_key_errors_are_translated_to_value_errors(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{key: value, key: again}")

    def test_parser_error_is_translated_to_value_error(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{[invalid yaml")
