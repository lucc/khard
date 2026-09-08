from collections.abc import Iterator
import csv
import re
from typing import Any


class Parser:
    """An iterator over rows in a CSV file that returns contact data."""

    def __init__(self, input_from_stdin_or_file: str, delimiter: str) -> None:
        """Parse first row to determine structure of contact data.

        :param input_from_stdin_or_file: A string from stdin, from an input
            file specified with "-i" or "--input-file", or otherwise from a
            temporary file created by khard and edited by the user.
        :param delimiter: The field delimiter ("," by default).
        """
        self.reader = csv.reader(input_from_stdin_or_file.split("\n"),
                                 delimiter=delimiter)
        first_row = next(self.reader)
        self.template, self.columns = self._parse_headers(first_row)

    def __iter__(self) -> Iterator[dict]:
        return self

    def __next__(self) -> dict:
        """Return the next parsed row from the CSV reader.

        Iteration stops when "reader" raises "StopIteration", or when row is
        blank.

        :returns: A dict with the same structure as the dict returned by
            khard.YAMLEditable._parse_yaml(). Can be passed to
            khard.YAMLEditable.update().
        """
        try:
            row = next(self.reader)
        except StopIteration:
            raise
        else:
            if not row:
                raise StopIteration
            return self.parse(row)

    def parse(self, row: list[str]) -> dict:
        """Get data from a CSV row that can be used to make a new Contact.

        :param row: A list of strings, one for each column.
        :returns: A dict with the same structure as the dict returned by
            khard.YAMLEditable._parse_yaml(). Can be passed to
            khard.YAMLEditable.update().
        """
        self._get_data(row)
        return self._process_data()

    @staticmethod
    def _parse_headers(first_row: list[str]) -> tuple[dict, list]:
        """Determine the data structure of each contact by parsing first row.

        Valid headers have the form "<key>[ <idx>[ - <subkey>]]".

        If the column header has the form "<key>", each value in the column is
        a string indexed by "<key>". If the column header has the form "<key>
        <idx>", each value in the column is a string, at index "<idx - 1>", in
        a list indexed by "<key>". If the column header has the form "<key>
        <idx> - <subkey>", each value in the column is a value in a dict
        indexed by "<subkey>". This dict is in a list indexed by "key", at
        index "<idx - 1>".

        For example, the following CSV would have the following raw data
        structure:

        First name,Last name,Organisation 1,Organisation 2,Email 1 -
        type,Email 1 - value,Email 2 - type

        Bruce,Wayne,Justice League,Wayne
        Enterprises,work,thebat@justice.org,work,bruce@wayne.com

        {'First name': 'Bruce',
         'Last name': 'Wayne',
         'Organisation': {1: 'Justice League', 2: 'Wayne Enterprises'},
         'Email': {1: {'type': 'work'}, 2: {'value': 'thebat@justice.org'}}}

        Note that, rather than actual lists, we use dicts with numeric keys.
        This is to avoid making assumptions about how users will structure
        their CSV files. For example, if a user for some reason placed "Email
        2" before "Email 1", and we were storing email data in a list, that
        would lead to an IndexError. A dict, on the other hand, does not care
        if key "1" does not yet exist when mapping a value to key "2".

        :param first_row: First row of the CSV file, which must contain column
            headers.
        :returns: The "template" dict and the "columns" list. The structure of
            "template" is determined by the CSV column headers, and all of its
            keys are initialized. "columns" is a list of 2-tuples. The first
            item in each tuple is the data structure in which each value in
            that column belongs. The second item is the index in that data
            structure at which the value is located.
        """
        template: dict[str, Any] = {}
        columns: list[tuple[dict, Any]] = []

        headers = re.compile(r"^([a-zA-Z ]+)(?: (\d+))?(?: - ([a-zA-Z ]+))?$")
        for val in first_row:
            match = headers.search(val)
            if not match:
                raise ValueError(f"Column header \"{val}\" is invalid.")
            else:
                key, idx, subkey = match.groups()

            if idx:
                idx = int(idx) - 1
                template.setdefault(key, {})
                if subkey:
                    template[key].setdefault(idx, {})
                    template[key][idx].update({subkey: None})
                    columns.append(
                            (template[key][idx], subkey)
                            )
                else:
                    template[key].setdefault(idx, None)
                    columns.append(
                            (template[key], idx)
                            )
            else:
                template[key] = None
                columns.append(
                        (template, key)
                        )

        return template, columns

    def _get_data(self, row: list[str]) -> None:
        """Populate "self.template" with data using info in "self.columns".

        We have to fill in "self.template" in place, rather than a copy,
        because the data structures referenced in "self.columns" point to
        "self.template" itself. This approach is safe because every value in
        "self.template" is overwritten on every iteration.
        """
        for i in range(0, len(row)):
            data_structure, idx = self.columns[i]
            data_structure[idx] = row[i]

    def _process_data(self) -> dict:
        """Process raw data into a form that can be used to create Contacts.

        Turn dicts with numeric keys into actual lists, if the keys index
        strings. For example, the line `'Organisation': {1: 'Justice League',
        2: 'Wayne Enterprises'}` becomes `'Organisation': ['Justice League',
        'Wayne Enterprises']`.

        Turn dicts with numeric keys into dicts with string keys, if the keys
        index dicts. If any of the indexed dicts contains two keys, "type" and
        "value", the value indexed by "type" is a key in the new dict, and the
        value indexed by "value" is mapped to that key. For example, the line
        `'Email': {1: {'type': 'work', 'value': 'thebat@justice.org'}, 2:
        {'type': 'home', 'value': 'bruce@gmail.com}` becomes `'Email':
        {'work': 'thebat@justice.org', 'home': 'bruce@gmail.com'}`.

        If any of the indexed dicts contain the key "type" but not the key
        "value", "type" is a key in the new dict, and all other key-value
        pairs in the indexed dict are key-value pairs in a dict mapped to that
        key. For example, the line `'Address': {1: {'type': 'home', 'Street':
        '1007 Mountain Drive', 'City': 'Gotham City', 'Country': 'USA'}}`
        becomes `'Address': {'home': {'Street': '1007 Mountain Drive', 'City':
        'Gotham City', 'Country': 'USA'}}`.

        If any of the indexed dicts have the same value mapped to key "type",
        the value indexed by "type" indexes a list in the new dict. The list
        contains all of the values that could have been mapped to the key, if
        any of the dicts had been the only dict with a "type" of that value.
        For example, `'Email': {1: {'type': 'work', 'value':
        'thebat@justice.org'}, 2: {'type': 'work', 'value':
        'bruce@wayne.com'}` becomes `'Email': {'work': ['thebat@justice.org',
        'bruce@wayne.com']}`.

        :returns: A dict with the same structure as the dict returned by
            khard.YAMLEditable._parse_yaml(). Can be passed to
            khard.YAMLEditable.update().
        """
        contact_data = {}
        for key, val in self.template.items():
            if not isinstance(val, dict):
                contact_data[key] = val
            elif not isinstance(val[0], dict):
                contact_data[key] = [val[k] for k in sorted(val.keys())
                                     if val[k]]
            elif list(sorted(val[0].keys())) == ["type", "value"]:
                contact_data[key] = {}
                for d in val.values():
                    if not d["type"]:
                        continue
                    try:
                        contact_data[key][d["type"]].append(d["value"])
                    except KeyError:
                        contact_data[key][d["type"]] = [d["value"]]
            else:
                contact_data[key] = {}
                for d in val.values():
                    if not d["type"]:
                        continue
                    try:
                        contact_data[key][d["type"]].append(d)
                        del contact_data[key][d["type"]][-1]["type"]
                    except KeyError:
                        contact_data[key][d["type"]] = [d]
                        del contact_data[key][d["type"]][-1]["type"]
        return contact_data
