# -*- coding: utf-8 -*-

# contact object class
# vcard: https://tools.ietf.org/html/rfc6350

import os, sys, string, datetime, re
import vobject, yaml
from atomicwrites import atomic_write
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

    def get_filename(self):
        return self.filename

    def set_filename(self, filename):
        self.filename = filename

    def get_address_book(self):
        return self.address_book

    def get_rev(self):
        try:
            return self.vcard_value_to_string(self.vcard.rev.value)
        except AttributeError as e:
            return ""

    def add_rev(self, dt):
        rev_obj = self.vcard.add('rev')
        rev_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2dZ" \
                % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second) 

    def get_uid(self):
        try:
            return self.vcard_value_to_string(self.vcard.uid.value)
        except AttributeError as e:
            return ""

    def add_uid(self, uid):
        uid_obj = self.vcard.add('uid')
        uid_obj.value = self.string_to_vcard_value(uid, output="text")

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

    def get_first_name_last_name(self):
        if self.get_first_name() != "" and self.get_last_name() != "":
            return "%s %s" % (self.get_first_name(), self.get_last_name())
        elif self.get_first_name() != "":
            return self.get_first_name()
        elif self.get_last_name() != "":
            return self.get_last_name()
        else:
            return self.get_full_name()

    def get_last_name_first_name(self):
        if self.get_first_name() != "" and self.get_last_name() != "":
            return "%s, %s" % (self.get_last_name(), self.get_first_name())
        elif self.get_first_name() != "":
            return self.get_first_name()
        elif self.get_last_name() != "":
            return self.get_last_name()
        else:
            return self.get_full_name()

    def add_name(self, prefix, first_name, additional_name, last_name, suffix):
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

    def get_organisations(self):
        organisations = []
        for child in self.vcard.getChildren():
            if child.name == "ORG":
                # some newer versions of vobject module don't return a list but a single string
                # but the library awaits a list, if the vcard is serialized again
                # so fix that by splitting the organisation value manually at the ";"
                if not isinstance(child.value, list):
                    child.value = [ x.replace("\\;", ";") \
                            for x in re.split("[^\\\\];", child.value) ]
                organisations.append(self.vcard_value_to_string(child.value))
        return organisations

    def add_organisation(self, organisation):
        org_obj = self.vcard.add('org')
        org_obj.value = self.string_to_vcard_value(organisation, output="list")
        # check if fn attribute is already present
        if not self.vcard.getChildValue("fn") \
                and len(self.get_organisations()) > 0:
            # if not, set fn to organisation name
            name_obj = self.vcard.add('fn')
            name_obj.value = self.string_to_vcard_value(self.get_organisations()[0], output="text")
            showas_obj = self.vcard.add('x-abshowas')
            showas_obj.value = "COMPANY"

    def get_titles(self):
        titles = []
        for child in self.vcard.getChildren():
            if child.name == "TITLE":
                titles.append(self.vcard_value_to_string(child.value))
        return titles

    def add_title(self, title):
        title_obj = self.vcard.add('title')
        title_obj.value = self.string_to_vcard_value(title, output="text")

    def get_roles(self):
        roles = []
        for child in self.vcard.getChildren():
            if child.name == "ROLE":
                roles.append(self.vcard_value_to_string(child.value))
        return roles

    def add_role(self, role):
        role_obj = self.vcard.add('role')
        role_obj.value = self.string_to_vcard_value(role, output="text")

    def get_phone_numbers(self):
        phone_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "TEL":
                type = self.vcard_value_to_string(
                        self.get_type_for_vcard_object(child) or "voice")
                if phone_dict.get(type) is None:
                    phone_dict[type] = []
                phone_dict[type].append(self.vcard_value_to_string(child.value))
        return phone_dict

    def add_phone_number(self, type, number):
        standard_types, custom_types = self.parse_type_value(
                type, number, self.supported_phone_types)
        phone_obj = self.vcard.add('tel')
        phone_obj.value = number
        if standard_types != "":
            phone_obj.type_param = self.string_to_vcard_value(standard_types, output="list")
        if custom_types != "":
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
        email_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "EMAIL":
                type = self.vcard_value_to_string(
                        self.get_type_for_vcard_object(child) or "internet")
                if email_dict.get(type) is None:
                    email_dict[type] = []
                email_dict[type].append(self.vcard_value_to_string(child.value))
        return email_dict

    def add_email_address(self, type, address):
        standard_types, custom_types = self.parse_type_value(
                type, address, self.supported_email_types)
        email_obj = self.vcard.add('email')
        email_obj.value = address
        if standard_types != "":
            email_obj.type_param = self.string_to_vcard_value(standard_types, output="list")
        if custom_types != "":
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
        post_adr_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "ADR":
                type = self.vcard_value_to_string(
                        self.get_type_for_vcard_object(child) or "work")
                if post_adr_dict.get(type) is None:
                    post_adr_dict[type] = []
                post_adr_dict[type].append(
                        {
                            "box" : self.vcard_value_to_string(child.value.box),
                            "extended" : self.vcard_value_to_string(child.value.extended),
                            "street" : self.vcard_value_to_string(child.value.street),
                            "code" : self.vcard_value_to_string(child.value.code),
                            "city" : self.vcard_value_to_string(child.value.city),
                            "region" : self.vcard_value_to_string(child.value.region),
                            "country" : self.vcard_value_to_string(child.value.country)
                        })
        return post_adr_dict

    def get_formatted_post_addresses(self):
        formatted_post_adr_dict = {}
        for type, post_adr_list in self.get_post_addresses().items():
            formatted_post_adr_dict[type] = []
            for post_adr in post_adr_list:
                strings = []
                if post_adr.get("street") != "":
                    strings.append(post_adr.get("street"))
                if post_adr.get("box") != "" and post_adr.get("extended") != "":
                    strings.append("%s %s" % (post_adr.get("box"), post_adr.get("extended")))
                elif post_adr.get("box") != "":
                    strings.append(post_adr.get("box"))
                elif post_adr.get("extended") != "":
                    strings.append(post_adr.get("extended"))
                if post_adr.get("code") != "" and post_adr.get("city") != "":
                    strings.append("%s %s" % (post_adr.get("code"), post_adr.get("city")))
                elif post_adr.get("code") != "":
                    strings.append(post_adr.get("code"))
                elif post_adr.get("city") != "":
                    strings.append(post_adr.get("city"))
                if post_adr.get("region") != "" and post_adr.get("country") != "":
                    strings.append("%s, %s" % (post_adr.get("region"), post_adr.get("country")))
                elif post_adr.get("region") != "":
                    strings.append(post_adr.get("region"))
                elif post_adr.get("country") != "":
                    strings.append(post_adr.get("country"))
                formatted_post_adr_dict[type].append('\n'.join(strings))
        return formatted_post_adr_dict

    def add_post_address(self, type, box, extended, street, code, city, region, country):
        standard_types, custom_types = self.parse_type_value(
                type, "%s, %s" % (street, city), self.supported_address_types)
        adr_obj = self.vcard.add('adr')
        adr_obj.value = vobject.vcard.Address(
                box = self.string_to_vcard_value(box, output="list"),
                extended = self.string_to_vcard_value(extended, output="list"),
                street = self.string_to_vcard_value(street, output="list"),
                code = self.string_to_vcard_value(code, output="list"),
                city = self.string_to_vcard_value(city, output="list"),
                region = self.string_to_vcard_value(region, output="list"),
                country = self.string_to_vcard_value(country, output="list"))
        if standard_types != "":
            adr_obj.type_param = self.string_to_vcard_value(standard_types, output="list")
        if custom_types != "":
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
        category_list = []
        for child in self.vcard.getChildren():
            if child.name == "CATEGORIES":
                category_list.append(self.vcard_value_to_string(child.value))
        return category_list

    def add_category(self, categories):
        categories_obj = self.vcard.add('categories')
        categories_obj.value = self.string_to_vcard_value(categories, output="list")

    def get_nicknames(self):
        nicknames = []
        for child in self.vcard.getChildren():
            if child.name == "NICKNAME":
                nicknames.append(self.vcard_value_to_string(child.value))
        return nicknames

    def add_nickname(self, nick_name):
        nickname_obj = self.vcard.add('nickname')
        nickname_obj.value = self.string_to_vcard_value(nick_name, output="text")

    def get_notes(self):
        notes = []
        for child in self.vcard.getChildren():
            if child.name == "NOTE":
                notes.append(self.vcard_value_to_string(child.value))
        return notes

    def add_note(self, note):
        note_obj = self.vcard.add('note')
        note_obj.value = self.string_to_vcard_value(note, output="text")

    def get_jabber_ids(self):
        jabber_ids = []
        for child in self.vcard.getChildren():
            if child.name == "X-JABBER":
                jabber_ids.append(self.vcard_value_to_string(child.value))
        return jabber_ids

    def add_jabber_id(self, jabber_id):
        jabber_obj = self.vcard.add('x-jabber')
        jabber_obj.value = self.string_to_vcard_value(jabber_id, output="text")

    def get_skype_ids(self):
        skype_ids = []
        for child in self.vcard.getChildren():
            if child.name == "X-SKYPE":
                skype_ids.append(self.vcard_value_to_string(child.value))
        return skype_ids
        try:
            return self.vcard_value_to_string(self.vcard.x_skype.value)
        except AttributeError as e:
            return ""

    def add_skype_id(self, skype_id):
        skype_obj = self.vcard.add('x-skype')
        skype_obj.value = self.string_to_vcard_value(skype_id, output="text")

    def get_twitter_ids(self):
        twitter_ids = []
        for child in self.vcard.getChildren():
            if child.name == "X-TWITTER":
                twitter_ids.append(self.vcard_value_to_string(child.value))
        return twitter_ids

    def add_twitter_id(self, twitter_id):
        twitter_obj = self.vcard.add('x-twitter')
        twitter_obj.value = self.string_to_vcard_value(twitter_id, output="text")

    def get_webpages(self):
        urls = []
        for child in self.vcard.getChildren():
            if child.name == "URL":
                urls.append(self.vcard_value_to_string(child.value))
        return urls

    def add_webpage(self, webpage):
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

    def add_birthday(self, date):
        bday_obj = self.vcard.add('bday')
        bday_obj.value = "%.4d%.2d%.2d" % (date.year, date.month, date.day)


    #######################
    # object helper methods
    #######################

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
        else:
            if contact_data is None:
                raise ValueError("Error: Found no contact information")

        # check for available data
        # at least enter name or organisation
        if not bool(contact_data.get("First name")) \
                and not bool(contact_data.get("Last name")) \
                and not bool(contact_data.get("Organisation")):
            raise ValueError("Error: You must either enter a name or an organisation")

        # delete vcard version
        # the correct version is added automatically on saving again
        self.delete_vcard_object("VERSION")

        # update rev
        self.delete_vcard_object("REV")
        self.add_rev(datetime.datetime.now())

        # name
        if isinstance(contact_data.get("Prefix"), list) \
                or isinstance(contact_data.get("Prefix"), dict) \
                or isinstance(contact_data.get("First name"), list) \
                or isinstance(contact_data.get("First name"), dict) \
                or isinstance(contact_data.get("Additional"), list) \
                or isinstance(contact_data.get("Additional"), dict) \
                or isinstance(contact_data.get("Last name"), list) \
                or isinstance(contact_data.get("Last name"), dict) \
                or isinstance(contact_data.get("Suffix"), list) \
                or isinstance(contact_data.get("Suffix"), dict):
            raise ValueError("Error: Multiple entries for name fields are not allowed. Separate by comma instead.")
        # although the "n" attribute is not explisitely required by the vcard specification,
        # the vobject library throws an exception, if it doesn't exist
        # so add the name regardless if it's empty or not
        self.delete_vcard_object("FN")
        self.delete_vcard_object("N")
        self.add_name(
                contact_data.get("Prefix") or "",
                contact_data.get("First name") or "",
                contact_data.get("Additional") or "",
                contact_data.get("Last name") or "",
                contact_data.get("Suffix") or "")
        # nickname
        self.delete_vcard_object("NICKNAME")
        try:
            nickname_list = contact_data.get("Nickname")
            if not isinstance(nickname_list, list):
                nickname_list = [nickname_list]
            for nickname in sorted(nickname_list):
                if bool(nickname):
                    self.add_nickname(nickname)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # organisation
        self.delete_vcard_object("ORG")
        self.delete_vcard_object("X-ABSHOWAS")
        try:
            organisation_list = contact_data.get("Organisation")
            if not isinstance(organisation_list, list):
                organisation_list = [organisation_list]
            for organisation in sorted(organisation_list):
                if bool(organisation):
                    self.add_organisation(organisation)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass
        # role
        self.delete_vcard_object("ROLE")
        try:
            role_list = contact_data.get("Role")
            if not isinstance(role_list, list):
                role_list = [role_list]
            for role in sorted(role_list):
                if bool(role):
                    self.add_role(role)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass
        # title
        self.delete_vcard_object("TITLE")
        try:
            title_list = contact_data.get("Title")
            if not isinstance(title_list, list):
                title_list = [title_list]
            for title in sorted(title_list):
                if bool(title):
                    self.add_title(title)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # phone
        self.delete_vcard_object("TEL")
        try:
            for type, number_list in sorted(contact_data.get("Phone").items()):
                if not isinstance(number_list, list):
                    number_list = [number_list]
                for number in number_list:
                    if bool(number):
                        self.add_phone_number(type, number)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # email
        self.delete_vcard_object("EMAIL")
        try:
            for type, email_list in sorted(contact_data.get("Email").items()):
                if not isinstance(email_list, list):
                    email_list = [email_list]
                for email in email_list:
                    if bool(email):
                        self.add_email_address(type, email)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # post addresses
        self.delete_vcard_object("ADR")
        try:
            for type, post_adr_list in sorted(contact_data.get("Address").items()):
                if not isinstance(post_adr_list, list):
                    post_adr_list = [post_adr_list]
                for post_adr in post_adr_list:
                    try:
                        number_of_non_empty_address_values = 0
                        for key, value in post_adr.items():
                            if key in ["Box", "Extended", "Street", "Code", "City", "Region", "Country"] \
                                    and bool(value):
                                number_of_non_empty_address_values += 1
                        if number_of_non_empty_address_values > 0:
                            self.add_post_address(
                                    type,
                                    post_adr.get("Box") or "",
                                    post_adr.get("Extended") or "",
                                    post_adr.get("Street") or "",
                                    post_adr.get("Code") or "",
                                    post_adr.get("City") or "",
                                    post_adr.get("Region") or "",
                                    post_adr.get("Country") or "")
                    except TypeError as e:
                        raise ValueError("Error during parsing of address with type %s" % type)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # categories
        self.delete_vcard_object("CATEGORIES")
        try:
            category_list = contact_data.get("Categories")
            if not isinstance(category_list, list):
                category_list = [category_list]
            for category in sorted(category_list):
                if bool(category):
                    self.add_category(category)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # jabber
        self.delete_vcard_object("X-JABBER")
        try:
            jabber_list = contact_data.get("Jabber")
            if not isinstance(jabber_list, list):
                jabber_list = [jabber_list]
            for jabber_id in sorted(jabber_list):
                if bool(jabber_id):
                    self.add_jabber_id(jabber_id)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # skype
        self.delete_vcard_object("X-SKYPE")
        try:
            skype_list = contact_data.get("Skype")
            if not isinstance(skype_list, list):
                skype_list = [skype_list]
            for skype_id in sorted(skype_list):
                if bool(skype_id):
                    self.add_skype_id(skype_id)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # twitter
        self.delete_vcard_object("X-TWITTER")
        try:
            twitter_list = contact_data.get("Twitter")
            if not isinstance(twitter_list, list):
                twitter_list = [twitter_list]
            for twitter_id in sorted(twitter_list):
                if bool(twitter_id):
                    self.add_twitter_id(twitter_id)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # urls
        self.delete_vcard_object("URL")
        try:
            url_list = contact_data.get("Webpage")
            if not isinstance(url_list, list):
                url_list = [url_list]
            for url in sorted(url_list):
                if bool(url):
                    self.add_webpage(url)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass

        # birthday
        self.delete_vcard_object("BDAY")
        if bool(contact_data.get("Birthday")):
            if isinstance(contact_data.get("Birthday"), list) \
                    or isinstance(contact_data.get("Birthday"), dict):
                raise ValueError("Error: Multiple birthday entries are not allowed")
            supported_date_formats = ["%d-%m-%Y", "%Y-%m-%d"]
            for date_format in supported_date_formats:
                try:
                    self.add_birthday(
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

        # notes
        self.delete_vcard_object("NOTE")
        try:
            note_list = contact_data.get("Note")
            if not isinstance(note_list, list):
                note_list = [note_list]
            for note in sorted(note_list):
                if bool(note):
                    self.add_note(note)
        except AttributeError as e:
            pass
        except KeyError as e:
            pass


    def get_template(self):
        strings = []
        for line in helpers.get_new_contact_template().splitlines():
            if line.startswith("#"):
                strings.append(line)
            elif line == "":
                strings.append(line)

            elif line.lower().startswith("prefix"):
                strings.append("Prefix     : %s" % \
                        helpers.format_yaml_values(self.get_name_prefix(), 4, "|"))
            elif line.lower().startswith("first name"):
                strings.append("First name : %s" % \
                        helpers.format_yaml_values(self.get_first_name(), 4, "|"))
            elif line.lower().startswith("additional"):
                strings.append("Additional : %s" % \
                        helpers.format_yaml_values(self.get_additional_name(), 4, "|"))
            elif line.lower().startswith("last name"):
                strings.append("Last name  : %s" % \
                        helpers.format_yaml_values(self.get_last_name(), 4, "|"))
            elif line.lower().startswith("suffix"):
                strings.append("Suffix     : %s" % \
                        helpers.format_yaml_values(self.get_name_suffix(), 4, "|"))
            elif line.lower().startswith("nickname"):
                if len(self.get_nicknames()) == 0:
                    strings.append("Nickname : ")
                elif len(self.get_nicknames()) == 1:
                    strings.append("Nickname : %s" \
                            % helpers.format_yaml_values(self.get_nicknames()[0], 4, "|"))
                else:
                    strings.append("Nickname : ")
                    for nickname in sorted(self.get_nicknames()):
                        strings.append("    - %s" % helpers.format_yaml_values(nickname, 8, "|"))

            elif line.lower().startswith("organisation"):
                if len(self.get_organisations()) == 0:
                    strings.append("Organisation : ")
                elif len(self.get_organisations()) == 1:
                    strings.append("Organisation : %s" \
                            % helpers.format_yaml_values(self.get_organisations()[0], 4, "|"))
                else:
                    strings.append("Organisation : ")
                    for organisation in sorted(self.get_organisations()):
                        strings.append("    - %s" % helpers.format_yaml_values(organisation, 8, "|"))
            elif line.lower().startswith("title"):
                if len(self.get_titles()) == 0:
                    strings.append("Title        : ")
                elif len(self.get_titles()) == 1:
                    strings.append("Title        : %s" \
                            % helpers.format_yaml_values(self.get_titles()[0], 4, "|"))
                else:
                    strings.append("Title        : ")
                    for title in sorted(self.get_titles()):
                        strings.append("    - %s" % helpers.format_yaml_values(title, 8, "|"))
            elif line.lower().startswith("role"):
                if len(self.get_roles()) == 0:
                    strings.append("Role         : ")
                elif len(self.get_roles()) == 1:
                    strings.append("Role         : %s" \
                            % helpers.format_yaml_values(self.get_roles()[0], 4, "|"))
                else:
                    strings.append("Role         : ")
                    for role in sorted(self.get_roles()):
                        strings.append("    - %s" % helpers.format_yaml_values(role, 8, "|"))

            elif line.lower().startswith("phone"):
                strings.append("Phone :")
                if len(self.get_phone_numbers().keys()) == 0:
                    strings.append("    cell : ")
                    strings.append("    work : ")
                else:
                    for type, number_list in sorted(self.get_phone_numbers().items(), key=lambda k: k[0].lower()):
                        if len(number_list) == 1:
                            strings.append("    %s : %s" \
                                    % (type, helpers.format_yaml_values(number_list[0], 8, "|")))
                        else:
                            strings.append("    %s:" % type)
                            for number in sorted(number_list):
                                strings.append("        - %s" \
                                        % helpers.format_yaml_values(number, 12, "|"))

            elif line.lower().startswith("email"):
                strings.append("Email :")
                if len(self.get_email_addresses().keys()) == 0:
                    strings.append("    home : ")
                    strings.append("    work : ")
                else:
                    for type, email_list in sorted(self.get_email_addresses().items(), key=lambda k: k[0].lower()):
                        if len(email_list) == 1:
                            strings.append("    %s : %s" \
                                    % (type, helpers.format_yaml_values(email_list[0], 8, "|")))
                        else:
                            strings.append("    %s:" % type)
                            for email in sorted(email_list):
                                strings.append("        - %s" \
                                        % helpers.format_yaml_values(email, 12, "|"))

            elif line.lower().startswith("address"):
                strings.append("Address :")
                if len(self.get_post_addresses().keys()) == 0:
                    strings.append("    home :")
                    strings.append("        Box      : ")
                    strings.append("        Extended : ")
                    strings.append("        Street   : ")
                    strings.append("        Code     : ")
                    strings.append("        City     : ")
                    strings.append("        Region   : ")
                    strings.append("        Country  : ")
                else:
                    for type, post_adr_list in sorted(self.get_post_addresses().items(), key=lambda k: k[0].lower()):
                        strings.append("    %s:" % type)
                        if len(post_adr_list) == 1:
                            post_adr = post_adr_list[0]
                            strings.append("        Box      : %s" \
                                    % helpers.format_yaml_values(post_adr.get("box"), 12, "|"))
                            strings.append("        Extended : %s" \
                                    % helpers.format_yaml_values(post_adr.get("extended"), 12, "|"))
                            strings.append("        Street   : %s" \
                                    % helpers.format_yaml_values(post_adr.get("street"), 12, "|"))
                            strings.append("        Code     : %s" \
                                    % helpers.format_yaml_values(post_adr.get("code"), 12, "|"))
                            strings.append("        City     : %s" \
                                    % helpers.format_yaml_values(post_adr.get("city"), 12, "|"))
                            strings.append("        Region   : %s" \
                                    % helpers.format_yaml_values(post_adr.get("region"), 12, "|"))
                            strings.append("        Country  : %s" \
                                    % helpers.format_yaml_values(post_adr.get("country"), 12, "|"))
                        else:
                            for post_adr in sorted(post_adr_list):
                                strings.append("        -")
                                strings.append("            Box      : %s" \
                                        % helpers.format_yaml_values(post_adr.get("box"), 16, "|"))
                                strings.append("            Extended : %s" \
                                        % helpers.format_yaml_values(post_adr.get("extended"), 16, "|"))
                                strings.append("            Street   : %s" \
                                        % helpers.format_yaml_values(post_adr.get("street"), 16, "|"))
                                strings.append("            Code     : %s" \
                                        % helpers.format_yaml_values(post_adr.get("code"), 16, "|"))
                                strings.append("            City     : %s" \
                                        % helpers.format_yaml_values(post_adr.get("city"), 16, "|"))
                                strings.append("            Region   : %s" \
                                        % helpers.format_yaml_values(post_adr.get("region"), 16, "|"))
                                strings.append("            Country  : %s" \
                                        % helpers.format_yaml_values(post_adr.get("country"), 16, "|"))

            elif line.lower().startswith("jabber"):
                if len(self.get_jabber_ids()) == 0:
                    strings.append("Jabber  : ")
                elif len(self.get_jabber_ids()) == 1:
                    strings.append("Jabber  : %s" \
                            % helpers.format_yaml_values(self.get_jabber_ids()[0], 4, "|"))
                else:
                    strings.append("Jabber  : ")
                    for jabber_id in sorted(self.get_jabber_ids()):
                        strings.append("    - %s" % helpers.format_yaml_values(jabber_id, 8, "|"))
            elif line.lower().startswith("skype"):
                if len(self.get_skype_ids()) == 0:
                    strings.append("Skype   : ")
                elif len(self.get_skype_ids()) == 1:
                    strings.append("Skype   : %s" \
                            % helpers.format_yaml_values(self.get_skype_ids()[0], 4, "|"))
                else:
                    strings.append("Skype   : ")
                    for skype_id in sorted(self.get_skype_ids()):
                        strings.append("    - %s" % helpers.format_yaml_values(skype_id, 8, "|"))
            elif line.lower().startswith("twitter"):
                if len(self.get_twitter_ids()) == 0:
                    strings.append("Twitter : ")
                elif len(self.get_twitter_ids()) == 1:
                    strings.append("Twitter : %s" \
                            % helpers.format_yaml_values(self.get_twitter_ids()[0], 4, "|"))
                else:
                    strings.append("Twitter : ")
                    for twitter_id in sorted(self.get_twitter_ids()):
                        strings.append("    - %s" % helpers.format_yaml_values(twitter_id, 8, "|"))
            elif line.lower().startswith("webpage"):
                if len(self.get_webpages()) == 0:
                    strings.append("Webpage : ")
                elif len(self.get_webpages()) == 1:
                    strings.append("Webpage : %s" \
                            % helpers.format_yaml_values(self.get_webpages()[0], 4, "|"))
                else:
                    strings.append("Webpage : ")
                    for webpage in sorted(self.get_webpages()):
                        strings.append("    - %s" % helpers.format_yaml_values(webpage, 8, "|"))

            elif line.lower().startswith("birthday"):
                date = self.get_birthday()
                if not date:
                    strings.append("Birthday : ")
                else:
                    strings.append("Birthday : %.2d.%.2d.%.4d" % (date.day, date.month, date.year))
            elif line.lower().startswith("categories"):
                if len(self.get_categories()) == 0:
                    strings.append("Categories : ")
                elif len(self.get_categories()) == 1:
                    strings.append("Categories : %s" \
                            % helpers.format_yaml_values(self.get_categories()[0], 4, "|"))
                else:
                    strings.append("Categories : ")
                    for category in sorted(self.get_categories()):
                        strings.append("    - %s" % helpers.format_yaml_values(category, 8, "|"))
            elif line.lower().startswith("note"):
                if len(self.get_notes()) == 0:
                    strings.append("Note : ")
                elif len(self.get_notes()) == 1:
                    strings.append("Note : %s" \
                            % helpers.format_yaml_values(self.get_notes()[0], 4, "|"))
                else:
                    strings.append("Note : ")
                    for note in sorted(self.get_notes()):
                        strings.append("    - %s" % helpers.format_yaml_values(note, 8, "|"))
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
        # organisation
        if len(self.get_organisations()) > 0:
            if len(self.get_organisations()) == 1:
                strings.append("Organisation: %s" \
                        % helpers.format_yaml_values(self.get_organisations()[0], 4, ""))
            else:
                strings.append("Organisations:")
                for organisation in sorted(self.get_organisations()):
                    strings.append("    - %s" % helpers.format_yaml_values(organisation, 8, ""))

        # person related information
        if self.get_birthday() != None \
                or len(self.get_nicknames()) > 0 \
                or len(self.get_roles()) > 0 \
                or len(self.get_titles()) > 0:
            strings.append("General:")
            if self.get_birthday() != None:
                date = self.get_birthday()
                strings.append("    Birthday: %.2d.%.2d.%.4d" % (date.day, date.month, date.year))
            if len(self.get_nicknames()) > 0:
                if len(self.get_nicknames()) == 1:
                    strings.append("    Nickname: %s" \
                            % helpers.format_yaml_values(self.get_nicknames()[0], 8, ""))
                else:
                    strings.append("    Nicknames:")
                    for nickname in sorted(self.get_nicknames()):
                        strings.append("        - %s" % helpers.format_yaml_values(nickname, 12, ""))
            if len(self.get_roles()) > 0:
                if len(self.get_roles()) == 1:
                    strings.append("    Role: %s" \
                            % helpers.format_yaml_values(self.get_roles()[0], 8, ""))
                else:
                    strings.append("    Roles:")
                    for role in sorted(self.get_roles()):
                        strings.append("        - %s" % helpers.format_yaml_values(role, 12, ""))
            if len(self.get_titles()) > 0:
                if len(self.get_titles()) == 1:
                    strings.append("    Title: %s" \
                            % helpers.format_yaml_values(self.get_titles()[0], 8, ""))
                else:
                    strings.append("    Titles:")
                    for title in sorted(self.get_titles()):
                        strings.append("        - %s" % helpers.format_yaml_values(title, 12, ""))

        # phone numbers
        if len(self.get_phone_numbers().keys()) > 0:
            strings.append("Phone")
            for type, number_list in sorted(self.get_phone_numbers().items(), key=lambda k: k[0].lower()):
                if len(number_list) == 1:
                    strings.append("    %s: %s" \
                            % (type, helpers.format_yaml_values(number_list[0], 8, "")))
                else:
                    strings.append("    %s:" % type)
                    for number in sorted(number_list):
                        strings.append("        - %s" \
                                % helpers.format_yaml_values(number, 12, ""))

        # email addresses
        if len(self.get_email_addresses().keys()) > 0:
            strings.append("E-Mail")
            for type, email_list in sorted(self.get_email_addresses().items(), key=lambda k: k[0].lower()):
                if len(email_list) == 1:
                    strings.append("    %s: %s" \
                            % (type, helpers.format_yaml_values(email_list[0], 8, "")))
                else:
                    strings.append("    %s:" % type)
                    for email in sorted(email_list):
                        strings.append("        - %s" \
                                % helpers.format_yaml_values(email, 12, ""))

        # post addresses
        if len(self.get_post_addresses().keys()) > 0:
            strings.append("Address")
            for type, post_adr_list in sorted(self.get_formatted_post_addresses().items(), key=lambda k: k[0].lower()):
                if len(post_adr_list) == 1:
                    strings.append("    %s: %s" \
                            % (type, helpers.format_yaml_values(post_adr_list[0], 8, "")))
                else:
                    strings.append("    %s:" % type)
                    for post_adr in sorted(post_adr_list):
                        strings.append("        - %s" \
                                % helpers.format_yaml_values(post_adr, 12, ""))

        # im and webpages
        if len(self.get_jabber_ids()) > 0 \
                or len(self.get_skype_ids()) > 0 \
                or len(self.get_twitter_ids()) > 0 \
                or len(self.get_webpages()) > 0:
            strings.append("Instant messaging and social networks")
            if len(self.get_jabber_ids()) > 0:
                if len(self.get_jabber_ids()) == 1:
                    strings.append("    Jabber: %s" \
                            % helpers.format_yaml_values(self.get_jabber_ids()[0], 8, ""))
                else:
                    strings.append("    Jabber:")
                    for jabber_id in sorted(self.get_jabber_ids()):
                        strings.append("        - %s" % helpers.format_yaml_values(jabber_id, 12, ""))
            if len(self.get_skype_ids()) > 0:
                if len(self.get_skype_ids()) == 1:
                    strings.append("    Skype: %s" \
                            % helpers.format_yaml_values(self.get_skype_ids()[0], 8, ""))
                else:
                    strings.append("    Skype:")
                    for skype_id in sorted(self.get_skype_ids()):
                        strings.append("        - %s" % helpers.format_yaml_values(skype_id, 12, ""))
            if len(self.get_twitter_ids()) > 0:
                if len(self.get_twitter_ids()) == 1:
                    strings.append("    Twitter: %s" \
                            % helpers.format_yaml_values(self.get_twitter_ids()[0], 8, ""))
                else:
                    strings.append("    Twitter:")
                    for twitter_id in sorted(self.get_twitter_ids()):
                        strings.append("        - %s" % helpers.format_yaml_values(twitter_id, 12, ""))
            if len(self.get_webpages()) > 0:
                if len(self.get_webpages()) == 1:
                    strings.append("    Webpage: %s" \
                            % helpers.format_yaml_values(self.get_webpages()[0], 8, ""))
                else:
                    strings.append("    Webpages:")
                    for webpage in sorted(self.get_webpages()):
                        strings.append("        - %s" % helpers.format_yaml_values(webpage, 12, ""))

        # misc stuff
        if show_address_book \
                or len(self.get_categories()) > 0 \
                or len(self.get_notes()) > 0 \
                or (show_uid and self.get_uid() != ""):
            strings.append("Miscellaneous")
            if show_address_book:
                strings.append("    Address book: %s" % self.address_book.get_name())
            if len(self.get_categories()) > 0:
                if len(self.get_categories()) == 1:
                    strings.append("    Categories: %s" \
                            % helpers.format_yaml_values(self.get_categories()[0], 8, ""))
                else:
                    strings.append("    Categories:")
                    for category in sorted(self.get_categories()):
                        strings.append("        - %s" % helpers.format_yaml_values(category, 12, ""))
            if len(self.get_notes()) > 0:
                if len(self.get_notes()) == 1:
                    strings.append("    Note: %s" \
                            % helpers.format_yaml_values(self.get_notes()[0], 8, ""))
                else:
                    strings.append("    Notes:")
                    for note in sorted(self.get_notes()):
                        strings.append("        - %s" % helpers.format_yaml_values(note, 12, ""))
            if show_uid and self.get_uid() != "":
                strings.append("    UID: %s" % helpers.format_yaml_values(self.get_uid(), 8, ""))
        return '\n'.join(strings)


    def write_to_file(self, overwrite=False):
        try:
            with atomic_write(self.filename, overwrite=overwrite) as f:
                f.write(self.vcard.serialize())
        except vobject.base.ValidateError as e:
            print("Error: Vcard is not valid.\n%s" % e)
            sys.exit(4)
        except IOError as e:
            print("Error: Can't write\n%s" % e)
            sys.exit(4)
        except OSError as e:
            print("Error: vcard with the file name %s already exists\n%s" \
                    % (os.path.basename(self.filename), e))
            sys.exit(4)

    def delete_vcard_object(self, object_name):
        # first collect all vcard items, which should be removed
        to_be_removed = []
        for child in self.vcard.getChildren():
            if child.name == object_name:
                if child.group:
                    for label in self.vcard.getChildren():
                        if label.name == "X-ABLABEL" and label.group == child.group:
                            to_be_removed.append(label)
                to_be_removed.append(child)
        # then delete them one by one
        for item in to_be_removed:
            self.vcard.remove(item)

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
        type_list = []
        # try to find label group for custom value type
        if object.group:
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group == object.group:
                    for custom_type in label.value.split(","):
                        type_list.append(custom_type)
        # then load type from params dict
        standard_types = object.params.get("TYPE")
        if standard_types is not None:
            if not isinstance(standard_types, list):
                standard_types = [standard_types]
            for type in standard_types:
                if not type.lower().startswith("x-"):
                    type_list.append(type)
                elif type[2:] not in type_list:
                    type_list.append(type[2:])
        if len(type_list) > 0:
            return sorted(type_list)
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
            if type != "":
                if type.lower() in supported_types:
                    standard_types.append(type)
                else:
                    if type.lower().startswith("x-"):
                        custom_types.append(type[2:])
                        standard_types.append(type)
                    else:
                        custom_types.append(type)
                        standard_types.append("X-%s" % type)
        # throw an exception, if no label is given
        if len(custom_types) == 0 and len(standard_types) == 0:
            raise ValueError("Error: Missing type for %s" % value)
        return (','.join(standard_types), ','.join(custom_types))

