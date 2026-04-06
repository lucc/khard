"""Tests for the csv submodule"""

import os
import unittest
from unittest import mock

from khard.contacts import Contact
from khard.csv import Parser


class TestCSVParser(unittest.TestCase):
    """Tests the csv module and khard.contacts.Contact.from_dict()."""
    def test_yaml_and_csv_produce_equivalent_contacts(self):
        """Test that YAML and CSV with same data produce equivalent Contacts.

        Make one of the CSV files "jumbled" to verify that column order
        doesn't matter to getting the right result.
        """
        contacts_from_yaml = []
        for basename in ["batman.yaml", "superman.yaml", "lois_lane.yaml"]:
            with open(os.path.join("test/fixture/csv", basename)) as f:
                contact = Contact.from_yaml(
                        address_book=mock.Mock(path="foo-path"),
                        yaml=f.read(),
                        supported_private_objects=[],
                        version="3.0",
                        localize_dates=False
                        )
                contacts_from_yaml.append(contact)

        contacts_from_neat_csv = []
        with open("test/fixture/csv/neat.csv") as f:
            for contact_data in Parser(f.read(), ","):
                contact = Contact.from_dict(
                        address_book=mock.Mock(path="foo-path"),
                        data=contact_data,
                        supported_private_objects=[],
                        version="3.0",
                        localize_dates=False
                        )
                contacts_from_neat_csv.append(contact)

        contacts_from_jumbled_csv = []
        with open("test/fixture/csv/jumbled.csv") as f:
            for contact_data in Parser(f.read(), ","):
                contact = Contact.from_dict(
                        address_book=mock.Mock(path="foo-path"),
                        data=contact_data,
                        supported_private_objects=[],
                        version="3.0",
                        localize_dates=False
                        )
                contacts_from_jumbled_csv.append(contact)

        self.assertEqual(len(contacts_from_yaml),
                         len(contacts_from_neat_csv))
        self.assertEqual(len(contacts_from_neat_csv),
                         len(contacts_from_jumbled_csv))
        for i in range(0, len(contacts_from_yaml)):
            with self.subTest(row=i+1):
                self.assertEqual(contacts_from_yaml[i],
                                 contacts_from_neat_csv[i])
                self.assertEqual(contacts_from_neat_csv[i],
                                 contacts_from_jumbled_csv[i])
