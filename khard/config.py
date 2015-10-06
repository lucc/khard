# -*- coding: utf-8 -*-

# singleton code comes from:
# http://code.activestate.com/recipes/52558/#as_content

import os, sys, glob, re, operator
import vobject
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

            # default values for action and nickname settings
            if self.config['general'].has_key("default_action") == False:
                print("Error in config file\nMissing default action parameter.")
                sys.exit(2)
            elif self.config['general']['default_action'] not in self.get_list_of_actions():
                print("Error in config file\n" \
                        "Non existing value for default action parameter\n" \
                        "Possible values are: %s" % ', '.join(self.get_list_of_actions()))
                sys.exit(2)
            if self.config['general'].has_key("show_nicknames") == False:
                self.config['general']['show_nicknames'] = False
            elif self.config['general']['show_nicknames'] == "yes":
                self.config['general']['show_nicknames'] = True
            elif self.config['general']['show_nicknames'] == "no":
                self.config['general']['show_nicknames'] = False
            else:
                print("Error in config file\nshow_nicknames parameter must be yes or no.")
                sys.exit(2)

            # load address books
            error_counter = 0
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
                if error_counter == 1:
                    print("\n1 vcard file could not be parsed")
                elif error_counter > 1:
                    print("\n%d vcard files could not be parsed" % error_counter)
                sys.exit(2)


        def get_editor(self):
            return self.config['general']['editor']


        def get_merge_editor(self):
            return self.config['general']['merge_editor']


        def get_list_of_actions(self):
            return ["list", "details", "source", "mutt", "alot", "phone",
                    "new", "add-email", "merge", "modify", "copy", "move", "remove"]


        def get_default_action(self):
            return self.config['general']['default_action']


        def show_nicknames(self):
            return self.config['general']['show_nicknames']


        def get_all_address_books(self):
            return self.address_book_list


        def get_address_book(self, name):
            for address_book in self.address_book_list:
                if name == address_book.get_name():
                    return address_book
            return None


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

