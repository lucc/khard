"""Names and aliases for the subcommands on the command line"""

from typing import Dict, Generator, Iterable, List, Optional


class Actions:

    """A class to manage the names and aliases of the command line
    subcommands."""

    action_map: Dict[str, List[str]] = {
        "add-email":    [],
        "addressbooks": ["abooks"],
        "birthdays":    ["bdays"],
        "copy":         ["cp"],
        "email":        [],
        "filename":     ["file"],
        "list":         ["ls"],
        "merge":        [],
        "edit":         ["modify", "ed"],
        "move":         ["mv"],
        "new":          ["add"],
        "phone":        [],
        "postaddress":  ["post", "postaddr"],
        "remove":       ["delete", "del", "rm"],
        "show":         ["details"],
        "template":     [],
    }

    @classmethod
    def get_action(cls, alias: str) -> Optional[str]:
        """Find the name of the action for the supplied alias.  If no action is
        associated with the given alias, None is returned.

        :param alias: the alias to look up
        :returns: the name of the corresponding action or None

        """
        for action, alias_list in cls.action_map.items():
            if alias in alias_list:
                return action
        return None

    @classmethod
    def get_aliases(cls, action: str) -> List[str]:
        """Find all aliases for the given action.  If there is no such action,
        None is returned.

        :param action: the action name to look up
        :returns: the list of aliases corresponding to the action or None

        """
        return cls.action_map[action]

    @classmethod
    def get_actions(cls) -> Iterable[str]:
        """Find the names of all defined actions.

        :returns: all action names
        """
        return cls.action_map.keys()

    @classmethod
    def get_all(cls) -> Generator[str, None, None]:
        """Find the names of all defined actions and their aliases.

        :returns: the names of all actions and aliases
        """
        for key, value in cls.action_map.items():
            yield key
            yield from value
