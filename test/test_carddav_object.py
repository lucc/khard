"""Tests for the CarddavObject class from the carddav module."""
# pylint: disable=missing-docstring

import base64
import datetime
import unittest
from unittest import mock

from khard.carddav_object import CarddavObject, multi_property_key


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


class AltIds(unittest.TestCase):

    def test_altids_are_read(self):
        card = CarddavObject.from_file(None, 'test/fixture/vcards/altid.vcf')
        expected = 'one representation'
        self.assertEqual(expected, card.get_first_name_last_name())


class Photo(unittest.TestCase):

    """Tests related to the PHOTO property of vCards"""

    PNG_HEADER = b'\x89PNG\r\n\x1a\n'

    def test_parsing_base64_ecoded_photo_vcard_v3(self):
        c = CarddavObject.from_file(None, 'test/fixture/vcards/photov3.vcf')
        self.assertEqual(c.vcard.photo.value[:8], self.PNG_HEADER)

    def test_parsing_base64_ecoded_photo_vcard_v4(self):
        c = CarddavObject.from_file(None, 'test/fixture/vcards/photov4.vcf')
        uri_stuff, data = c.vcard.photo.value.split(',')
        self.assertEqual(uri_stuff, 'data:image/png;base64')
        data = base64.decodebytes(data.encode())
        self.assertEqual(data[:8], self.PNG_HEADER)


class MultiPropertyKey(unittest.TestCase):
    """Test for the multi_property_key helper function"""

    def test_strings_are_in_the_first_sort_group(self) -> None:
        group, _key = multi_property_key("some string")
        self.assertEqual(group, 0)

    def test_dicts_are_in_the_second_sort_group(self) -> None:
        group, _key = multi_property_key({"some": "dict"})
        self.assertEqual(group, 1)

    def test_strings_are_their_own_keys(self) -> None:
        _group, key = multi_property_key("some string")
        self.assertEqual(key, "some string")

    def test_dicts_are_keyed_by_the_first_key(self) -> None:
        _group, key = multi_property_key({"some": "dict", "more": "stuff"})
        self.assertEqual(key, "some")

    def test_all_strings_are_sorted_before_dicts(self) -> None:
        my_list = ["a", {"c": "d"}, "e", {"f": "g"}]
        my_list.sort(key=multi_property_key)
        self.assertEqual(my_list, ["a", "e", {"c": "d"}, {"f": "g"}])
