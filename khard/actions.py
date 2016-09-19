# -*- coding: utf-8 -*-


class Actions:

    action_map = {
        "add-email":    [],
        "addressbooks": ["abooks"],
        "birthdays":    ["bdays"],
        "copy":         ["cp"],
        "details":      ["show"],
        "email":        [],
        "export":       [],
        "list":         ["ls"],
        "merge":        [],
        "modify":       ["edit", "ed"],
        "move":         ["mv"],
        "new":          ["add"],
        "phone":        [],
        "remove":       ["delete", "del", "rm"],
        "source":       ["src"]
    }

    @classmethod
    def get_action_for_alias(cls, alias):
        """Find the name of the action for the supplied alias.  If no action s
        asociated with the given alias, None is returned.

        :param alias: the alias to look up
        :type alias: str
        :rturns: the name of the corresponding action or None
        :rtype: str or NoneType

        """
        for action, alias_list in cls.action_map.items():
            if alias in alias_list:
                return action
        return None

    @classmethod
    def get_alias_list_for_action(cls, action):
        """Find all aliases for the given action.  If there is no such action,
        None is returned.

        :param action: the action name to look up
        :type action: str
        :returns: the list of aliases or None
        :rtype: list(str) or NoneType

        """
        return cls.action_map.get(action)

    @classmethod
    def get_list_of_all_actions(cls):
        """Find the names of all defined actions.

        :returns: all action names
        :rtype: iterable(str)
        """
        return cls.action_map.keys()

    @classmethod
    def get_all_actions_and_aliases(cls):
        """Find the names of all defined actions and their aliases.

        :returns: the names of all actions and aliases
        :rtype: list(str)

        """
        all = []
        for key, value in cls.action_map.items():
            all.append(key)
            all.extend(value)
        return all
