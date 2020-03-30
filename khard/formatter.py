"""Formatting and sorting of contacts"""

from typing import List

from .carddav_object import CarddavObject


class Formatter:

    """A formtter for CarddavObject.

    It recieves some settings on initialisation which influence the formatting
    of the contact.
    """

    def __init__(self, display: str, preferred_email: List[str],
                 preferred_phone: List[str], show_nicknames: bool) -> None:
        self._display = display
        self._preferred_email = preferred_email
        self._preferred_phone = preferred_phone
        self._show_nicknames = show_nicknames

    @staticmethod
    def format_labeled_field(field, preferred):
        """Format a labeled field from a vcard for display, the first entry
        under the preferred label will be returned

        :param dict(str:list(str)) field: the labeled field
        :param list(str) preferred: the order of preferred labels
        :returns: the formatted field entry
        :rtype: str
        """
        # filter out preferred type if set in config file
        keys = []
        for pref in preferred:
            for key in field:
                if pref.lower() in key.lower():
                    keys.append(key)
            if keys:
                break
        if not keys:
            keys = [k for k in field if "pref" in k.lower()] or field.keys()
        # get first key in alphabetical order
        first_key = sorted(keys, key=lambda k: k.lower())[0]
        return "{}: {}".format(first_key, sorted(field.get(first_key))[0])

    def get_special_field(self, vcard: CarddavObject, field: str) -> str:
        """Returns certain fields with specific formatting options
            (for support of some list command options)."""
        if field == 'name':
            if self._display == "first_name":
                name = vcard.get_first_name_last_name()
            elif self._display == "formatted_name":
                name = vcard.formatted_name
            else:
                name = vcard.get_last_name_first_name()
            if vcard.nicknames and self._show_nicknames:
                return "{} (Nickname: {})".format(name, vcard.nicknames[0])
            return name
        elif field == 'phone':
            if vcard.phone_numbers:
                return self.format_labeled_field(vcard.phone_numbers,
                                                 self._preferred_phone)
        elif field == 'email':
            if vcard.emails:
                return self.format_labeled_field(vcard.emails,
                                                 self._preferred_email)
        return ""
