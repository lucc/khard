"""Tests for the CarddavObject class from the carddav module."""

import datetime
from io import StringIO
import unittest
from unittest import mock

from ruamel.yaml import YAML

from khard.carddav_object import CarddavObject


def create_test_card():
    # TODO Write a more test friendly constructor.
    abook = mock.Mock()
    abook.path = 'some/temp/path'
    with mock.patch('__main__.open', mock.mock_open()):
        return CarddavObject(abook, None)


def to_yaml(data):
    if 'First name' not in data:
        data['First name'] = 'Nobody'
    stream = StringIO()
    YAML().dump(data, stream)
    return stream.getvalue()


class CarddavObjectFormatDateObject(unittest.TestCase):

    def test_format_date_object_will_not_touch_strings(self):
        expected = 'untouched string'
        actual = CarddavObject._format_date_object(expected, False)
        self.assertEqual(actual, expected)

    def test_format_date_object_with_simple_date_object(self):
        d = datetime.datetime(2018, 2, 13)
        actual = CarddavObject._format_date_object(d, False)
        self.assertEqual(actual, '2018-02-13')

    def test_format_date_object_with_simple_datetime_object(self):
        d = datetime.datetime(2018, 2, 13, 0, 38, 31)
        with mock.patch('time.timezone', -7200):
            actual = CarddavObject._format_date_object(d, False)
        self.assertEqual(actual, '2018-02-13T00:38:31+02:00')

    def test_format_date_object_with_date_1900(self):
        d = datetime.datetime(1900, 2, 13)
        actual = CarddavObject._format_date_object(d, False)
        self.assertEqual(actual, '--02-13')


class UpdateVcardWithYamlUserInput(unittest.TestCase):

    def test_update_org_simple(self):
        card = create_test_card()
        data = {'Organisation': 'Foo'}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertListEqual(card.organisations, [['Foo']])

    def test_update_org_multi(self):
        card = create_test_card()
        orgs = ['foo', 'bar', 'baz']
        data = {'Organisation': orgs}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertListEqual(card.organisations, sorted([[x] for x in orgs]))

    def test_update_org_complex(self):
        card = create_test_card()
        org = ['org.', 'dep.', 'office']
        data = {'Organisation': [org]}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertListEqual(card.organisations, [org])

    def test_update_categories_simple(self):
        card = create_test_card()
        data = {'Categories': 'foo'}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertListEqual(card.categories, ['foo'])

    def test_update_categories_multi(self):
        card = create_test_card()
        cat = ['foo', 'bar', 'baz']
        data = {'Categories': cat}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertListEqual(card.categories, cat)

    def test_update_bday_date(self):
        card = create_test_card()
        data = {'Birthday': '2000-01-01'}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertEqual(card.birthday,
                         datetime.datetime.fromisoformat('2000-01-01'))

    def test_update_anniverary(self):
        card = create_test_card()
        data = {'Anniversary': '2000-01-01'}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertEqual(card.anniversary,
                         datetime.datetime.fromisoformat('2000-01-01'))

    def test_update_name_simple(self):
        card = create_test_card()
        data = {'First name': 'first', 'Last name': 'last'}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertEqual(card.get_first_name_last_name(), 'first last')

    def test_update_fn(self):
        card = create_test_card()
        fn = 'me myself and i'
        data = {'Formatted name': fn}
        data = to_yaml(data)
        card._process_user_input(data)
        self.assertEqual(card.formatted_name, fn)

