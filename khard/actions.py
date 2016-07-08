# -*- coding: utf-8 -*-


class Actions:

    action_map = {
            "addressbooks": ["abooks"],
            "add-email":    [],
            "birthdays":    ["bdays"],
            "copy":         ["cp"],
            "details":      [],
            "email":        [],
            "export":       [],
            "list":         ["ls"],
            "merge":        [],
            "modify":       ["edit"],
            "move":         ["mv"],
            "new":          ["add"],
            "phone":        [],
            "remove":       ["delete", "del", "rm"],
            "source":       []
    }

    @classmethod
    def get_action_for_alias(cls, alias):
        for action, alias_list in cls.action_map.items():
            if alias in alias_list:
                return action
        return None

    @classmethod
    def get_alias_list_for_action(cls, action):
        return cls.action_map.get(action)

    @classmethod
    def get_list_of_all_actions(cls):
        return list(cls.action_map.keys())
