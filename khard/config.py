# -*- coding: utf-8 -*-

# singleton code comes from:
# http://code.activestate.com/recipes/52558/#as_content

import os, sys, glob, re, operator, vobject
import helpers
from configobj import ConfigObj
from distutils.spawn import find_executable
from address_book import AddressBook
from carddav_object import CarddavObject

class Config:
    """ A python singleton """

    class __impl:
        """ Implementation of the singleton interface """
        def __init__(self):
            self.config = None
            self.address_book_list = []
            self.uid_dict = {}

            # load config file
            xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or \
                    os.path.expanduser("~/.config")
            config_file = os.environ.get("KHARD_CONFIG") or \
                    os.path.join(xdg_config_home, "khard", "khard.conf")
            if os.path.exists(config_file) == False:
                print("Config file %s not available" % config_file)
                sys.exit(2)
            self.config = ConfigObj(config_file, interpolation=False)

            # general settings
            if self.config.has_key("general") == False:
                print("Error in config file\nMissing main section \"[general]\".")
                sys.exit(2)

            # editor
            self.config['general']['editor'] = self.config['general'].get("editor") \
                    or os.environ.get("EDITOR")
            if self.config['general']['editor'] is None:
                print("Error in config file\n" \
                        "Set path to your preferred text editor in khard's config file or the $EDITOR shell variable\n" \
                        "Example for khard.conf: editor = vim")
                sys.exit(2)
            self.config['general']['editor'] = find_executable(
                    os.path.expanduser(self.config['general']['editor']))
            if self.config['general']['editor'] is None:
                print("Error in config file\nInvalid editor path or executable not found.")
                sys.exit(2)

            # merge editor
            self.config['general']['merge_editor'] = self.config['general'].get("merge_editor") \
                    or os.environ.get("MERGE_EDITOR")
            if self.config['general']['merge_editor'] is None:
                print("Error in config file\n" \
                        "Set path to your preferred text merge editor in khard's config file or the $MERGE_EDITOR shell variable\n" \
                        "Example for khard.conf: merge_editor = vimdiff")
                sys.exit(2)
            self.config['general']['merge_editor'] = find_executable(
                    os.path.expanduser(self.config['general']['merge_editor']))
            if self.config['general']['merge_editor'] is None:
                print("Error in config file\nInvalid merge editor path or executable not found.")
                sys.exit(2)

            # default action
            if self.config['general'].has_key("default_action") == False:
                print("Error in config file\nMissing default action parameter.")
                sys.exit(2)
            elif self.config['general']['default_action'] not in self.get_list_of_actions():
                print("Error in config file\n" \
                        "Invalid value for default_action parameter\n" \
                        "Possible values: %s" % ', '.join(self.get_list_of_actions()))
                sys.exit(2)

            # contact table settings
            if self.config.has_key("contact table") == False:
                self.config['contact table'] = {}

            # sort contacts table by first or last name
            if self.config['contact table'].has_key("sort") == False:
                self.config['contact table']['sort'] = "first_name"
            elif self.config['contact table']['sort'] not in ["first_name", "last_name"]:
                print("Error in config file\n" \
                        "Invalid value for sort parameter\n" \
                        "Possible values: first_name, last_name")
                sys.exit(2)

            # reverse contact table
            if self.config['contact table'].has_key("reverse") == False:
                self.config['contact table']['reverse'] = False
            elif self.config['contact table']['reverse'] == "yes":
                self.config['contact table']['reverse'] = True
            elif self.config['contact table']['reverse'] == "no":
                self.config['contact table']['reverse'] = False
            else:
                print("Error in config file\n" \
                        "Invalid value for reverse parameter\n" \
                        "Possible values: yes, no")
                sys.exit(2)

            # group contact table by address book
            if self.config['contact table'].has_key("group_by_addressbook") == False:
                self.config['contact table']['group_by_addressbook'] = False
            elif self.config['contact table']['group_by_addressbook'] == "yes":
                self.config['contact table']['group_by_addressbook'] = True
            elif self.config['contact table']['group_by_addressbook'] == "no":
                self.config['contact table']['group_by_addressbook'] = False
            else:
                print("Error in config file\n" \
                        "Invalid value for group_by_addressbook parameter\n" \
                        "Possible values: yes, no")
                sys.exit(2)

            # nickname
            if self.config['contact table'].has_key("show_nicknames") == False:
                self.config['contact table']['show_nicknames'] = False
            elif self.config['contact table']['show_nicknames'] == "yes":
                self.config['contact table']['show_nicknames'] = True
            elif self.config['contact table']['show_nicknames'] == "no":
                self.config['contact table']['show_nicknames'] = False
            else:
                print("Error in config file\n" \
                        "Invalid value for show_nicknames parameter\n" \
                        "Possible values: yes, no")
                sys.exit(2)

            # show uids
            if self.config['contact table'].has_key("show_uids") == False:
                self.config['contact table']['show_uids'] = True
            elif self.config['contact table']['show_uids'] == "yes":
                self.config['contact table']['show_uids'] = True
            elif self.config['contact table']['show_uids'] == "no":
                self.config['contact table']['show_uids'] = False
            else:
                print("Error in config file\n" \
                        "Invalid value for show_uids parameter\n" \
                        "Possible values: yes, no")
                sys.exit(2)

            # load address books and contacts
            error_counter = 0
            number_of_contacts = 0
            if self.config.has_key("addressbooks") == False:
                print("Error in config file\nMissing main section \"[addressbooks]\".")
                sys.exit(2)
            if len(self.config['addressbooks'].keys()) == 0:
                print("Error in config file\nNo address book entries available.")
                sys.exit(2)
            for name in self.config['addressbooks'].keys():
                # create address book object
                try:
                    address_book = AddressBook(name, self.config['addressbooks'][name]['path'])
                except KeyError as e:
                    print("Error in config file\nMissing path to the \"%s\" address book." % name)
                    sys.exit(2)
                except IOError as e:
                    print("Error in config file\n%s" % e)
                    sys.exit(2)

                # load all vcard files
                for filename in glob.glob(os.path.join(address_book.get_path(), "*.vcf")):
                    try:
                        address_book.add_contact(
                                CarddavObject.from_file(address_book, filename))
                        number_of_contacts += 1
                    except IOError as e:
                        print("Error: Could not open file %s\n%s" % (filename, e))
                        error_counter += 1
                    except vobject.base.ParseError as e:
                        print("Error: Could not parse file %s\n%s" % (filename, e))
                        error_counter += 1

                # add address book to list
                self.address_book_list.append(address_book)

            # check if one or more contacts could not be parsed
            if error_counter > 0:
                print("\n%d of %d vcard files could not be parsed" % (error_counter, number_of_contacts))
                sys.exit(2)

            # check uniqueness of vcard uids and create short uid dictionary
            # that can be disabled with the show_uids option in the config file, if desired
            if self.config['contact table']['show_uids']:
                # check, if multiple contacts have the same uid
                flat_contact_list = []
                for address_book in self.address_book_list:
                    for contact in address_book.get_contact_list():
                        uid = contact.get_uid()
                        if bool(uid):
                            matching_contact = self.uid_dict.get(uid)
                            if matching_contact is None:
                                self.uid_dict[uid] = contact
                            else:
                                print("The contact %s from address book %s" \
                                        " and the contact %s from address book %s have the same uid %s" \
                                        % (matching_contact.get_full_name(),
                                            matching_contact.get_address_book().get_name(),
                                            contact.get_full_name(),
                                            contact.get_address_book().get_name(),
                                            contact.get_uid())
                                        )
                                sys.exit(2)
                            # add to flat contact list
                            flat_contact_list.append(contact)

                # now we can be sure, that all uid's are unique but we don't want to enter
                # the whole uid, if we choose a contact by the -u / --uid option
                # so clear previously filled uid_dict and recreate with the shortest possible uid, so
                # that it's still unique and easier to enter
                # with around 100 contacts that short id should not be longer then two or three characters
                self.uid_dict.clear()
                flat_contact_list.sort(key = lambda x: x.get_uid())
                if len(flat_contact_list) == 1:
                    current = flat_contact_list[0]
                    self.uid_dict[current.get_uid()[:1]] = current
                elif len(flat_contact_list) > 1:
                    # first list element
                    current = flat_contact_list[0]
                    next = flat_contact_list[1]
                    same = helpers.compare_uids(current.get_uid(), next.get_uid())
                    self.uid_dict[current.get_uid()[:same+1]] = current
                    # list elements 1 to len(flat_contact_list)-1
                    for index in range(1, len(flat_contact_list)-1):
                        prev = flat_contact_list[index-1]
                        current = flat_contact_list[index]
                        next = flat_contact_list[index+1]
                        same = max(
                                helpers.compare_uids(prev.get_uid(), current.get_uid()),
                                helpers.compare_uids(current.get_uid(), next.get_uid()))
                        self.uid_dict[current.get_uid()[:same+1]] = current
                    # last list element
                    prev = flat_contact_list[-2]
                    current = flat_contact_list[-1]
                    same = helpers.compare_uids(prev.get_uid(), current.get_uid())
                    self.uid_dict[current.get_uid()[:same+1]] = current


        def get_editor(self):
            return self.config['general']['editor']


        def get_merge_editor(self):
            return self.config['general']['merge_editor']


        def get_default_action(self):
            return self.config['general']['default_action']


        def get_list_of_actions(self):
            return ["list", "details", "export", "email", "phone", "source",
                    "new", "add-email", "merge", "modify", "copy", "move", "remove"]


        def sort_by_name(self):
            return self.config['contact table']['sort']


        def set_sort_by_name(self, criteria):
            self.config['contact table']['sort'] = criteria


        def group_by_addressbook(self):
            return self.config['contact table']['group_by_addressbook']


        def set_group_by_addressbook(self, bool):
            self.config['contact table']['group_by_addressbook'] = bool


        def reverse(self):
            return self.config['contact table']['reverse']


        def set_reverse(self, bool):
            self.config['contact table']['reverse'] = bool


        def show_nicknames(self):
            return self.config['contact table']['show_nicknames']


        def get_all_address_books(self):
            return self.address_book_list


        def get_address_book(self, name):
            for address_book in self.address_book_list:
                if name == address_book.get_name():
                    return address_book
            return None


        def has_uids(self):
            return len(self.uid_dict.keys()) > 0


        def get_shortened_uid(self, uid):
            if bool(uid):
                for length_of_uid in range(len(uid), 0, -1):
                    if self.uid_dict.get(uid[:length_of_uid]) is not None:
                        return uid[:length_of_uid]
            return ""


    ####################################
    # storage for the instance reference
    ####################################
    __instance = None

    def __init__(self):
        """ Create singleton instance """
        # Check whether we already have an instance
        if Config.__instance is None:
            # Create and remember instance
            Config.__instance = Config.__impl()
        # Store instance reference as the only member in the handle
        self.__dict__['_Config__instance'] = Config.__instance


    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)


    def __setattr__(self, attr, value):
        """ Delegate access to implementation """
        return setattr(self.__instance, attr, value)

