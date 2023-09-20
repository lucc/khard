"""Tests for the user interaction functions."""

import unittest
from unittest import mock

from khard.helpers import interactive

from .helpers import mock_stream


class Select(unittest.TestCase):

    def _test(self, include_none=None):
        input_list = ["a", "b", "c"]
        if include_none is None:
            return interactive.select(input_list)
        else:
            return interactive.select(input_list, include_none)

    def test_selection_index_is_1_based(self):
        with mock.patch("builtins.input", lambda _: "1"):
            actual = self._test()
        self.assertEqual(actual, "a")

    def test_typing_a_non_number_prints_a_message_and_repeats(self):
        with mock.patch("builtins.input", mock.Mock(side_effect=["foo", "2"])):
            with mock_stream() as stdout:
                actual = self._test()
        stdout = stdout.getvalue()
        self.assertEqual(stdout, "Please enter an index value between 1 and 3 "
                         "or q to quit.\n")
        self.assertEqual(actual, "b")

    def test_out_of_bounds_repeats(self):
        with mock.patch("builtins.input", mock.Mock(side_effect=["5", "2"])):
            with mock_stream() as stdout:
                actual = self._test()
        stdout = stdout.getvalue()
        self.assertEqual(stdout, "Please enter an index value between 1 and 3 "
                         "or q to quit.\n")
        self.assertEqual(actual, "b")

    def test_index_0_is_not_accepted(self):
        with mock.patch("builtins.input", mock.Mock(side_effect=["0", "2"])):
            with mock_stream() as stdout:
                actual = self._test()
        stdout = stdout.getvalue()
        self.assertEqual(stdout, "Please enter an index value between 1 and 3 "
                         "or q to quit.\n")
        self.assertEqual(actual, "b")

    def test_index_0_is_accepted_with_include_none(self):
        with mock.patch("builtins.input", lambda _: "0"):
            actual = self._test(True)
        self.assertIsNone(actual)

    def test_empty_input_cancels(self):
        with mock.patch("builtins.input", lambda _: ""):
            with mock_stream() as stdout:
                actual = self._test()
        stdout = stdout.getvalue()
        self.assertEqual(stdout, "Canceled\n")
        self.assertIsNone(actual)




class Confirm(unittest.TestCase):

    def test_y_is_true(self):
        with mock.patch("builtins.input", lambda x: "y"):
            self.assertTrue(interactive.confirm(""))

    def test_n_is_false(self):
        with mock.patch("builtins.input", lambda x: "n"):
            self.assertFalse(interactive.confirm(""))

    def test_Y_is_true(self):
        with mock.patch("builtins.input", lambda x: "Y"):
            self.assertTrue(interactive.confirm(""))

    def test_N_is_false(self):
        with mock.patch("builtins.input", lambda x: "N"):
            self.assertFalse(interactive.confirm(""))

    def test_full_word_yes_is_not_accepted(self):
        with mock.patch("builtins.input", mock.Mock(side_effect=["yes", "n"])):
            with mock_stream():
                self.assertFalse(interactive.confirm(""))

    def test_full_word_no_is_not_accepted(self):
        with mock.patch("builtins.input", mock.Mock(side_effect=["no", "y"])):
            with mock_stream():
                self.assertTrue(interactive.confirm(""))
