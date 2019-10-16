"""Tests for the custom YAML format."""
# pylint: disable=missing-docstring

import datetime
from io import StringIO
import unittest
from unittest import mock

from ruamel.yaml import YAML

from khard.carddav_object import CarddavObject, YAMLEditable

from . import helpers


def create_test_card():
    return YAMLEditable(helpers.create_test_vcard())


def to_yaml(data):
    if 'First name' not in data:
        data['First name'] = 'Nobody'
    stream = StringIO()
    YAML().dump(data, stream)
    return stream.getvalue()


def parse_yaml(yaml=''):
    """Parse some yaml string into a CarddavObject

    :param yaml: the yaml input string to parse
    :type yaml: str
    :returns: the parsed CarddavObject
    :rtype: CarddavObject
    """
    return CarddavObject.from_yaml(address_book=mock.Mock(path='foo-path'),
                                   yaml=yaml, supported_private_objects=[],
                                   version='3.0', localize_dates=False)


class EmptyFieldsAndSpaces(unittest.TestCase):

    def test_empty_birthday_in_yaml_input(self):
        empty_birthday = "First name: foo\nBirthday:"
        x = parse_yaml(empty_birthday)
        self.assertIsNone(x.birthday)

    def test_only_spaces_in_birthday_in_yaml_input(self):
        spaces_birthday = "First name: foo\nBirthday:  "
        x = parse_yaml(spaces_birthday)
        self.assertIsNone(x.birthday)

    def test_empty_anniversary_in_yaml_input(self):
        empty_anniversary = "First name: foo\nAnniversary:"
        x = parse_yaml(empty_anniversary)
        self.assertIsNone(x.anniversary)

    def test_empty_organisation_in_yaml_input(self):
        empty_organisation = "First name: foo\nOrganisation:"
        x = parse_yaml(empty_organisation)
        self.assertListEqual(x.organisations, [])

    def test_empty_nickname_in_yaml_input(self):
        empty_nickname = "First name: foo\nNickname:"
        x = parse_yaml(empty_nickname)
        self.assertListEqual(x.nicknames, [])

    def test_empty_role_in_yaml_input(self):
        empty_role = "First name: foo\nRole:"
        x = parse_yaml(empty_role)
        self.assertListEqual(x.roles, [])

    def test_empty_title_in_yaml_input(self):
        empty_title = "First name: foo\nTitle:"
        x = parse_yaml(empty_title)
        self.assertListEqual(x.titles, [])

    def test_empty_categories_in_yaml_input(self):
        empty_categories = "First name: foo\nCategories:"
        x = parse_yaml(empty_categories)
        self.assertListEqual(x.categories, [])

    def test_empty_webpage_in_yaml_input(self):
        empty_webpage = "First name: foo\nWebpage:"
        x = parse_yaml(empty_webpage)
        self.assertListEqual(x.webpages, [])

    def test_empty_note_in_yaml_input(self):
        empty_note = "First name: foo\nNote:"
        x = parse_yaml(empty_note)
        self.assertListEqual(x.notes, [])


class yaml_ablabel(unittest.TestCase):

    def test_ablabelled_url_in_yaml_input(self):
        ablabel_url = "First name: foo\nWebpage:\n - http://example.com\n" \
                      " - github: https://github.com/scheibler/khard"
        x = parse_yaml(ablabel_url)
        self.assertListEqual(x.webpages, [
            'github: https://github.com/scheibler/khard', 'http://example.com'])


class UpdateVcardWithYamlUserInput(unittest.TestCase):

    _date = datetime.datetime(2000, 1, 1)

    def test_update_org_simple(self):
        card = create_test_card()
        data = {'Organisation': 'Foo'}
        data = to_yaml(data)
        card.update(data)
        self.assertListEqual(card.organisations, [['Foo']])

    def test_update_org_multi(self):
        card = create_test_card()
        orgs = ['foo', 'bar', 'baz']
        data = {'Organisation': orgs}
        data = to_yaml(data)
        card.update(data)
        self.assertListEqual(card.organisations, sorted([[x] for x in orgs]))

    def test_update_org_complex(self):
        card = create_test_card()
        org = ['org.', 'dep.', 'office']
        data = {'Organisation': [org]}
        data = to_yaml(data)
        card.update(data)
        self.assertListEqual(card.organisations, [org])

    def test_update_categories_simple(self):
        card = create_test_card()
        data = {'Categories': 'foo'}
        data = to_yaml(data)
        card.update(data)
        self.assertListEqual(card.categories, ['foo'])

    def test_update_categories_multi(self):
        card = create_test_card()
        cat = ['foo', 'bar', 'baz']
        data = {'Categories': cat}
        data = to_yaml(data)
        card.update(data)
        self.assertListEqual(card.categories, cat)

    def test_update_bday_date(self):
        card = create_test_card()
        data = {'Birthday': '2000-01-01'}
        data = to_yaml(data)
        card.update(data)
        self.assertEqual(card.birthday, self._date)

    def test_update_anniverary(self):
        card = create_test_card()
        data = {'Anniversary': '2000-01-01'}
        data = to_yaml(data)
        card.update(data)
        self.assertEqual(card.anniversary, self._date)

    def test_update_name_simple(self):
        card = create_test_card()
        data = {'First name': 'first', 'Last name': 'last'}
        data = to_yaml(data)
        card.update(data)
        self.assertEqual(card.get_first_name_last_name(), 'first last')

    def test_update_fn(self):
        card = create_test_card()
        fn = 'me myself and i'
        data = {'Formatted name': fn}
        data = to_yaml(data)
        card.update(data)
        self.assertEqual(card.formatted_name, fn)
