"""Tests for the Contact class from the contacts module."""

# pylint: disable=missing-docstring

import base64
import datetime
import errno
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from khard.contacts import Contact, atomic_write, multi_property_key


class ContactFormatDateObject(unittest.TestCase):
    def test_format_date_object_will_not_touch_strings(self):
        expected = "untouched string"
        actual = Contact._format_date_object(expected, False)
        self.assertEqual(actual, expected)

    def test_format_date_object_with_simple_date_object(self):
        d = datetime.datetime(2018, 2, 13)
        actual = Contact._format_date_object(d, False)
        self.assertEqual(actual, "2018-02-13")

    def test_format_date_object_with_simple_datetime_object(self):
        d = datetime.datetime(2018, 2, 13, 0, 38, 31)
        with mock.patch("time.timezone", -7200):
            actual = Contact._format_date_object(d, False)
        self.assertEqual(actual, "2018-02-13T00:38:31+02:00")

    def test_format_date_object_with_date_1900(self):
        d = datetime.datetime(1900, 2, 13)
        actual = Contact._format_date_object(d, False)
        self.assertEqual(actual, "--02-13")


class AltIds(unittest.TestCase):
    def test_altids_are_read(self):
        card = Contact.from_file(None, "test/fixture/vcards/altid.vcf")
        expected = "one representation"
        self.assertEqual(expected, card.get_first_name_last_name())


class Photo(unittest.TestCase):
    """Tests related to the PHOTO property of vCards"""

    PNG_HEADER = b"\x89PNG\r\n\x1a\n"

    def test_parsing_base64_ecoded_photo_vcard_v3(self):
        c = Contact.from_file(None, "test/fixture/vcards/photov3.vcf")
        self.assertEqual(c.vcard.photo.value[:8], self.PNG_HEADER)

    def test_parsing_base64_ecoded_photo_vcard_v4(self):
        c = Contact.from_file(None, "test/fixture/vcards/photov4.vcf")
        uri_stuff, data = c.vcard.photo.value.split(",")
        self.assertEqual(uri_stuff, "data:image/png;base64")
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
        my_list.sort(key=multi_property_key)  # type: ignore[arg-type]
        self.assertEqual(my_list, ["a", "e", {"c": "d"}, {"f": "g"}])


class AtomicWrite(unittest.TestCase):
    """Tests for the atomic_write functionself.

    These tests have been migrated from the original atomicwrites repository.
    """

    def setUp(self) -> None:
        self.t = tempfile.TemporaryDirectory()
        self.tmpdir = pathlib.Path(self.t.name)
        return super().setUp()

    def tearDown(self) -> None:
        self.t.cleanup()
        return super().tearDown()

    def assertFileContents(self, file: pathlib.Path, contents: str) -> None:
        """Assert the file contents of the given file"""
        with file.open() as f:
            return self.assertEqual(f.read(), contents)

    @staticmethod
    def write(path: pathlib.Path, contents: str) -> None:
        """Write a string to a file"""
        with path.open("w") as f:
            f.write(contents)

    def test_atomic_write(self) -> None:
        fname = self.tmpdir / 'ha'
        for i in range(2):
            with atomic_write(str(fname), overwrite=True) as f:
                f.write('hoho')

        with self.assertRaises(OSError) as excinfo:
            with atomic_write(str(fname), overwrite=False) as f:
                f.write('haha')

        self.assertEqual(excinfo.exception.errno, errno.EEXIST)

        self.assertFileContents(fname, 'hoho')
        self.assertEqual(len(list(self.tmpdir.iterdir())), 1)


    def test_teardown(self) -> None:
        fname = self.tmpdir / 'ha'
        with self.assertRaises(AssertionError):
            with atomic_write(str(fname), overwrite=True):
                self.fail("This code should not be reached")

        self.assertFalse(any(self.tmpdir.iterdir()))


    def test_replace_simultaneously_created_file(self) -> None:
        fname = self.tmpdir / 'ha'
        with atomic_write(str(fname), overwrite=True) as f:
            f.write('hoho')
            self.write(fname, 'harhar')
            self.assertFileContents(fname, 'harhar')
        self.assertFileContents(fname, 'hoho')
        self.assertEqual(len(list(self.tmpdir.iterdir())), 1)


    def test_dont_remove_simultaneously_created_file(self) -> None:
        fname = self.tmpdir / 'ha'
        with self.assertRaises(OSError) as excinfo:
            with atomic_write(str(fname), overwrite=False) as f:
                f.write('hoho')
                self.write(fname, 'harhar')
                self.assertFileContents(fname, 'harhar')

        self.assertEqual(excinfo.exception.errno, errno.EEXIST)
        self.assertFileContents(fname, 'harhar')
        self.assertEqual(len(list(self.tmpdir.iterdir())), 1)


    def test_open_reraise(self) -> None:
        """Verify that nested exceptions during rollback do not overwrite the
        initial exception that triggered a rollback."""
        fname = self.tmpdir / 'ha'
        with self.assertRaises(AssertionError):
            with atomic_write(str(fname), overwrite=False):
                # Mess with internals; find and remove the temp file used by
                # atomic_write internally. We're testing that the initial
                # AssertionError triggered below is propagated up the stack,
                # not the second exception triggered during commit.
                tmp = next(self.tmpdir.iterdir())
                tmp.unlink()
                # Now trigger our own exception.
                self.fail("Intentional failure for testing purposes")


    def test_atomic_write_in_cwd(self) -> None:
        orig_curdir = os.getcwd()
        try:
            os.chdir(str(self.tmpdir))
            fname = 'ha'
            for i in range(2):
                with atomic_write(fname, overwrite=True) as f:
                    f.write('hoho')

            with self.assertRaises(OSError) as excinfo:
                with atomic_write(fname, overwrite=False) as f:
                    f.write('haha')

            self.assertEqual(excinfo.exception.errno, errno.EEXIST)

            self.assertFileContents(pathlib.Path(fname), 'hoho')
            self.assertEqual(len(list(self.tmpdir.iterdir())), 1)
        finally:
            os.chdir(orig_curdir)
