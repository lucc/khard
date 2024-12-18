"""Tests for the action class"""
# pylint: disable=missing-docstring

import unittest

from khard import actions

action = 'list'
alias = 'ls'
unknown = 'this is not an action or an alias'


class Action(unittest.TestCase):

    def test_get_action_resolves_aliases(self):
        self.assertEqual(action, actions.Actions.get_action(alias))

    def test_get_action_returns_none_for_actions(self):
        self.assertIsNone(actions.Actions.get_action(action))

    def test_get_action_returns_none_for_unknown(self):
        self.assertIsNone(actions.Actions.get_action(unknown))

    def test_get_aliases_reverse_resolves_aliases(self):
        self.assertEqual([alias], actions.Actions.get_aliases(action))

    def test_get_aliases_throws_keyerror_for_aliases(self):
        with self.assertRaises(KeyError):
            actions.Actions.get_aliases(alias)

    def test_get_aliases_throws_keyerror_for_unknown(self):
        with self.assertRaises(KeyError):
            actions.Actions.get_aliases(unknown)

    def test_get_actions_returns_actions(self):
        self.assertIn(action, actions.Actions.get_actions())

    def test_get_actions_does_not_return_aliases(self):
        self.assertNotIn(alias, actions.Actions.get_actions())

    def test_get_all_returns_actions(self):
        self.assertIn(action, actions.Actions.get_all())

    def test_get_all_returns_aliases(self):
        self.assertIn(alias, actions.Actions.get_all())
