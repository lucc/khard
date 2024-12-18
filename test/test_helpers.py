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

    def test_preparing_multiple_addresses_with_same_label_for_yaml_conversion_returns_all_entries(self):
        input = {'home': [{'street': 'street 1',
                           'city': 'city1',
                           'code': 'zip1',
                           'country': ''},
                          {'street': 'street 2',
                           'city': 'city2',
                           'code': 'zip2',
                           'country': ''}]}
        expected = [{'Street': 'street 1',
                     'City': 'city1',
                     'Code': 'zip1',
                     'Country': None},
                    {'Street': 'street 2',
                     'City': 'city2',
                     'Code': 'zip2',
                     'Country': None}]
        actual = helpers.yaml_addresses(input, ["Street", "Code", "City",
                                                "Country"])
        self.assertEqual(expected, actual["home"])

    def test_preparing_single_addresse_for_yaml_conversion_returns_dict_not_list(self):
        input = {'home': [{'street': 'street', 'city': 'city', 'code': 'zip',
                           'country': ''}]}
        expected = {'Street': 'street', 'City': 'city', 'Code': 'zip',
                    'Country': None}
        actual = helpers.yaml_addresses(input, ["Street", "Code", "City",
                                                "Country"])
        self.assertEqual(expected, actual["home"])


if __name__ == "__main__":
    unittest.main()
