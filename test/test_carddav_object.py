"""Tests for the carddav module."""

import unittest

import vobject

from khard import carddav_object


class DeleteVcardObject(unittest.TestCase):

    def test_deletes_fields_given_in_upper_case(self):
        vcard = vobject.vCard()
        vcard.add('FN').value = "Test vCard"
        expected = vcard.serialize()
        vcard.add('FOO').value = 'bar'
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('FOO')
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_deletes_all_field_occurences(self):
        vcard = vobject.vCard()
        vcard.add('FN').value = "Test vCard"
        expected = vcard.serialize()
        vcard.add('FOO').value = 'bar'
        vcard.add('FOO').value = 'baz'
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('FOO')
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_deletes_grouped_ablabel_fields(self):
        vcard = vobject.vCard()
        vcard.add('FN').value = "Test vCard"
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
        vcard = vobject.vCard()
        vcard.add('FN').value = "Test vCard"
        vcard.add('FOO').value = 'bar'
        expected = vcard.serialize()
        vcard.add('BAR').value = 'baz'
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('BAR')
        self.assertEqual(wrapper.vcard.serialize(), expected)

    def test_does_not_fail_on_non_existing_field_name(self):
        vcard = vobject.vCard()
        vcard.add('FN').value = "Test vCard"
        vcard.add('FOO').value = 'bar'
        expected = vcard.serialize()
        wrapper = carddav_object.VCardWrapper(vcard)
        wrapper.delete_vcard_object('BAR')
        self.assertEqual(wrapper.vcard.serialize(), expected)
