# -*- coding: utf-8 -*-

# contact object class
# vcard: https://tools.ietf.org/html/rfc6350

import os, sys, string, datetime, re
import vobject, yaml
from pkg_resources import parse_version, get_distribution
import helpers

class CarddavObject:
    def __init__(self, address_book, filename = None):
        self.vcard = None
        self.address_book = address_book
        self.filename = filename
        self.old_vobject_version = False

        # at the moment khard must support two different behavior of the vobject module
        # the versions < 0.8.2 are still widely in use and expect unicode strings for non-ascii characters
        # all newer versions use utf-8 encoded strings directly
        # so we must determine, which version is installed
        try:
            # try to compare the version numbers
            if parse_version(get_distribution("vobject").version) < parse_version("0.8.2"):
                self.old_vobject_version = True
        except Exception as e:
            # if something goes wrong during vobject version comparison, try to serialize a
            # minimal vcard object with umlauts
            # if that fails, khard still uses a vobject version < 0.8.2
            v = vobject.vCard()
            o = v.add("fn")
            o.value = "Markus Schröder"
            o = v.add("n")
            o.value = vobject.vcard.Name(family="Schröder", given="Markus")
            try:
                v.serialize()
            except UnicodeDecodeError as e:
                self.old_vobject_version = True

        # vcard supports the following type values
        self.supported_phone_types = ["bbs", "car", "cell", "fax", "home", "isdn",
                "msg", "modem", "pager", "pcs", "pref", "video", "voice", "work"]
        self.supported_email_types = ["home", "internet", "pref", "uri", "work", "x400"]
        self.supported_address_types = ["home", "pref", "work"]

        # load vcard
        if self.filename is None:
            # create new vcard object
            self.vcard = vobject.vCard()
            # uid
            uid_obj = self.vcard.add('uid')
            uid_obj.value = helpers.get_random_uid()
            # use uid for vcard filename
            self.filename = os.path.join(address_book.get_path(),
                    self.vcard.uid.value + ".vcf")

        else:
            # create vcard from .vcf file
            try:
                file = open(self.filename, "r")
                contents = file.read()
                file.close()
            except IOError as e:
                raise
            # create vcard object
            try:
                self.vcard = vobject.readOne(contents)
            except vobject.base.ParseError as e:
                # if creation fails, try to repair vcard contents
                try:
                    self.vcard = vobject.readOne(
                            self.filter_invalid_tags(contents))
                    self.write_to_file(overwrite=True)
                except vobject.base.ParseError as e:
                    raise
            # organisation value
            # some newer versions of vobject module don't return a list but a single string
            # but the library awaits a list, if the vcard is serialized again
            # so fix that by splitting the organisation value manually at the ";"
            try:
                organisation = self.vcard.org.value
            except AttributeError as e:
                pass
            else:
                if not isinstance(organisation, list):
                    self.vcard.org.value = organisation.split(";")


    #######################################
    # factory methods to create new contact
    #######################################

    @classmethod
    def new_contact(cls, address_book):
        """ use this to create a new and empty contact """
        return cls(address_book)

    @classmethod
    def from_file(cls, address_book, filename):
        """ Use this if you want to create a new contact from an existing .vcf file """
        return cls(address_book, filename)

    @classmethod
    def from_user_input(cls, address_book, user_input):
        """ Use this if you want to create a new contact from user input """
        contact = cls(address_book)
        contact.process_user_input(user_input)
        return contact

    @classmethod
    def from_existing_contact_with_new_user_input(cls, contact, user_input):
        """ use this if you want to clone an existing contact and  replace its data with new user input in one step """
        contact = cls(contact.get_address_book(), contact.get_filename())
        contact.process_user_input(user_input)
        return contact


    ######################################
    # overwrite some default class methods
    ######################################

    def __str__(self):
        return self.get_full_name()

    def __eq__(self, other):
        return isinstance(other, CarddavObject) \
                and self.print_vcard(show_address_book=False, show_uid=False) == other.print_vcard(show_address_book=False, show_uid=False)

    def __ne__(self, other):
        return not self == other


    #####################
    # getters and setters
    #####################

    def get_address_book(self):
        return self.address_book

    def get_uid(self):
        try:
            return self.vcard_value_to_string(self.vcard.uid.value)
        except AttributeError as e:
            return ""

    def set_uid(self, uid):
        # try to remove old uid
        try:
            self.vcard.remove(self.vcard.uid)
        except AttributeError as e:
            pass
        uid_obj = self.vcard.add('uid')
        uid_obj.value = self.string_to_vcard_value(uid, output="text")

    def get_filename(self):
        return self.filename

    def set_filename(self, filename):
        self.filename = filename

    def get_name_prefix(self):
        try:
            return self.vcard_value_to_string(self.vcard.n.value.prefix)
        except AttributeError as e:
            return ""

    def get_first_name(self):
        try:
            return self.vcard_value_to_string(self.vcard.n.value.given)
        except AttributeError as e:
            return ""

    def get_additional_name(self):
        try:
            return self.vcard_value_to_string(self.vcard.n.value.additional)
        except AttributeError as e:
            return ""

    def get_last_name(self):
        try:
            return self.vcard_value_to_string(self.vcard.n.value.family)
        except AttributeError as e:
            return ""

    def get_name_suffix(self):
        try:
            return self.vcard_value_to_string(self.vcard.n.value.suffix)
        except AttributeError as e:
            return ""

    def get_full_name(self):
        try:
            return self.vcard_value_to_string(self.vcard.fn.value)
        except AttributeError as e:
            return ""

    def set_name(self, prefix, first_name, additional_name, last_name, suffix):
        # n
        name_obj = self.vcard.add('n')
        name_obj.value = vobject.vcard.Name(
                prefix=self.string_to_vcard_value(prefix, output="list"),
                given=self.string_to_vcard_value(first_name, output="list"),
                additional=self.string_to_vcard_value(additional_name, output="list"),
                family=self.string_to_vcard_value(last_name, output="list"),
                suffix=self.string_to_vcard_value(suffix, output="list"))
        # fn
        if not self.vcard.getChildValue("fn") \
                and (self.get_first_name() != "" or self.get_last_name() != ""):
            names = []
            if self.get_name_prefix() != "":
                names.append(self.get_name_prefix())
            if self.get_first_name() != "":
                names.append(self.get_first_name())
            if self.get_last_name() != "":
                names.append(self.get_last_name())
            if self.get_name_suffix() != "":
                names.append(self.get_name_suffix())
            name_obj = self.vcard.add('fn')
            name_obj.value = self.string_to_vcard_value(
                    ' '.join(names).replace(",", ""), output="text")

    def get_organisation(self):
        try:
            return self.vcard_value_to_string(self.vcard.org.value)
        except AttributeError as e:
            return ""

    def set_organisation(self, organisation):
        org_obj = self.vcard.add('org')
        org_obj.value = self.string_to_vcard_value(organisation, output="list")
        # check if fn attribute is already present
        if not self.vcard.getChildValue("fn") \
                and self.get_organisation() != "":
            # if not, set fn to organisation name
            name_obj = self.vcard.add('fn')
            name_obj.value = self.string_to_vcard_value(self.get_organisation(), output="text")
            showas_obj = self.vcard.add('x-abshowas')
            showas_obj.value = "COMPANY"

    def get_title(self):
        try:
            return self.vcard_value_to_string(self.vcard.title.value)
        except AttributeError as e:
            return ""

    def set_title(self, title):
        title_obj = self.vcard.add('title')
        title_obj.value = self.string_to_vcard_value(title, output="text")

    def get_role(self):
        try:
            return self.vcard_value_to_string(self.vcard.role.value)
        except AttributeError as e:
            return ""

    def set_role(self, role):
        role_obj = self.vcard.add('role')
        role_obj.value = self.string_to_vcard_value(role, output="text")

    def get_phone_numbers(self):
        phone_list = []
        for child in self.vcard.getChildren():
            if child.name == "TEL":
                type = self.get_type_for_vcard_object(child) or "voice"
                number = child.value
                phone_list.append(
                        {
                            "type" : self.vcard_value_to_string(type),
                            "value" : self.vcard_value_to_string(number)
                        })
        return sorted(phone_list, key=lambda k: k['type'].lower())

    def add_phone_number(self, type, number):
        standard_types, custom_types = self.parse_type_value(
                type, number, self.supported_phone_types)
        phone_obj = self.vcard.add('tel')
        phone_obj.value = number
        if standard_types != "":
            phone_obj.type_param = self.string_to_vcard_value(standard_types, output="list")
        else:
            number_of_custom_phone_number_labels = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith("itemtel"):
                    number_of_custom_phone_number_labels += 1
            group_name = "itemtel%d" % (number_of_custom_phone_number_labels+1)
            phone_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = self.string_to_vcard_value(custom_types, output="text")

    def get_email_addresses(self):
        email_list = []
        for child in self.vcard.getChildren():
            if child.name == "EMAIL":
                type = self.get_type_for_vcard_object(child) or "internet"
                address = child.value
                email_list.append(
                        {
                            "type" : self.vcard_value_to_string(type),
                            "value" : self.vcard_value_to_string(address)
                        })
        return sorted(email_list, key=lambda k: k['type'].lower())

    def add_email_address(self, type, address):
        standard_types, custom_types = self.parse_type_value(
                type, address, self.supported_email_types)
        email_obj = self.vcard.add('email')
        email_obj.value = address
        if standard_types != "":
            email_obj.type_param = self.string_to_vcard_value(standard_types, output="list")
        else:
            number_of_custom_email_labels = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith("itememail"):
                    number_of_custom_email_labels += 1
            group_name = "itememail%d" % (number_of_custom_email_labels+1)
            email_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = self.string_to_vcard_value(custom_types, output="text")

    def get_post_addresses(self):
        address_list = []
        for child in self.vcard.getChildren():
            if child.name == "ADR":
                type = self.get_type_for_vcard_object(child) or "work"
                address = child.value
                address_list.append(
                        {
                            "type" : self.vcard_value_to_string(type),
                            "street" : self.vcard_value_to_string(address.street),
                            "code" : self.vcard_value_to_string(address.code),
                            "city" : self.vcard_value_to_string(address.city),
                            "region" : self.vcard_value_to_string(address.region),
                            "country" : self.vcard_value_to_string(address.country)
                        })
        return sorted(address_list, key=lambda k: k['type'].lower())

    def add_post_address(self, type, street, code, city, region, country):
        standard_types, custom_types = self.parse_type_value(
                type, "%s, %s" % (street, city), self.supported_address_types)
        adr_obj = self.vcard.add('adr')
        adr_obj.value = vobject.vcard.Address(
                street = self.string_to_vcard_value(street, output="list"),
                code = self.string_to_vcard_value(code, output="list"),
                city = self.string_to_vcard_value(city, output="list"),
                region = self.string_to_vcard_value(region, output="list"),
                country = self.string_to_vcard_value(country, output="list"))
        if standard_types != "":
            adr_obj.type_param = self.string_to_vcard_value(standard_types, output="list")
        else:
            number_of_custom_post_address_labels = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith("itemadr"):
                    number_of_custom_post_address_labels += 1
            group_name = "itemadr%d" % (number_of_custom_post_address_labels+1)
            adr_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = self.string_to_vcard_value(custom_types, output="text")

    def get_categories(self):
        try:
            return self.vcard_value_to_string(self.vcard.categories.value)
        except AttributeError as e:
            return ""

    def set_categories(self, categories):
        categories_obj = self.vcard.add('categories')
        categories_obj.value = self.string_to_vcard_value(categories, output="list")

    def get_nickname(self):
        try:
            return self.vcard_value_to_string(self.vcard.nickname.value)
        except AttributeError as e:
            return ""

    def set_nickname(self, nick_name):
        nickname_obj = self.vcard.add('nickname')
        nickname_obj.value = self.string_to_vcard_value(nick_name, output="text")

    def get_note(self):
        try:
            return self.vcard_value_to_string(self.vcard.note.value)
        except AttributeError as e:
            return ""

    def set_note(self, note):
        note_obj = self.vcard.add('note')
        note_obj.value = self.string_to_vcard_value(note, output="text")

    def get_jabber_id(self):
        try:
            return self.vcard_value_to_string(self.vcard.x_jabber.value)
        except AttributeError as e:
            return ""

    def set_jabber_id(self, jabber_id):
        jabber_obj = self.vcard.add('x-jabber')
        jabber_obj.value = self.string_to_vcard_value(jabber_id, output="text")

    def get_skype_id(self):
        try:
            return self.vcard_value_to_string(self.vcard.x_skype.value)
        except AttributeError as e:
            return ""

    def set_skype_id(self, skype_id):
        skype_obj = self.vcard.add('x-skype')
        skype_obj.value = self.string_to_vcard_value(skype_id, output="text")

    def get_twitter_id(self):
        try:
            return self.vcard_value_to_string(self.vcard.x_twitter.value)
        except AttributeError as e:
            return ""

    def set_twitter_id(self, twitter_id):
        twitter_obj = self.vcard.add('x-twitter')
        twitter_obj.value = self.string_to_vcard_value(twitter_id, output="text")

    def get_webpage(self):
        try:
            return self.vcard_value_to_string(self.vcard.url.value)
        except AttributeError as e:
            return ""

    def set_webpage(self, webpage):
        webpage_obj = self.vcard.add('url')
        webpage_obj.value = self.string_to_vcard_value(webpage, output="text")

    def get_birthday(self):
        """:returns: contacts birthday or None if not available
            :rtype: datetime.datetime
        """
        try:
            return datetime.datetime.strptime(
                    self.vcard_value_to_string(self.vcard.bday.value).replace('-', ''),
                    "%Y%m%d")
        except AttributeError as e:
            return None
        except ValueError as e:
            return None

    def set_birthday(self, date):
        bday_obj = self.vcard.add('bday')
        bday_obj.value = "%.4d%.2d%.2d" % (date.year, date.month, date.day)


    #######################
    # object helper methods
    #######################

    def clean_vcard(self):
        # rev
        try:
            self.vcard.remove(self.vcard.rev)
        except AttributeError as e:
            pass
        # n
        try:
            self.vcard.remove(self.vcard.n)
        except AttributeError as e:
            pass
        # fn
        try:
            self.vcard.remove(self.vcard.fn)
        except AttributeError as e:
            pass
        # nickname
        try:
            self.vcard.remove(self.vcard.nickname)
        except AttributeError as e:
            pass
        # organisation
        try:
            self.vcard.remove(self.vcard.org)
        except AttributeError as e:
            pass
        try:
            self.vcard.remove(self.vcard.x_abshowas)
        except AttributeError as e:
            pass
        # title
        try:
            self.vcard.remove(self.vcard.title)
        except AttributeError as e:
            pass
        # role
        try:
            self.vcard.remove(self.vcard.role)
        except AttributeError as e:
            pass
        # categories
        try:
            self.vcard.remove(self.vcard.categories)
        except AttributeError as e:
            pass
        # phone
        while True:
            try:
                self.vcard.remove(self.vcard.tel)
            except AttributeError as e:
                break
        # email addresses
        while True:
            try:
                self.vcard.remove(self.vcard.email)
            except AttributeError as e:
                break
        # addresses
        while True:
            try:
                self.vcard.remove(self.vcard.adr)
            except AttributeError as e:
                break
        # instant messaging and social networks
        try:
            self.vcard.remove(self.vcard.x_jabber)
        except AttributeError as e:
            pass
        try:
            self.vcard.remove(self.vcard.x_skype)
        except AttributeError as e:
            pass
        try:
            self.vcard.remove(self.vcard.x_twitter)
        except AttributeError as e:
            pass
        try:
            self.vcard.remove(self.vcard.url)
        except AttributeError as e:
            pass
        # note
        try:
            self.vcard.remove(self.vcard.note)
        except AttributeError as e:
            pass
        # birthday
        try:
            self.vcard.remove(self.vcard.bday)
        except AttributeError as e:
            pass
        # x-ablabel
        while True:
            try:
                self.vcard.remove(self.vcard.x_ablabel)
            except AttributeError as e:
                break

    def filter_invalid_tags(self, contents):
        contents = re.sub('(?i)' + re.escape('X-messaging/aim-All'), 'X-AIM', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/gadu-All'), 'X-GADUGADU', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/groupwise-All'), 'X-GROUPWISE', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/icq-All'), 'X-ICQ', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/xmpp-All'), 'X-JABBER', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/msn-All'), 'X-MSN', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/yahoo-All'), 'X-YAHOO', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/skype-All'), 'X-SKYPE', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/irc-All'), 'X-IRC', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/sip-All'), 'X-SIP', contents)
        return contents

    def process_user_input(self, input):
        # parse user input string
        try:
            contact_data = yaml.load(input, Loader=yaml.BaseLoader)
        except yaml.parser.ParserError as e:
            raise ValueError(e)
        except yaml.scanner.ScannerError as e:
            raise ValueError(e)

        # clean vcard
        self.clean_vcard()

        # update ref
        dt = datetime.datetime.now()
        rev_obj = self.vcard.add('rev')
        rev_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2dZ" \
                % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second) 

        # check for available data
        # at least enter name or organisation
        if not bool(contact_data.get("First name")) \
                and not bool(contact_data.get("Last name")) \
                and not bool(contact_data.get("Organisation")):
            raise ValueError("Error: You must either enter a name or an organisation")
        else:
            # set name
            self.set_name(
                    contact_data.get("Prefix") or "",
                    contact_data.get("First name") or "",
                    contact_data.get("Additional") or "",
                    contact_data.get("Last name") or "",
                    contact_data.get("Suffix") or "")

        # organisation
        if bool(contact_data.get("Organisation")):
            self.set_organisation(contact_data.get("Organisation"))
        # role
        if bool(contact_data.get("Role")):
            self.set_role(contact_data.get("Role"))
        # title
        if bool(contact_data.get("Title")):
            self.set_title(contact_data.get("Title"))

        # phone
        try:
            for label, number in contact_data.get("Phone").items():
                if number != "":
                    self.add_phone_number(label, number)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # email
        try:
            for label, address in contact_data.get("Email").items():
                if address != "":
                    self.add_email_address(label, address)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # post addresses
        try:
            for label, address in contact_data.get("Address").items():
                try:
                    number_of_non_empty_address_values = 0
                    for key, value in address.items():
                        if key in ["Street", "Code", "City", "Region", "Country"] \
                                and value != "":
                            number_of_non_empty_address_values += 1
                    if number_of_non_empty_address_values > 0:
                        self.add_post_address(
                                label,
                                address.get("Street") or "",
                                address.get("Code") or "",
                                address.get("City") or "",
                                address.get("Region") or "",
                                address.get("Country") or "")
                except TypeError as e:
                    raise ValueError("Error during parsing of address with label %s" % label)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # instant messaging and social networks
        if bool(contact_data.get("Jabber")):
            self.set_jabber_id(contact_data.get("Jabber"))
        if bool(contact_data.get("Skype")):
            self.set_skype_id(contact_data.get("Skype"))
        if bool(contact_data.get("Twitter")):
            self.set_twitter_id(contact_data.get("Twitter"))
        if bool(contact_data.get("Webpage")):
            self.set_webpage(contact_data.get("Webpage"))

        # miscellaneous stuff
        # birthday
        if bool(contact_data.get("Birthday")):
            supported_date_formats = ["%d-%m-%Y", "%Y-%m-%d"]
            for date_format in supported_date_formats:
                try:
                    self.set_birthday(
                            datetime.datetime.strptime(
                                re.sub("\D", "-", contact_data.get("Birthday")),
                                date_format)
                            )
                except ValueError as e:
                    pass
                else:
                    break
            if not self.get_birthday():
                raise ValueError("Error: Wrong date format\nExamples: 21.10.1988, 1988.10.21 or 1988-10-21")
        # categories
        if bool(contact_data.get("Categories")):
            self.set_categories(contact_data.get("Categories"))
        # nickname
        if bool(contact_data.get("Nickname")):
            self.set_nickname(contact_data.get("Nickname"))
        # note
        if bool(contact_data.get("Note")):
            self.set_note(contact_data.get("Note"))

    def get_template(self):
        strings = []
        for line in helpers.get_new_contact_template(self.get_address_book().get_name()).splitlines():
            if line.startswith("#"):
                strings.append(line)
            elif line == "":
                strings.append(line)

            elif line.lower().startswith("prefix"):
                strings.append("Prefix     : %s" % self.get_name_prefix())
            elif line.lower().startswith("first name"):
                strings.append("First name : %s" % self.get_first_name())
            elif line.lower().startswith("additional"):
                strings.append("Additional : %s" % self.get_additional_name())
            elif line.lower().startswith("last name"):
                strings.append("Last name  : %s" % self.get_last_name())
            elif line.lower().startswith("suffix"):
                strings.append("Suffix     : %s" % self.get_name_suffix())
            elif line.lower().startswith("nickname"):
                strings.append("Nickname   : %s" % self.get_nickname())

            elif line.lower().startswith("organisation"):
                strings.append("Organisation : %s" % self.get_organisation())
            elif line.lower().startswith("title"):
                strings.append("Title        : %s" % self.get_title())
            elif line.lower().startswith("role"):
                strings.append("Role         : %s" % self.get_role())
            elif line.lower().startswith("categories"):
                strings.append("Categories : %s" % self.get_categories())

            elif line.lower().startswith("phone"):
                strings.append("Phone :")
                if len(self.get_phone_numbers()) == 0:
                    strings.append("    cell : ")
                    strings.append("    work : ")
                else:
                    for entry in self.get_phone_numbers():
                        strings.append("    %s : %s" % (entry['type'], entry['value']))

            elif line.lower().startswith("email"):
                strings.append("Email :")
                if len(self.get_email_addresses()) == 0:
                    strings.append("    home : ")
                    strings.append("    work : ")
                else:
                    for entry in self.get_email_addresses():
                        strings.append("    %s : %s" % (entry['type'], entry['value']))

            elif line.lower().startswith("address"):
                strings.append("Address :")
                if len(self.get_post_addresses()) == 0:
                    strings.append("    home :")
                    strings.append("        Street  : ")
                    strings.append("        Code    : ")
                    strings.append("        City    : ")
                    strings.append("        Region  : ")
                    strings.append("        Country : ")
                else:
                    for entry in self.get_post_addresses():
                        strings.append("    %s :" % entry['type'])
                        strings.append("        Street  : %s" % entry['street'])
                        strings.append("        Code    : %s" % entry['code'])
                        strings.append("        City    : %s" % entry['city'])
                        strings.append("        Region  : %s" % entry['region'])
                        strings.append("        Country : %s" % entry['country'])

            elif line.lower().startswith("jabber"):
                strings.append("Jabber  : %s" % self.get_jabber_id())
            elif line.lower().startswith("skype"):
                strings.append("Skype   : %s" % self.get_skype_id())
            elif line.lower().startswith("twitter"):
                strings.append("Twitter : %s" % self.get_twitter_id())
            elif line.lower().startswith("webpage"):
                strings.append("Webpage : %s" % self.get_webpage())
            elif line.lower().startswith("birthday"):
                date = self.get_birthday()
                if not date:
                    strings.append("Birthday : ")
                else:
                    strings.append("Birthday : %.2d.%.2d.%.4d" % (date.day, date.month, date.year))
            elif line.lower().startswith("note"):
                note = self.get_note()
                if note == "":
                    strings.append("Note : ")
                else:
                    strings.append("Note : |")
                    for note_line in note.split("\n"):
                        strings.append("    %s" % note_line)
        return '\n'.join(strings)

    def print_vcard(self, show_address_book = True, show_uid = True):
        strings = []
        # name
        if self.get_first_name() != "" or self.get_last_name() != "":
            names = []
            if self.get_name_prefix() != "":
                names.append(self.get_name_prefix())
            if self.get_first_name() != "":
                names.append(self.get_first_name())
            if self.get_additional_name() != "":
                names.append(self.get_additional_name())
            if self.get_last_name() != "":
                names.append(self.get_last_name())
            if self.get_name_suffix() != "":
                names.append(self.get_name_suffix())
            strings.append("Name: %s" % ' '.join(names).replace(",", ""))
            if self.get_nickname() != "":
                strings.append("    Nickname: %s" % self.get_nickname())
        # organisation
        if self.get_organisation() != "":
            strings.append("Organisation: %s" % self.get_organisation())
            if self.get_title() != "":
                strings.append("    Title: %s" % self.get_title())
            if self.get_role() != "":
                strings.append("    Role: %s" % self.get_role())
        if show_address_book:
            strings.append("Address book: %s" % self.address_book.get_name())
        if self.get_categories() != "":
            strings.append("Categories\n    %s" % self.get_categories())
        if len(self.get_phone_numbers()) > 0:
            strings.append("Phone")
            for entry in self.get_phone_numbers():
                strings.append("    %s: %s" % (entry['type'], entry['value']))
        if len(self.get_email_addresses()) > 0:
            strings.append("E-Mail")
            for entry in self.get_email_addresses():
                strings.append("    %s: %s" % (entry['type'], entry['value']))
        if len(self.get_post_addresses()) > 0:
            strings.append("Address")
            for entry in self.get_post_addresses():
                strings.append("    %s:" % entry['type'])
                if entry['street'] != "":
                    strings.append("        %s" % entry['street'])
                if entry['code'] != "" and entry['city'] != "":
                    strings.append("        %s %s" % (entry['code'], entry['city']))
                elif entry['code'] != "":
                    strings.append("        %s" % entry['code'])
                elif entry['city'] != "":
                    strings.append("        %s" % entry['city'])
                if entry['region'] != "" and entry['country'] != "":
                    strings.append("        %s, %s" % (entry['region'], entry['country']))
                elif entry['region'] != "":
                    strings.append("        %s" % entry['region'])
                elif entry['country'] != "":
                    strings.append("        %s" % entry['country'])
        if self.get_jabber_id() != "" \
                or self.get_skype_id() != "" \
                or self.get_twitter_id() != "" \
                or self.get_webpage() != "":
            strings.append("Instant messaging and social networks")
            if self.get_jabber_id() != "":
                strings.append("    Jabber:  %s" % self.get_jabber_id())
            if self.get_skype_id() != "":
                strings.append("    Skype:   %s" % self.get_skype_id())
            if self.get_twitter_id() != "":
                strings.append("    Twitter: %s" % self.get_twitter_id())
            if self.get_webpage() != "":
                strings.append("    Webpage: %s" % self.get_webpage())
        if self.get_birthday() != None \
                or self.get_note() != "" \
                or show_uid:
            strings.append("Miscellaneous")
            if show_uid and self.get_uid() != "":
                strings.append("    UID: %s" % self.get_uid())
            if self.get_birthday() != None:
                date = self.get_birthday()
                strings.append("    Birthday: %.2d.%.2d.%.4d" % (date.day, date.month, date.year))
            if self.get_note() != "":
                if len(self.get_note().split("\n")) == 1:
                    strings.append("    Note: %s" % self.get_note())
                else:
                    strings.append("    Note:")
                    for note_line in self.get_note().split("\n"):
                        strings.append("        %s" % note_line)
        return '\n'.join(strings)

    def write_to_file(self, overwrite=False):
        if os.path.exists(self.filename) and overwrite == False:
            print("Error: vcard with the file name %s already exists" \
                    % os.path.basename(self.filename))
            sys.exit(4)
        try:
            vcard_output = self.vcard.serialize()
            file = open(self.filename, "w")
            file.write(vcard_output)
            file.close()
        except vobject.base.ValidateError as e:
            print("Error: Vcard is not valid.\n%s" % e)
            sys.exit(4)
        except IOError as e:
            print("Error: Can't write\n%s" % e)
            sys.exit(4)

    def delete_vcard_file(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)
        else:
            print("Error: Vcard file %s does not exist." % self.filename)
            sys.exit(4)

    def vcard_value_to_string(self, value):
        """convert values from source vcard to string
        function is used by all getters
        includes:
            vobject version < 0.8.2 still uses unicode, so encode to utf-8
            if it's a list, join to a comma separated string
        """
        if isinstance(value, list):
            value = ', '.join(value)
        if isinstance(value, unicode):
            value = value.encode("utf-8")
        return value

    def string_to_vcard_value(self, string, output):
        """Convert strings to vcard object data
        function is used by all setters
        The output parameter specifies the required type, currently we only need simple text and lists
        vobject version < 0.8.2 needs unicode, so decode if necessary
        """
        # the yaml parser returns unicode strings, so fix that first
        if isinstance(string, unicode):
            string = string.encode("utf-8")
        # possible vcard object types: list and text
        if output == "list":
            # use that for vcard objects, which require list output
            # example: name or categories fields
            #
            # devide by comma char
            value_list = [ x.strip() for x in string.split(",") ]
            if self.old_vobject_version:
                value_list = [ x.decode("utf-8") for x in value_list ]
            return value_list
        if output == "text":
            # use that for vcard objects, which require a single text output
            # examples: nickname and note field
            string = string.strip()
            if self.old_vobject_version:
                string = string.decode("utf-8")
            return string

    def get_type_for_vcard_object(self, object):
        # try to find label group for custom value type
        if object.group:
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group == object.group:
                    return label.value
        # if that fails, try to load type from params dict
        type = object.params.get("TYPE")
        if type:
            if isinstance(type, list):
                return sorted(type)
            return type
        return None

    def parse_type_value(self, types, value, supported_types):
        """ parse type value of phone numbers, email and post addresses
        :param types: one or several type values, separated by comma character
        :type types: str or unicode
        :param value: the corresponding label, required for more verbose exceptions
        :type value: str or unicode
        :param supported_types: all allowed standard types
        :type supported_types: list
        :returns: tuple of standard and custom types
        :rtype: tuple(str, str)
        """
        if isinstance(types, unicode):
            types = types.encode("utf-8")
        if isinstance(value, unicode):
            value = value.encode("utf-8")
        custom_types = []
        standard_types = []
        for type in types.split(","):
            type = type.strip()
            if type.lower() in supported_types:
                standard_types.append(type)
            else:
                custom_types.append(type)
        # throw an exception if the type contains more than one custom label
        if len(custom_types) == 0 and len(standard_types) == 0:
            raise ValueError("Error: Missing type for %s" % value)
        elif len(custom_types) > 0 and len(standard_types) > 0:
            raise ValueError("Error: Mixing of standard and custom types for %s not allowed\nInput: %s" % (value, types))
        elif len(custom_types) > 1:
            raise ValueError("Error: Only a single custom type for %s allowed\nInput: %s" % (value, types))
        return (','.join(standard_types), ','.join(custom_types))

