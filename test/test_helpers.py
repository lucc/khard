"""Tests for the helpers module."""
# pylint: disable=missing-docstring

import unittest

from khard import helpers


class ConvertToYAML(unittest.TestCase):

    def test_colon_handling(self):
        result = helpers.convert_to_yaml("Note", "foo: bar", 0, 5, True)
        self.assertListEqual(result, ["Note : |\n    foo: bar"])

    def test_none_values_produce_no_output(self):
        result = helpers.convert_to_yaml("Note", None, 0, 5, True)
        self.assertListEqual(result, [])

    def test_empty_strings_produce_empty_values(self):
        result = helpers.convert_to_yaml("Note", "", 0, 5, True)
        self.assertListEqual(result, ["Note : "])


if __name__ == "__main__":
    unittest.main()
