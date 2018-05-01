"""Tests for the custom YAML format."""

import unittest
from unittest import mock

from khard.carddav_object import CarddavObject


class EmptyFieldsAndSpaces(unittest.TestCase):

    @staticmethod
    def _parse_yaml(yaml=''):
        """Parse some yaml string into a CarddavObject

        :param yaml: the yaml input string to parse
        :type yaml: str
        :returns: the parsed CarddavObject
        :rtype: CarddavObject
        """
        # Careful, this function doesn't actually support named arguments so
        # they have to be kept in this order!
        return CarddavObject.from_user_input(
                address_book=mock.Mock(path='foo-path'), user_input=yaml,
                supported_private_objects=[], version='3.0',
                localize_dates=False)

    def test_empty_birthday_in_yaml_input(self):
        empty_birthday = "First name: foo\nBirthday:"
        x = self._parse_yaml(empty_birthday)
        self.assertIsNone(x.get_birthday())

    def test_only_spaces_in_birthday_in_yaml_input(self):
        spaces_birthday = "First name: foo\nBirthday:  "
        x = self._parse_yaml(spaces_birthday)
        self.assertIsNone(x.get_birthday())

    def test_empty_anniversary_in_yaml_input(self):
        empty_anniversary = "First name: foo\nAnniversary:"
        x = self._parse_yaml(empty_anniversary)
        self.assertIsNone(x.get_anniversary())

    def test_empty_organisation_in_yaml_input(self):
        empty_organisation = "First name: foo\nOrganisation:"
        x = self._parse_yaml(empty_organisation)
        self.assertListEqual(x._get_organisations(), [])

    def test_empty_nickname_in_yaml_input(self):
        empty_nickname = "First name: foo\nNickname:"
        x = self._parse_yaml(empty_nickname)
        self.assertListEqual(x.get_nicknames(), [])

    def test_empty_role_in_yaml_input(self):
        empty_role = "First name: foo\nRole:"
        x = self._parse_yaml(empty_role)
        self.assertListEqual(x._get_roles(), [])

    def test_empty_title_in_yaml_input(self):
        empty_title = "First name: foo\nTitle:"
        x = self._parse_yaml(empty_title)
        self.assertListEqual(x._get_titles(), [])

    def test_empty_categories_in_yaml_input(self):
        empty_categories = "First name: foo\nCategories:"
        x = self._parse_yaml(empty_categories)
        self.assertListEqual(x._get_categories(), [])

    def test_empty_webpage_in_yaml_input(self):
        empty_webpage = "First name: foo\nWebpage:"
        x = self._parse_yaml(empty_webpage)
        self.assertListEqual(x._get_webpages(), [])

    def test_empty_note_in_yaml_input(self):
        empty_note = "First name: foo\nNote:"
        x = self._parse_yaml(empty_note)
        self.assertListEqual(x._get_notes(), [])
