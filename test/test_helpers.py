"""Tests for the helpers module."""

import unittest

from khard import helpers


class CompareUids(unittest.TestCase):

    def test_different_strings(self):
        uid1 = 'abc'
        uid2 = 'xyz'
        expected = 0
        actual = helpers.compare_uids(uid1, uid2)
        self.assertEqual(actual, expected)

    def test_two_simple_strings(self):
        uid1 = 'abcdef'
        uid2 = 'abcxyz'
        expected = 3
        actual = helpers.compare_uids(uid1, uid2)
        self.assertEqual(actual, expected)

    def test_no_error_on_equal_strings(self):
        uid = 'abcdefghij'
        expected = len(uid)
        actual = helpers.compare_uids(uid, uid)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
