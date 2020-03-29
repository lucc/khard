"""Formatting and sorting of contacts"""


class Formatter:

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
