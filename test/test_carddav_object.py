"""Tests for the carddav module."""

import datetime
import unittest

import vobject

from khard import carddav_object


def _create_test_vcard(**kwargs):
    """Create a simple vcard for tests."""
    vcard = vobject.vCard()
    vcard.add('FN').value = "Test vCard"
    for key, value in kwargs.items():
        vcard.add(key.upper()).value = value
    return vcard


class DeleteVcardObject(unittest.TestCase):

    def test_deletes_fields_given_in_upper_case(self):
        vcard = _create_test_vcard()
        expected = vcard.serialize()
        vcard.add('FOO').value = 'bar'
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('FOO')
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_deletes_all_field_occurences(self):
        vcard = _create_test_vcard()
        expected = vcard.serialize()
        vcard.add('FOO').value = 'bar'
        vcard.add('FOO').value = 'baz'
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('FOO')
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_deletes_grouped_ablabel_fields(self):
        vcard = _create_test_vcard()
        expected = vcard.serialize()
        foo = vcard.add('FOO')
        foo.value = 'bar'
        foo.group = 'group1'
        label = vcard.add('X-ABLABEL')
        label.value = 'test label'
        label.group = foo.group
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('FOO')
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_keeps_other_fields(self):
        vcard = _create_test_vcard(foo='bar')
        expected = vcard.serialize()
        vcard.add('BAR').value = 'baz'
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('BAR')
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_does_not_fail_on_non_existing_field_name(self):
        vcard = _create_test_vcard(foo='bar')
        expected = vcard.serialize()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('BAR')
        self.assertEqual(wrapper.vcard.serialize(), expected)


class BirthdayLikeAttributes(unittest.TestCase):

    def test_birthday_supports_setting_date_objects(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        date = datetime.datetime(2018, 2, 1)
        wrapper.birthday = date
        wrapper.vcard.validate()
        self.assertEqual(wrapper.birthday, date)

    def test_birthday_supports_setting_datetime_objects(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        date = datetime.datetime(2018, 2, 1, 19, 29, 31)
        wrapper.birthday = date
        wrapper.vcard.validate()
        self.assertEqual(wrapper.birthday, date)

    def test_birthday_supports_setting_text_values_for_v4(self):
        vcard = _create_test_vcard(version="4.0")
        wrapper = carddav_object.VCardWrapper(vcard)
        date = 'some time yesterday'
        wrapper.birthday = date
        wrapper.vcard.validate()
        self.assertEqual(wrapper.birthday, date)

    def test_birthday_does_not_support_setting_text_values_for_v3(self):
        vcard = _create_test_vcard(version="3.0")
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.birthday = 'some time yesterday'
        wrapper.vcard.validate()
        self.assertIsNone(wrapper.birthday)

    def test_anniversary_supports_setting_date_objects(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        date = datetime.datetime(2018, 2, 1)
        wrapper.anniversary = date
        wrapper.vcard.validate()
        self.assertEqual(wrapper.anniversary, date)

    def test_anniversary_supports_setting_datetime_objects(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        date = datetime.datetime(2018, 2, 1, 19, 29, 31)
        wrapper.anniversary = date
        wrapper.vcard.validate()
        self.assertEqual(wrapper.anniversary, date)

    def test_anniversary_supports_setting_text_values_for_v4(self):
        vcard = _create_test_vcard(version="4.0")
        wrapper = carddav_object.VCardWrapper(vcard)
        date = 'some time yesterday'
        wrapper.anniversary = date
        wrapper.vcard.validate()
        self.assertEqual(wrapper.anniversary, date)

    def test_anniversary_does_not_support_setting_text_values_for_v3(self):
        vcard = _create_test_vcard(version="3.0")
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.anniversary = 'some time yesterday'
        wrapper.vcard.validate()
        self.assertIsNone(wrapper.anniversary)
