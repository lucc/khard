"""Tests for the carddav_object.YAMLEditable class"""

import unittest
from unittest import mock

from khard.carddav_object import YAMLEditable

from .helpers import TestYAMLEditable


class ExceptionHandling(unittest.TestCase):

    def test_duplicate_key_errors_are_translated_to_value_errors(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{key: value, key: again}")

    def test_parser_error_is_translated_to_value_error(self):
        ye = TestYAMLEditable()
        with self.assertRaises(ValueError):
            ye.update("{[invalid yaml")
