# -*- coding: utf-8 -*-

import os


class AddressBook:
    def __init__(self, name, path):
        self.loaded = False
        self.contact_list = []
        self.name = name
        self.path = os.path.expanduser(path)
        if not os.path.isdir(self.path):
            raise IOError("[Errno 2] The path %s to the address book %s "
                          "does not exist." % (self.path, self.name))

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, AddressBook) and self.name == other.get_name()

    def __ne__(self, other):
        return not self == other

    def get_name(self):
        return self.name

    def get_path(self):
        return self.path

    def get_contact_list(self):
        return self.contact_list

    def add_contact(self, contact):
        self.contact_list.append(contact)
