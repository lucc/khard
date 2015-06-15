# -*- coding: utf-8 -*-

# singleton code comes from:
# http://code.activestate.com/recipes/52558/#as_content

import os, sys, glob, re, operator
from configobj import ConfigObj
from carddav_object import CarddavObject

class Config:
    """ A python singleton """

    class __impl:
        """ Implementation of the singleton interface """
        def __init__(self):
            # load config file
            config_file = os.path.join(os.path.expanduser("~"), ".config", "khard", "khard.conf")
            if os.path.exists(config_file) == False:
                print "Config file %s not available" % config_file
                sys.exit(2)
            self.config = ConfigObj(config_file, interpolation=False)

            # general settings
            if self.config.has_key("general") == False:
                print "Error in config file\nMissing main section \"[general]\"."
                sys.exit(2)
            if self.config['general'].has_key("editor") == False:
                print "Error in config file\nMissing editor parameter. Example: editor = /usr/bin/vim."
                sys.exit(2)
            elif os.path.exists(self.config['general']['editor']) == False:
                print "Error in config file\nInvalid editor path."
                sys.exit(2)
            if self.config['general'].has_key("default_country") == False:
                print "Error in config file\nMissing default country parameter."
                sys.exit(2)
            if self.config['general'].has_key("default_action") == False:
                print "Error in config file\nMissing default action parameter."
                sys.exit(2)
            elif self.config['general']['default_action'] not in ["list", "details", "new", "add-email", "modify", "remove", "mutt", "phone", "alot", "source"]:
                print "Error in config file\n" \
                        "Non existing value for default action parameter\n" \
                        "Possible values are: list, details, mutt, phone, alot, new, add-email, modify, remove and source"
                sys.exit(2)
            if self.config['general'].has_key("show_nicknames") == False:
                self.config['general']['show_nicknames'] = False
            elif self.config['general']['show_nicknames'] == "yes":
                self.config['general']['show_nicknames'] = True
            elif self.config['general']['show_nicknames'] == "no":
                self.config['general']['show_nicknames'] = False
            else:
                print "Error in config file\nshow_nicknames parameter must be yes or no."
                sys.exit(2)

            # load address books
            if self.config.has_key("addressbooks") == False:
                print "Error in config file\nMissing main section \"[addressbooks]\"."
                sys.exit(2)
            if self.config['addressbooks'].keys().__len__() == 0:
                print "Error in config file\nNo address book entries available."
                sys.exit(2)
            for name in self.config['addressbooks'].keys():
                addressbook = self.config['addressbooks'][name]
                if addressbook.has_key("path") == False:
                    print "Error in config file\nMissing path to the \"%s\" address book." % name
                    sys.exit(2)
                if addressbook['path'].startswith("~"):
                    addressbook['path'] = addressbook['path'].replace("~", os.path.expanduser("~"))
                if os.path.exists(addressbook['path']) == False:
                    print "Error in config file\nThe path %s to the address book %s does not exist." % (addressbook['path'], name)
                    sys.exit(2)
                # set address book name
                addressbook['name'] = name
                # load all vcard files
                error_counter = 0
                addressbook['vcards'] = []
                for filename in glob.glob(os.path.join(addressbook['path'], "*.vcf")):
                    try:
                        addressbook['vcards'].append(
                                CarddavObject(addressbook['name'], addressbook['path'], filename))
                    except CarddavObject.VCardParseError as e:
                        error_counter += 1
                        print "Parse Error: %s" % e
                if error_counter == 1:
                    print "1 vcard file could not be parsed"
                elif error_counter > 1:
                    print "%d vcard files could not be parsed" % error_counter

        def get_editor(self):
            return self.config['general']['editor']

        def get_default_country(self):
            return self.config['general']['default_country']

        def get_default_action(self):
            return self.config['general']['default_action']

        def show_nicknames(self):
            return self.config['general']['show_nicknames']

        def has_addressbook(self, name):
            return self.config['addressbooks'].has_key(name)

        def get_all_addressbooks(self):
            return self.config['addressbooks']

        def get_addressbook(self, name):
            try:
                return self.config['addressbooks'][name]
            except KeyError as e:
                print "The address book \"%s\" does not exist" % name
                sys.exit(3)

        def get_vcard_objects(self, addressbook_names, sort_criteria, reverse, search, strict_search):
            """returns a list of vcard objects
            :param addressbook_names: list of selected address books
            :type addressbook_names: list(str)
            :param sort_criteria: sort list by given criteria
            :type sort_criteria: str
            :param reverse: reverse ordering
            :type reverse: bool
            :param search: filter contact list
            :type search: str
            :param strict_search: if True, search only in full name field
            :type strict_search: bool
            :returns: list of vcard objects
            :rtype: list(vobject.vCard)
            """
            vcard_list = []
            # regexp
            if search == None or search == "":
                regexp = re.compile(".*", re.IGNORECASE)
            else:
                regexp = re.compile(search.replace(" ", ".*"), re.IGNORECASE)
            for addressbook_name in addressbook_names:
                addressbook = self. get_addressbook(addressbook_name)
                for vcard in addressbook['vcards']:
                    if strict_search:
                        if regexp.search(vcard.get_full_name()) != None:
                            vcard_list.append(vcard)
                    else:
                        if regexp.search(vcard.print_vcard()) != None:
                            vcard_list.append(vcard)
                        else:
                            # special case for phone numbers without a space between prefix and number
                            for phone_entry in vcard.get_phone_numbers():
                                if regexp.search(re.sub("\D", "", phone_entry['value'])) != None:
                                    vcard_list.append(vcard)
                                    break
            if sort_criteria == "addressbook":
                return sorted(vcard_list,
                        key = lambda x: (x.get_addressbook_name().lower(),
                            x.get_full_name().lower()),
                        reverse=reverse)
            else:
                return sorted(vcard_list, key = lambda x: x.get_full_name().lower(), reverse=reverse)

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

