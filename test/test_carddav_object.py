"""Tests for the carddav module."""

import datetime
import unittest

import vobject

from khard import carddav_object


def _create_test_vcard(**kwargs):
    """Create a simple vcard for tests."""
    vcard = vobject.vCard()
    if 'fn' not in kwargs:
        kwargs['fn'] = 'Test vCard'
    if 'version' not in kwargs:
        kwargs['version'] = '3.0'
    for key, value in kwargs.items():
        vcard.add(key.upper()).value = value
    return vcard


class VcardWrapperInit(unittest.TestCase):

    def test_stores_vcard_object_unmodified(self):
        vcard = _create_test_vcard()
        expected = vcard.serialize()
        wrapper = carddav_object.VCardWrapper(vcard)
        # assert that it is the same object
        self.assertIs(wrapper.vcard, vcard)
        # assert that it (the serialization) was not changed
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_warns_about_unsupported_version(self):
        vcard = _create_test_vcard(version="something unsupported")
        with self.assertLogs(level="WARNING"):
            carddav_object.VCardWrapper(vcard)

    def test_warns_about_missing_version_and_sets_it(self):
        vcard = _create_test_vcard()
        vcard.remove(vcard.version)
        with self.assertLogs(level="WARNING"):
            wrapper = carddav_object.VCardWrapper(vcard)
        self.assertEqual(wrapper.version, "3.0")


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
        with self.assertLogs(level='WARNING'):
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
        with self.assertLogs(level='WARNING'):
            wrapper.birthday = 'some time yesterday'
        wrapper.vcard.validate()
        self.assertIsNone(wrapper.anniversary)


class NameAttributes(unittest.TestCase):

    def test_fn_can_be_set_with_a_string(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.formatted_name = 'foo bar'
        self.assertEqual(vcard.fn.value, 'foo bar')

    def test_only_one_fn_will_be_stored(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.formatted_name = 'foo bar'
        self.assertEqual(len(vcard.contents['fn']), 1)

    def test_fn_is_returned_as_string(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        self.assertIsInstance(wrapper.formatted_name, str)

    def test_fn_is_used_as_string_representation(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        self.assertEqual(str(wrapper), wrapper.formatted_name)

    def test_name_can_be_set_with_empty_strings(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name('', '', '', '', '')
        self.assertEqual(vcard.serialize(),
                         'BEGIN:VCARD\r\n'
                         'VERSION:3.0\r\n'
                         'FN:Test vCard\r\n'
                         'N:;;;;\r\n'
                         'END:VCARD\r\n')

    def test_name_can_be_set_with_empty_lists(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name([], [], [], [], [])
        self.assertEqual(vcard.serialize(),
                         'BEGIN:VCARD\r\n'
                         'VERSION:3.0\r\n'
                         'FN:Test vCard\r\n'
                         'N:;;;;\r\n'
                         'END:VCARD\r\n')

    def test_name_can_be_set_with_lists_of_empty_strings(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name(['', ''], ['', ''], ['', ''], ['', ''], ['', ''])
        self.assertEqual(vcard.serialize(),
                         'BEGIN:VCARD\r\n'
                         'VERSION:3.0\r\n'
                         'FN:Test vCard\r\n'
                         'N:;;;;\r\n'
                         'END:VCARD\r\n')

    def test_get_first_name_last_name_retunrs_fn_if_no_name_present(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        self.assertEqual(wrapper.get_first_name_last_name(), 'Test vCard')

    def test_get_first_name_last_name_with_simple_name(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name('', 'given', '', 'family', '')
        self.assertEqual(wrapper.get_first_name_last_name(), "given family")

    def test_get_first_name_last_name_with_all_name_fields(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name('prefix', 'given', 'additional', 'family', 'suffix')
        self.assertEqual(wrapper.get_first_name_last_name(),
                         'given additional family')

    def test_get_first_name_last_name_with_complex_name(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name(['prefix1', 'prefix2'], ['given1', 'given2'],
                          ['additional1', 'additional2'],
                          ['family1', 'family2'], ['suffix1', 'suffix2'])
        self.assertEqual(wrapper.get_first_name_last_name(), 'given1 given2 '
                         'additional1 additional2 family1 family2')

    def test_get_last_name_first_name_retunrs_fn_if_no_name_present(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        self.assertEqual(wrapper.get_last_name_first_name(), 'Test vCard')

    def test_get_last_name_first_name_with_simple_name(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name('', 'given', '', 'family', '')
        self.assertEqual(wrapper.get_last_name_first_name(), "family, given")

    def test_get_last_name_first_name_with_all_name_fields(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name('prefix', 'given', 'additional', 'family', 'suffix')
        self.assertEqual(wrapper.get_last_name_first_name(),
                         'family, given additional')

    def test_get_last_name_first_name_with_complex_name(self):
        vcard = _create_test_vcard()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper._add_name(['prefix1', 'prefix2'], ['given1', 'given2'],
                          ['additional1', 'additional2'],
                          ['family1', 'family2'], ['suffix1', 'suffix2'])
        self.assertEqual(wrapper.get_last_name_first_name(), 'family1 family2,'
                         ' given1 given2 additional1 additional2')
