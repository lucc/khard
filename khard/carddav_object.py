# -*- coding: utf-8 -*-

# contact object class
# vcard version 3.0: https://tools.ietf.org/html/rfc2426
# vcard version 4.0: https://tools.ietf.org/html/rfc6350

import datetime
import locale
import os
import re
import sys

from atomicwrites import atomic_write
import vobject

import ruamel.yaml
from ruamel.yaml import YAML

from . import helpers
from .object_type import ObjectType


class CarddavObject:

    # vcard v3.0 supports the following type values
    phone_types_v3 = ("bbs", "car", "cell", "fax", "home", "isdn", "msg",
                      "modem", "pager", "pcs", "video", "voice", "work")
    email_types_v3 = ("home", "internet", "work", "x400")
    address_types_v3 = ("dom", "intl", "home", "parcel", "postal", "work")
    # vcard v4.0 supports the following type values
    phone_types_v4 = ("text", "voice", "fax", "cell", "video", "pager",
                      "textphone", "home", "work")
    email_types_v4 = ("home", "internet", "work")
    address_types_v4 = ("home", "work")

    def __init__(self, address_book, filename, supported_private_objects,
                 vcard_version, localize_dates):
        """Initialize the vcard object.

        :param address_book: a reference to the address book where this vcard
            is stored
        :type address_book: khard.address_book.AddressBook
        :param filename: the path to the file where this vcard is stored or
            None
        :type filename: str or NoneType
        :param supported_private_objects: the list of private property names
            that will be loaded from the actual vcard and represented in this
            pobject
        :type supported_private_objects: list(str)
        :param vcard_version: str or None
        :type vcard_version: str
        :param localize_dates: should the formatted output of anniversary and
            birthday be localized or should the isoformat be used instead
        :type localize_dates: bool

        """
        self.vcard = None
        self.address_book = address_book
        self.filename = filename
        self.supported_private_objects = supported_private_objects
        self.localize_dates = localize_dates

        # load vcard
        if self.filename is None:
            # create new vcard object
            self.vcard = vobject.vCard()
            # add uid
            self.add_uid(helpers.get_random_uid())
            # use uid for vcard filename
            self.filename = os.path.join(address_book.path,
                                         self.get_uid() + ".vcf")
            # add preferred vcard version
            self._add_version(vcard_version)

        else:
            # create vcard from .vcf file
            with open(self.filename, "r") as file:
                contents = file.read()
            # create vcard object
            try:
                self.vcard = vobject.readOne(contents)
            except Exception:
                # if creation fails, try to repair some vcard attributes
                self.vcard = vobject.readOne(self._filter_invalid_tags(contents))

    #######################################
    # factory methods to create new contact
    #######################################

    @classmethod
    def new_contact(cls, address_book, supported_private_objects, version,
            localize_dates):
        """Use this to create a new and empty contact."""
        return cls(address_book, None, supported_private_objects, version,
                localize_dates)

    @classmethod
    def from_file(cls, address_book, filename, supported_private_objects,
            localize_dates):
        """
        Use this if you want to create a new contact from an existing .vcf
        file.
        """
        return cls(address_book, filename, supported_private_objects, None,
                localize_dates)

    @classmethod
    def from_user_input(cls, address_book, user_input,
                        supported_private_objects, version, localize_dates):
        """Use this if you want to create a new contact from user input."""
        contact = cls(address_book, None, supported_private_objects, version,
                localize_dates)
        contact._process_user_input(user_input)
        return contact

    @classmethod
    def from_existing_contact_with_new_user_input(cls, contact, user_input,
            localize_dates):
        """
        Use this if you want to clone an existing contact and  replace its data
        with new user input in one step.
        """
        contact = cls(contact.address_book, contact.filename,
                      contact.supported_private_objects, None, localize_dates)
        contact._process_user_input(user_input)
        return contact

    ######################################
    # overwrite some default class methods
    ######################################

    def __str__(self):
        return self.get_full_name()

    def __eq__(self, other):
        return isinstance(other, CarddavObject) and \
            self.print_vcard(show_address_book=False, show_uid=False) == \
            other.print_vcard(show_address_book=False, show_uid=False)

    def __ne__(self, other):
        return not self == other

    #####################
    # getters and setters
    #####################

    def _get_rev(self):
        """
        :rtype: str
        """
        try:
            return self.vcard.rev.value
        except AttributeError:
            return ""

    def _add_rev(self, dt):
        rev_obj = self.vcard.add('rev')
        rev_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2dZ" % (
            dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

    def get_uid(self):
        """
        :rtype: str
        """
        try:
            return self.vcard.uid.value
        except AttributeError:
            return ""

    def add_uid(self, uid):
        uid_obj = self.vcard.add('uid')
        uid_obj.value = helpers.convert_to_vcard(
            "uid", uid, ObjectType.string)

    def get_version(self):
        """
        :rtype: str
        """
        try:
            return self.vcard.version.value
        except AttributeError:
            return ""

    def _add_version(self, vcard_version):
        version_obj = self.vcard.add('version')
        version_obj.value = helpers.convert_to_vcard(
            "version", vcard_version, ObjectType.string)

    def _get_name_prefixes(self):
        """
        :rtype: list(str)
        """
        try:
            prefix_list = self.vcard.n.value.prefix
        except AttributeError:
            prefix_list = []
        else:
            # check if list only contains an empty string ([""])
            if not ''.join(prefix_list):
                prefix_list = []
        return prefix_list if isinstance(prefix_list, list) else [prefix_list]

    def _get_first_names(self):
        """
        :rtype: list(str)
        """
        try:
            first_name_list = self.vcard.n.value.given
        except AttributeError:
            first_name_list = []
        else:
            # check if list only contains an empty string ([""])
            if not ''.join(first_name_list):
                first_name_list = []
        return first_name_list if isinstance(first_name_list, list) \
            else [first_name_list]

    def _get_additional_names(self):
        """
        :rtype: list(str)
        """
        try:
            additional_name_list = self.vcard.n.value.additional
        except AttributeError:
            additional_name_list = []
        else:
            # check if list only contains an empty string ([""])
            if not ''.join(additional_name_list):
                additional_name_list = []
        return additional_name_list if isinstance(additional_name_list, list) \
            else [additional_name_list]

    def _get_last_names(self):
        """
        :rtype: list(str)
        """
        try:
            last_name_list = self.vcard.n.value.family
        except AttributeError:
            last_name_list = []
        else:
            # check if list only contains an empty string ([""])
            if not ''.join(last_name_list):
                last_name_list = []
        return last_name_list if isinstance(last_name_list, list) \
            else [last_name_list]

    def _get_name_suffixes(self):
        """
        :rtype: list(str)
        """
        try:
            suffix_list = self.vcard.n.value.suffix
        except AttributeError:
            suffix_list = []
        else:
            # check if list only contains an empty string ([""])
            if not ''.join(suffix_list):
                suffix_list = []
        return suffix_list if isinstance(suffix_list, list) else [suffix_list]

    def get_full_name(self):
        """
        :rtype: str
        """
        try:
            return self.vcard.fn.value
        except AttributeError:
            return ""

    def get_first_name_last_name(self):
        """
        :rtype: str
        """
        names = []
        if self._get_first_names():
            names += self._get_first_names()
        if self._get_additional_names():
            names += self._get_additional_names()
        if self._get_last_names():
            names += self._get_last_names()
        if names:
            return helpers.list_to_string(names, " ")
        else:
            return self.get_full_name()

    def get_last_name_first_name(self):
        """
        :rtype: str
        """
        last_names = []
        if self._get_last_names():
            last_names += self._get_last_names()
        first_and_additional_names = []
        if self._get_first_names():
            first_and_additional_names += self._get_first_names()
        if self._get_additional_names():
            first_and_additional_names += self._get_additional_names()
        if last_names and first_and_additional_names:
            return "%s, %s" % (
                helpers.list_to_string(last_names, " "),
                helpers.list_to_string(first_and_additional_names, " "))
        elif last_names:
            return helpers.list_to_string(last_names, " ")
        elif first_and_additional_names:
            return helpers.list_to_string(first_and_additional_names, " ")
        else:
            return self.get_full_name()

    def _add_name(self, prefix, first_name, additional_name, last_name,
                  suffix):
        # n
        name_obj = self.vcard.add('n')
        name_obj.value = vobject.vcard.Name(
            prefix=helpers.convert_to_vcard(
                "name prefix", prefix, ObjectType.string_or_list_with_strings),
            given=helpers.convert_to_vcard(
                "first name", first_name,
                ObjectType.string_or_list_with_strings),
            additional=helpers.convert_to_vcard(
                "additional name", additional_name,
                ObjectType.string_or_list_with_strings),
            family=helpers.convert_to_vcard(
                "last name", last_name,
                ObjectType.string_or_list_with_strings),
            suffix=helpers.convert_to_vcard(
                "name suffix", suffix, ObjectType.string_or_list_with_strings))
        # fn
        if not self.vcard.getChildValue("fn") and (self._get_first_names() or
                                                   self._get_last_names()):
            names = []
            if self._get_name_prefixes():
                names += self._get_name_prefixes()
            if self._get_first_names():
                names += self._get_first_names()
            if self._get_last_names():
                names += self._get_last_names()
            if self._get_name_suffixes():
                names += self._get_name_suffixes()
            name_obj = self.vcard.add('fn')
            name_obj.value = helpers.list_to_string(names, " ")

    def _get_organisations(self):
        """
        :returns: list of organisations, sorted alphabetically
        :rtype: list(list(str))
        """
        organisations = []
        for child in self.vcard.getChildren():
            if child.name == "ORG":
                organisations.append(child.value)
        return sorted(organisations)

    def _add_organisation(self, organisation):
        org_obj = self.vcard.add('org')
        org_obj.value = helpers.convert_to_vcard(
            "organisation", organisation, ObjectType.list_with_strings)
        # check if fn attribute is already present
        if not self.vcard.getChildValue("fn") \
                and self._get_organisations():
            # if not, set fn to organisation name
            org_value = helpers.list_to_string(self._get_organisations()[0],
                                               ", ")
            name_obj = self.vcard.add('fn')
            name_obj.value = org_value.replace("\n", " ").replace("\\", "")
            showas_obj = self.vcard.add('x-abshowas')
            showas_obj.value = "COMPANY"

    def _get_titles(self):
        """
        :rtype: list(list(str))
        """
        titles = []
        for child in self.vcard.getChildren():
            if child.name == "TITLE":
                titles.append(child.value)
        return sorted(titles)

    def _add_title(self, title):
        title_obj = self.vcard.add('title')
        title_obj.value = helpers.convert_to_vcard("title", title,
                                                   ObjectType.string)

    def _get_roles(self):
        """
        :rtype: list(list(str))
        """
        roles = []
        for child in self.vcard.getChildren():
            if child.name == "ROLE":
                roles.append(child.value)
        return sorted(roles)

    def _add_role(self, role):
        role_obj = self.vcard.add('role')
        role_obj.value = helpers.convert_to_vcard("role", role,
                                                  ObjectType.string)

    def get_phone_numbers(self):
        """
        : returns: dict of type and phone number list
        :rtype: dict(str, list(str))
        """
        phone_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "TEL":
                type = helpers.list_to_string(
                    self._get_types_for_vcard_object(child, "voice"), ", ")
                if phone_dict.get(type) is None:
                    phone_dict[type] = []
                try:
                    # detect uri
                    if child.params.get("VALUE")[0] == "uri":
                        phone_dict[type].append(child.value.split(":")[1])
                except (IndexError, TypeError):
                    phone_dict[type].append(child.value)
        # sort phone number lists
        for number_list in phone_dict.values():
            number_list.sort()
        return phone_dict

    def _add_phone_number(self, type, number):
        standard_types, custom_types, pref = self._parse_type_value(
            helpers.string_to_list(type, ","), number, self.phone_types_v4 if
            self.get_version() == "4.0" else self.phone_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for phone number " + number +
                             " is missing.")
        elif len(custom_types) > 1:
            raise ValueError("Error: phone number " + number + " got more "
                             "than one custom label: " +
                             helpers.list_to_string(custom_types, ", "))
        else:
            phone_obj = self.vcard.add('tel')
            if self.get_version() == "4.0":
                phone_obj.value = "tel:%s" % helpers.convert_to_vcard(
                    "phone number", number, ObjectType.string)
                phone_obj.params['VALUE'] = ["uri"]
                if pref > 0:
                    phone_obj.params['PREF'] = str(pref)
            else:
                phone_obj.value = helpers.convert_to_vcard(
                    "phone number", number, ObjectType.string)
                if pref > 0:
                    standard_types.append("pref")
            if standard_types:
                phone_obj.params['TYPE'] = standard_types
            if custom_types:
                number_of_custom_phone_number_labels = 0
                for label in self.vcard.getChildren():
                    if label.name == "X-ABLABEL" \
                            and label.group.startswith("itemtel"):
                        number_of_custom_phone_number_labels += 1
                group_name = "itemtel%d" % (
                    number_of_custom_phone_number_labels+1)
                phone_obj.group = group_name
                label_obj = self.vcard.add('x-ablabel')
                label_obj.group = group_name
                label_obj.value = custom_types[0]

    def get_email_addresses(self):
        """
        : returns: dict of type and email address list
        :rtype: dict(str, list(str))
        """
        email_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "EMAIL":
                type = helpers.list_to_string(
                    self._get_types_for_vcard_object(child, "internet"), ", ")
                if email_dict.get(type) is None:
                    email_dict[type] = []
                email_dict[type].append(child.value)
        # sort email address lists
        for email_list in email_dict.values():
            email_list.sort()
        return email_dict

    def add_email_address(self, type, address):
        standard_types, custom_types, pref = self._parse_type_value(
            helpers.string_to_list(type, ","), address, self.email_types_v4 if
            self.get_version() == "4.0" else self.email_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for email address " + address +
                             " is missing.")
        elif len(custom_types) > 1:
            raise ValueError("Error: email address " + address + " got more "
                             "than one custom label: " +
                             helpers.list_to_string(custom_types, ", "))
        else:
            email_obj = self.vcard.add('email')
            email_obj.value = helpers.convert_to_vcard(
                "email address", address, ObjectType.string)
            if self.get_version() == "4.0":
                if pref > 0:
                    email_obj.params['PREF'] = str(pref)
            else:
                if pref > 0:
                    standard_types.append("pref")
            if standard_types:
                email_obj.params['TYPE'] = standard_types
            if custom_types:
                number_of_custom_email_labels = 0
                for label in self.vcard.getChildren():
                    if label.name == "X-ABLABEL" \
                            and label.group.startswith("itememail"):
                        number_of_custom_email_labels += 1
                group_name = "itememail%d" % (number_of_custom_email_labels+1)
                email_obj.group = group_name
                label_obj = self.vcard.add('x-ablabel')
                label_obj.group = group_name
                label_obj.value = custom_types[0]

    def _get_post_addresses(self):
        """
        : returns: dict of type and post address list
        :rtype: dict(str, list(dict(str,list|str)))
        """
        post_adr_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "ADR":
                type = helpers.list_to_string(
                    self._get_types_for_vcard_object(child, "home"), ", ")
                if post_adr_dict.get(type) is None:
                    post_adr_dict[type] = []
                post_adr_dict[type].append(
                    {
                        "box": child.value.box,
                        "extended": child.value.extended,
                        "street": child.value.street,
                        "code": child.value.code,
                        "city": child.value.city,
                        "region": child.value.region,
                        "country": child.value.country
                    })
        # sort post address lists
        for post_adr_list in post_adr_dict.values():
            post_adr_list.sort(key=lambda x: (
                helpers.list_to_string(x['city'], " ").lower(),
                helpers.list_to_string(x['street'], " ").lower()))
        return post_adr_dict

    def _get_formatted_post_addresses(self):
        formatted_post_adr_dict = {}
        for type, post_adr_list in self._get_post_addresses().items():
            formatted_post_adr_dict[type] = []
            for post_adr in post_adr_list:
                strings = []
                if post_adr.get("street"):
                    strings.append(
                        helpers.list_to_string(post_adr.get("street"), "\n"))
                if post_adr.get("box") and post_adr.get("extended"):
                    strings.append("%s %s" % (
                        helpers.list_to_string(post_adr.get("box"), " "),
                        helpers.list_to_string(post_adr.get("extended"), " ")))
                elif post_adr.get("box"):
                    strings.append(
                        helpers.list_to_string(post_adr.get("box"), " "))
                elif post_adr.get("extended"):
                    strings.append(
                        helpers.list_to_string(post_adr.get("extended"), " "))
                if post_adr.get("code") and post_adr.get("city"):
                    strings.append("%s %s" % (
                        helpers.list_to_string(post_adr.get("code"), " "),
                        helpers.list_to_string(post_adr.get("city"), " ")))
                elif post_adr.get("code"):
                    strings.append(
                        helpers.list_to_string(post_adr.get("code"), " "))
                elif post_adr.get("city"):
                    strings.append(
                        helpers.list_to_string(post_adr.get("city"), " "))
                if post_adr.get("region") and post_adr.get("country"):
                    strings.append("%s, %s" % (
                        helpers.list_to_string(post_adr.get("region"), " "),
                        helpers.list_to_string(post_adr.get("country"), " ")))
                elif post_adr.get("region"):
                    strings.append(
                        helpers.list_to_string(post_adr.get("region"), " "))
                elif post_adr.get("country"):
                    strings.append(
                        helpers.list_to_string(post_adr.get("country"), " "))
                formatted_post_adr_dict[type].append('\n'.join(strings))
        return formatted_post_adr_dict

    def _add_post_address(self, type, box, extended, street, code, city,
                          region, country):
        standard_types, custom_types, pref = self._parse_type_value(
            helpers.string_to_list(type, ","), "%s, %s" % (street, city),
            self.address_types_v4 if self.get_version() == "4.0" else
            self.address_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for post address " + street +
                             " is missing.")
        elif len(custom_types) > 1:
            raise ValueError("Error: post address " + street + " got more "
                             "than one custom " "label: " +
                             helpers.list_to_string(custom_types, ", "))
        else:
            adr_obj = self.vcard.add('adr')
            adr_obj.value = vobject.vcard.Address(
                box=helpers.convert_to_vcard(
                    "box address field", box,
                    ObjectType.string_or_list_with_strings),
                extended=helpers.convert_to_vcard(
                    "extended address field", extended,
                    ObjectType.string_or_list_with_strings),
                street=helpers.convert_to_vcard(
                    "street", street, ObjectType.string_or_list_with_strings),
                code=helpers.convert_to_vcard(
                    "post code", code, ObjectType.string_or_list_with_strings),
                city=helpers.convert_to_vcard(
                    "city", city, ObjectType.string_or_list_with_strings),
                region=helpers.convert_to_vcard(
                    "region", region, ObjectType.string_or_list_with_strings),
                country=helpers.convert_to_vcard(
                    "country", country,
                    ObjectType.string_or_list_with_strings))
            if self.get_version() == "4.0":
                if pref > 0:
                    adr_obj.params['PREF'] = str(pref)
            else:
                if pref > 0:
                    standard_types.append("pref")
            if standard_types:
                adr_obj.params['TYPE'] = standard_types
            if custom_types:
                number_of_custom_post_address_labels = 0
                for label in self.vcard.getChildren():
                    if label.name == "X-ABLABEL" \
                            and label.group.startswith("itemadr"):
                        number_of_custom_post_address_labels += 1
                group_name = "itemadr%d" % (
                    number_of_custom_post_address_labels+1)
                adr_obj.group = group_name
                label_obj = self.vcard.add('x-ablabel')
                label_obj.group = group_name
                label_obj.value = custom_types[0]

    def _get_categories(self):
        """
        :rtype: list(str) or list(list(str))
        """
        category_list = []
        for child in self.vcard.getChildren():
            if child.name == "CATEGORIES":
                value = child.value
                category_list.append(
                    value if isinstance(value, list) else [value])
        if len(category_list) == 1:
            return category_list[0]
        return sorted(category_list)

    def _add_category(self, categories):
        """ categories variable must be a list """
        categories_obj = self.vcard.add('categories')
        categories_obj.value = helpers.convert_to_vcard(
            "category", categories, ObjectType.list_with_strings)

    def get_nicknames(self):
        """
        :rtype: list(list(str))
        """
        nicknames = []
        for child in self.vcard.getChildren():
            if child.name == "NICKNAME":
                nicknames.append(child.value)
        return sorted(nicknames)

    def _add_nickname(self, nickname):
        nickname_obj = self.vcard.add('nickname')
        nickname_obj.value = helpers.convert_to_vcard(
            "nickname", nickname, ObjectType.string)

    def _get_notes(self):
        """
        :rtype: list(list(str))
        """
        notes = []
        for child in self.vcard.getChildren():
            if child.name == "NOTE":
                notes.append(child.value)
        return sorted(notes)

    def _add_note(self, note):
        note_obj = self.vcard.add('note')
        note_obj.value = helpers.convert_to_vcard(
            "note", note, ObjectType.string)

    def _get_private_objects(self):
        """
        :rtype: dict(str, list(str))
        """
        private_objects = {}
        for child in self.vcard.getChildren():
            if child.name.lower().startswith("x-"):
                try:
                    key_index = [
                        x.lower() for x in self.supported_private_objects
                    ].index(child.name[2:].lower())
                except ValueError:
                    pass
                else:
                    key = self.supported_private_objects[key_index]
                    if private_objects.get(key) is None:
                        private_objects[key] = []
                    private_objects[key].append(child.value)
        # sort private object lists
        for value in private_objects.values():
            value.sort()
        return private_objects

    def _add_private_object(self, key, value):
        private_obj = self.vcard.add('X-' + key.upper())
        private_obj.value = helpers.convert_to_vcard(
            key, value, ObjectType.string)

    def _get_webpages(self):
        """
        :rtype: list(list(str))
        """
        urls = []
        for child in self.vcard.getChildren():
            if child.name == "URL":
                urls.append(child.value)
        return sorted(urls)

    def _add_webpage(self, webpage):
        webpage_obj = self.vcard.add('url')
        webpage_obj.value = helpers.convert_to_vcard(
            "webpage", webpage, ObjectType.string)

    def get_anniversary(self):
        """:returns: contacts anniversary or None if not available
            :rtype: datetime.datetime or str
        """
        # vcard 4.0 could contain a single text value
        try:
            if self.vcard.anniversary.params.get("VALUE")[0] == "text":
                return self.vcard.anniversary.value
        except (AttributeError, IndexError, TypeError):
            pass
        # else try to convert to a datetime object
        try:
            return helpers.string_to_date(self.vcard.anniversary.value)
        except (AttributeError, ValueError):
            # vcard 3.0: x-anniversary (private object)
            try:
                return helpers.string_to_date(self.vcard.x_anniversary.value)
            except (AttributeError, ValueError):
                pass
        return None

    def get_formatted_anniversary(self):
        return self._format_date_object(
                self.get_anniversary(), self.localize_dates)

    def _add_anniversary(self, date):
        if isinstance(date, str):
            if self.get_version() == "4.0":
                anniversary_obj = self.vcard.add('anniversary')
                anniversary_obj.params['VALUE'] = ["text"]
                anniversary_obj.value = date.strip()
        elif date.year == 1900 and date.month != 0 and date.day != 0 \
                and date.hour == 0 and date.minute == 0 and date.second == 0 \
                and self.get_version() == "4.0":
            anniversary_obj = self.vcard.add('anniversary')
            anniversary_obj.value = "--%.2d%.2d" % (date.month, date.day)
        elif date.tzname() and date.tzname()[3:]:
            if self.get_version() == "4.0":
                anniversary_obj = self.vcard.add('anniversary')
                anniversary_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2d%s" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second, date.tzname()[3:])
            else:
                anniversary_obj = self.vcard.add('x-anniversary')
                anniversary_obj.value = "%.4d-%.2d-%.2dT%.2d:%.2d:%.2d%s" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second, date.tzname()[3:])
        elif date.hour != 0 or date.minute != 0 or date.second != 0:
            if self.get_version() == "4.0":
                anniversary_obj = self.vcard.add('anniversary')
                anniversary_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2dZ" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second)
            else:
                anniversary_obj = self.vcard.add('x-anniversary')
                anniversary_obj.value = "%.4d-%.2d-%.2dT%.2d:%.2d:%.2dZ" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second)
        else:
            if self.get_version() == "4.0":
                anniversary_obj = self.vcard.add('anniversary')
                anniversary_obj.value = "%.4d%.2d%.2d" % (date.year, date.month,
                                                   date.day)
            else:
                anniversary_obj = self.vcard.add('x-anniversary')
                anniversary_obj.value = "%.4d-%.2d-%.2d" % (date.year,
                        date.month, date.day)

    def get_birthday(self):
        """:returns: contacts birthday or None if not available
            :rtype: datetime.datetime or str
        """
        # vcard 4.0 could contain a single text value
        try:
            if self.vcard.bday.params.get("VALUE")[0] == "text":
                return self.vcard.bday.value
        except (AttributeError, IndexError, TypeError):
            pass
        # else try to convert to a datetime object
        try:
            return helpers.string_to_date(self.vcard.bday.value)
        except (AttributeError, ValueError):
            pass
        return None

    def get_formatted_birthday(self):
        return self._format_date_object(
                self.get_birthday(), self.localize_dates)

    def _add_birthday(self, date):
        if isinstance(date, str):
            if self.get_version() == "4.0":
                bday_obj = self.vcard.add('bday')
                bday_obj.params['VALUE'] = ["text"]
                bday_obj.value = date.strip()
        elif date.year == 1900 and date.month != 0 and date.day != 0 \
                and date.hour == 0 and date.minute == 0 and date.second == 0 \
                and self.get_version() == "4.0":
            bday_obj = self.vcard.add('bday')
            bday_obj.value = "--%.2d%.2d" % (date.month, date.day)
        elif date.tzname() and date.tzname()[3:]:
            bday_obj = self.vcard.add('bday')
            if self.get_version() == "4.0":
                bday_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2d%s" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second, date.tzname()[3:])
            else:
                bday_obj.value = "%.4d-%.2d-%.2dT%.2d:%.2d:%.2d%s" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second, date.tzname()[3:])
        elif date.hour != 0 or date.minute != 0 or date.second != 0:
            bday_obj = self.vcard.add('bday')
            if self.get_version() == "4.0":
                bday_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2dZ" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second)
            else:
                bday_obj.value = "%.4d-%.2d-%.2dT%.2d:%.2d:%.2dZ" % (
                    date.year, date.month, date.day, date.hour, date.minute,
                    date.second)
        else:
            bday_obj = self.vcard.add('bday')
            if self.get_version() == "4.0":
                bday_obj.value = "%.4d%.2d%.2d" % (date.year, date.month,
                                                   date.day)
            else:
                bday_obj.value = "%.4d-%.2d-%.2d" % (date.year, date.month,
                                                     date.day)

    #######################
    # object helper methods
    #######################

    @staticmethod
    def _format_date_object(date, localize):
        if date:
            if isinstance(date, str):
                return date
            elif date.year == 1900 and date.month != 0 and date.day != 0 \
                    and date.hour == 0 and date.minute == 0 \
                    and date.second == 0:
                return "--%.2d-%.2d" % (date.month, date.day)
            elif (date.tzname() and date.tzname()[3:]) or \
                    (date.hour != 0 or date.minute != 0 or date.second != 0):
                if localize:
                    return date.strftime(locale.nl_langinfo(locale.D_T_FMT))
                else:
                    utc_offset=-time.timezone/60/60
                    return date.strftime(
                            "%Y-%m-%dT%H:%M:%S+" + str(int(utc_offset)).zfill(2) + ":00")
            else:
                if localize:
                    return date.strftime(locale.nl_langinfo(locale.D_FMT))
                else:
                    return date.strftime("%Y-%m-%d")
        return ""

    @staticmethod
    def _filter_invalid_tags(contents):
        contents = re.sub('(?i)' + re.escape('X-messaging/aim-All'), 'X-AIM',
                          contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/gadu-All'),
                          'X-GADUGADU', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/groupwise-All'),
                          'X-GROUPWISE', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/icq-All'), 'X-ICQ',
                          contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/xmpp-All'),
                          'X-JABBER', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/msn-All'), 'X-MSN',
                          contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/yahoo-All'),
                          'X-YAHOO', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/skype-All'),
                          'X-SKYPE', contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/irc-All'), 'X-IRC',
                          contents)
        contents = re.sub('(?i)' + re.escape('X-messaging/sip-All'), 'X-SIP',
                          contents)
        return contents

    def _process_user_input(self, input):
        yaml_parser = YAML(typ='base')
        # parse user input string
        try:
            contact_data = yaml_parser.load(input)
        except ruamel.yaml.parser.ParserError as err:
            raise ValueError(err)
        except ruamel.yaml.scanner.ScannerError as err:
            raise ValueError(err)
        else:
            if contact_data is None:
                raise ValueError("Error: Found no contact information")

        # check for available data
        # at least enter name or organisation
        if not bool(contact_data.get("First name")) \
                and not bool(contact_data.get("Last name")) \
                and not bool(contact_data.get("Organisation")):
            raise ValueError(
                "Error: You must either enter a name or an organisation")

        # update rev
        self.delete_vcard_object("REV")
        self._add_rev(datetime.datetime.now())

        # name
        self.delete_vcard_object("FN")
        self.delete_vcard_object("N")
        # although the "n" attribute is not explisitely required by the vcard
        # specification,
        # the vobject library throws an exception, if it doesn't exist
        # so add the name regardless if it's empty or not
        self._add_name(
            contact_data.get("Prefix") or "",
            contact_data.get("First name") or "",
            contact_data.get("Additional") or "",
            contact_data.get("Last name") or "",
            contact_data.get("Suffix") or "")
        # nickname
        self.delete_vcard_object("NICKNAME")
        if bool(contact_data.get("Nickname")):
            if isinstance(contact_data.get("Nickname"), str):
                self._add_nickname(contact_data.get("Nickname"))
            elif isinstance(contact_data.get("Nickname"), list):
                for nickname in contact_data.get("Nickname"):
                    if bool(nickname):
                        self._add_nickname(nickname)
            else:
                raise ValueError(
                    "Error: nickname must be a string or a list of strings")

        # organisation
        self.delete_vcard_object("ORG")
        self.delete_vcard_object("X-ABSHOWAS")
        if bool(contact_data.get("Organisation")):
            if isinstance(contact_data.get("Organisation"), str):
                self._add_organisation([contact_data.get("Organisation")])
            elif isinstance(contact_data.get("Organisation"), list):
                for organisation in contact_data.get("Organisation"):
                    if bool(organisation):
                        if isinstance(organisation, str):
                            self._add_organisation([organisation])
                        else:
                            self._add_organisation(organisation)
            else:
                raise ValueError("Error: organisation must be a string or a "
                                 "list of strings")

        # role
        self.delete_vcard_object("ROLE")
        if bool(contact_data.get("Role")):
            if isinstance(contact_data.get("Role"), str):
                self._add_role(contact_data.get("Role"))
            elif isinstance(contact_data.get("Role"), list):
                for role in contact_data.get("Role"):
                    if bool(role):
                        self._add_role(role)
            else:
                raise ValueError(
                    "Error: role must be a string or a list of strings")

        # title
        self.delete_vcard_object("TITLE")
        if bool(contact_data.get("Title")):
            if isinstance(contact_data.get("Title"), str):
                self._add_title(contact_data.get("Title"))
            elif isinstance(contact_data.get("Title"), list):
                for title in contact_data.get("Title"):
                    if bool(title):
                        self._add_title(title)
            else:
                raise ValueError(
                    "Error: title must be a string or a list of strings")

        # phone
        self.delete_vcard_object("TEL")
        if contact_data.get("Phone"):
            if isinstance(contact_data.get("Phone"), dict):
                for type, number_list in contact_data.get("Phone").items():
                    if isinstance(number_list, str):
                        number_list = [number_list]
                    if isinstance(number_list, list):
                        for number in number_list:
                            if number:
                                self._add_phone_number(type, number)
                    else:
                        raise ValueError(
                            "Error: got no number or list of numbers for the "
                            "phone number type " + type)
            else:
                raise ValueError(
                    "Error: missing type value for phone number field")

        # email
        self.delete_vcard_object("EMAIL")
        if contact_data.get("Email"):
            if isinstance(contact_data.get("Email"), dict):
                for type, email_list in contact_data.get("Email").items():
                    if isinstance(email_list, str):
                        email_list = [email_list]
                    if isinstance(email_list, list):
                        for email in email_list:
                            if email:
                                self.add_email_address(type, email)
                    else:
                        raise ValueError(
                            "Error: got no email or list of emails for the "
                            "email address type " + type)
            else:
                raise ValueError(
                    "Error: missing type value for email address field")

        # post addresses
        self.delete_vcard_object("ADR")
        if contact_data.get("Address"):
            if isinstance(contact_data.get("Address"), dict):
                for type, post_adr_list in contact_data.get("Address").items():
                    if isinstance(post_adr_list, dict):
                        post_adr_list = [post_adr_list]
                    if isinstance(post_adr_list, list):
                        for post_adr in post_adr_list:
                            if isinstance(post_adr, dict):
                                address_not_empty = False
                                for key, value in post_adr.items():
                                    if key in ["Box", "Extended", "Street",
                                               "Code", "City", "Region",
                                               "Country"] and bool(value):
                                        address_not_empty = True
                                        break
                                if address_not_empty:
                                    self._add_post_address(
                                        type, post_adr.get("Box") or "",
                                        post_adr.get("Extended") or "",
                                        post_adr.get("Street") or "",
                                        post_adr.get("Code") or "",
                                        post_adr.get("City") or "",
                                        post_adr.get("Region") or "",
                                        post_adr.get("Country") or "")
                            else:
                                raise ValueError(
                                    "Error: one of the " + type + " type "
                                    "address list items does not contain an "
                                    "address")
                    else:
                        raise ValueError(
                            "Error: got no address or list of addresses for "
                            "the post address type " + type)
            else:
                raise ValueError(
                    "Error: missing type value for post address field")

        # categories
        self.delete_vcard_object("CATEGORIES")
        if contact_data.get("Categories"):
            if isinstance(contact_data.get("Categories"), str):
                self._add_category([contact_data.get("Categories")])
            elif isinstance(contact_data.get("Categories"), list):
                only_contains_strings = True
                for sub_category in contact_data.get("Categories"):
                    if not isinstance(sub_category, str):
                        only_contains_strings = False
                        break
                # if the category list only contains strings, pack all of them
                # in a single CATEGORIES vcard tag
                if only_contains_strings:
                    self._add_category(contact_data.get("Categories"))
                else:
                    for sub_category in contact_data.get("Categories"):
                        if sub_category:
                            if isinstance(sub_category, str):
                                self._add_category([sub_category])
                            else:
                                self._add_category(sub_category)
            else:
                raise ValueError(
                    "Error: category must be a string or a list of strings")

        # urls
        self.delete_vcard_object("URL")
        if contact_data.get("Webpage"):
            if isinstance(contact_data.get("Webpage"), str):
                self._add_webpage(contact_data.get("Webpage"))
            elif isinstance(contact_data.get("Webpage"), list):
                for webpage in contact_data.get("Webpage"):
                    if webpage:
                        self._add_webpage(webpage)
            else:
                raise ValueError(
                    "Error: webpage must be a string or a list of strings")

        # anniversary
        self.delete_vcard_object("ANNIVERSARY")
        self.delete_vcard_object("X-ANNIVERSARY")
        if contact_data.get("Anniversary"):
            if isinstance(contact_data.get("Anniversary"), str):
                if re.match(r"^text[\s]*=.*$", contact_data.get("Anniversary")):
                    l = [x.strip() for x in
                         re.split("text[\s]*=", contact_data.get("Anniversary"))
                         if x.strip()]
                    if self.get_version() == "4.0":
                        date = ', '.join(l)
                    else:
                        raise ValueError(
                            "Error: Free text format for anniversary only "
                            "usable with vcard version 4.0.")
                elif re.match(r"^--\d{4}$", contact_data.get("Anniversary")) \
                        and self.get_version() != "4.0":
                    raise ValueError(
                        "Error: Anniversary format --mmdd only usable with "
                        "vcard version 4.0. You may use 1900 as placeholder, "
                        "if the year of the anniversary is unknown.")
                elif re.match(
                        r"^--\d{2}-\d{2}$", contact_data.get("Anniversary")) \
                        and self.get_version() != "4.0":
                    raise ValueError(
                        "Error: Anniversary format --mm-dd only usable with "
                        "vcard version 4.0. You may use 1900 as placeholder, "
                        "if the year of the anniversary is unknown.")
                else:
                    try:
                        date = helpers.string_to_date(
                            contact_data.get("Anniversary"))
                    except ValueError:
                        raise ValueError(
                            "Error: Wrong anniversary format or invalid date\n"
                            "Use format yyyy-mm-dd or yyyy-mm-ddTHH:MM:SS")
                if date:
                    self._add_anniversary(date)
            else:
                raise ValueError("Error: anniversary must be a string object.")

        # birthday
        self.delete_vcard_object("BDAY")
        if contact_data.get("Birthday"):
            if isinstance(contact_data.get("Birthday"), str):
                if re.match(r"^text[\s]*=.*$", contact_data.get("Birthday")):
                    l = [x.strip() for x in
                         re.split("text[\s]*=", contact_data.get("Birthday"))
                         if x.strip()]
                    if self.get_version() == "4.0":
                        date = ', '.join(l)
                    else:
                        raise ValueError(
                            "Error: Free text format for birthday only usable "
                            "with vcard version 4.0.")
                elif re.match(r"^--\d{4}$", contact_data.get("Birthday")) \
                        and self.get_version() != "4.0":
                    raise ValueError(
                        "Error: Birthday format --mmdd only usable with "
                        "vcard version 4.0. You may use 1900 as placeholder, "
                        "if the year of birth is unknown.")
                elif re.match(
                        r"^--\d{2}-\d{2}$", contact_data.get("Birthday")) \
                        and self.get_version() != "4.0":
                    raise ValueError(
                        "Error: Birthday format --mm-dd only usable with "
                        "vcard version 4.0. You may use 1900 as placeholder, "
                        "if the year of birth is unknown.")
                else:
                    try:
                        date = helpers.string_to_date(
                            contact_data.get("Birthday"))
                    except ValueError:
                        raise ValueError(
                            "Error: Wrong birthday format or invalid date\n"
                            "Use format yyyy-mm-dd or yyyy-mm-ddTHH:MM:SS")
                if date:
                    self._add_birthday(date)
            else:
                raise ValueError("Error: birthday must be a string object.")

        # private objects
        for supported in self.supported_private_objects:
            self.delete_vcard_object("X-%s" % supported.upper())
        if contact_data.get("Private"):
            if isinstance(contact_data.get("Private"), dict):
                for key, value_list in contact_data.get("Private").items():
                    if key in self.supported_private_objects:
                        if isinstance(value_list, str):
                            value_list = [value_list]
                        if isinstance(value_list, list):
                            for value in value_list:
                                if value:
                                    self._add_private_object(key, value)
                        else:
                            raise ValueError(
                                "Error: got no value or list of values for "
                                "the private object " + key)
                    else:
                        raise ValueError(
                            "Error: private object key " + key + " was "
                            "changed.\nSupported private keys: " + ', '.join(
                                self.supported_private_objects))
            else:
                raise ValueError("Error: private objects must consist of a "
                                 "key : value pair.")

        # notes
        self.delete_vcard_object("NOTE")
        if contact_data.get("Note"):
            if isinstance(contact_data.get("Note"), str):
                self._add_note(contact_data.get("Note"))
            elif isinstance(contact_data.get("Note"), list):
                for note in contact_data.get("Note"):
                    if note:
                        self._add_note(note)
            else:
                raise ValueError(
                    "Error: note must be a string or a list of strings\n"
                    "Use the | character to create a multi-line note.")

    def get_template(self):
        strings = []
        for line in helpers.get_new_contact_template().splitlines():
            if line.startswith("#"):
                strings.append(line)
            elif line == "":
                strings.append(line)

            elif line.lower().startswith("prefix"):
                strings += helpers.convert_to_yaml(
                    "Prefix", self._get_name_prefixes(), 0, 11, True)
            elif line.lower().startswith("first name"):
                strings += helpers.convert_to_yaml(
                    "First name", self._get_first_names(), 0, 11, True)
            elif line.lower().startswith("additional"):
                strings += helpers.convert_to_yaml(
                    "Additional", self._get_additional_names(), 0, 11, True)
            elif line.lower().startswith("last name"):
                strings += helpers.convert_to_yaml(
                    "Last name", self._get_last_names(), 0, 11, True)
            elif line.lower().startswith("suffix"):
                strings += helpers.convert_to_yaml(
                    "Suffix", self._get_name_suffixes(), 0, 11, True)
            elif line.lower().startswith("nickname"):
                strings += helpers.convert_to_yaml(
                    "Nickname", self.get_nicknames(), 0, 9, True)

            elif line.lower().startswith("organisation"):
                strings += helpers.convert_to_yaml(
                    "Organisation", self._get_organisations(), 0, 13, True)
            elif line.lower().startswith("title"):
                strings += helpers.convert_to_yaml(
                    "Title", self._get_titles(), 0, 6, True)
            elif line.lower().startswith("role"):
                strings += helpers.convert_to_yaml(
                    "Role", self._get_roles(), 0, 6, True)

            elif line.lower().startswith("phone"):
                strings.append("Phone :")
                if not self.get_phone_numbers().keys():
                    strings.append("    cell : ")
                    strings.append("    home : ")
                else:
                    longest_key = max(self.get_phone_numbers().keys(), key=len)
                    for type, number_list in sorted(
                            self.get_phone_numbers().items(),
                            key=lambda k: k[0].lower()):
                        strings += helpers.convert_to_yaml(
                            type, number_list, 4, len(longest_key)+1, True)

            elif line.lower().startswith("email"):
                strings.append("Email :")
                if not self.get_email_addresses().keys():
                    strings.append("    home : ")
                    strings.append("    work : ")
                else:
                    longest_key = max(self.get_email_addresses().keys(),
                                      key=len)
                    for type, email_list in sorted(
                            self.get_email_addresses().items(),
                            key=lambda k: k[0].lower()):
                        strings += helpers.convert_to_yaml(
                            type, email_list, 4, len(longest_key)+1, True)

            elif line.lower().startswith("address"):
                strings.append("Address :")
                if not self._get_post_addresses().keys():
                    strings.append("    home :")
                    strings.append("        Box      : ")
                    strings.append("        Extended : ")
                    strings.append("        Street   : ")
                    strings.append("        Code     : ")
                    strings.append("        City     : ")
                    strings.append("        Region   : ")
                    strings.append("        Country  : ")
                else:
                    for type, post_adr_list in sorted(
                            self._get_post_addresses().items(),
                            key=lambda k: k[0].lower()):
                        strings.append("    %s:" % type)
                        for post_adr in post_adr_list:
                            indentation = 8
                            if len(post_adr_list) > 1:
                                indentation += 4
                                strings.append("        -")
                            strings += helpers.convert_to_yaml(
                                "Box", post_adr.get("box"), indentation, 9,
                                True)
                            strings += helpers.convert_to_yaml(
                                "Extended", post_adr.get("extended"),
                                indentation, 9, True)
                            strings += helpers.convert_to_yaml(
                                "Street", post_adr.get("street"), indentation,
                                9, True)
                            strings += helpers.convert_to_yaml(
                                "Code", post_adr.get("code"), indentation, 9,
                                True)
                            strings += helpers.convert_to_yaml(
                                "City", post_adr.get("city"), indentation, 9,
                                True)
                            strings += helpers.convert_to_yaml(
                                "Region", post_adr.get("region"), indentation,
                                9, True)
                            strings += helpers.convert_to_yaml(
                                "Country", post_adr.get("country"),
                                indentation, 9, True)

            elif line.lower().startswith("private"):
                strings.append("Private :")
                if self.supported_private_objects:
                    longest_key = max(self.supported_private_objects, key=len)
                    for object in self.supported_private_objects:
                        strings += helpers.convert_to_yaml(
                            object, self._get_private_objects().get(object)
                            or "", 4, len(longest_key)+1, True)

            elif line.lower().startswith("anniversary"):
                anniversary = self.get_anniversary()
                if anniversary:
                    if isinstance(anniversary, str):
                        strings.append("Anniversary : text= %s" % anniversary)
                    elif anniversary.year == 1900 and anniversary.month != 0 and \
                            anniversary.day != 0 and anniversary.hour == 0 and \
                            anniversary.minute == 0 and anniversary.second == 0 and \
                            self.get_version() == "4.0":
                        strings.append("Anniversary : --%.2d-%.2d"
                                       % (anniversary.month, anniversary.day))
                    elif (anniversary.tzname() and anniversary.tzname()[3:]) or \
                            (anniversary.hour != 0 or anniversary.minute != 0
                             or anniversary.second != 0):
                        strings.append("Anniversary : %s" % anniversary.isoformat())
                    else:
                        strings.append("Anniversary : %.4d-%.2d-%.2d" % (
                            anniversary.year, anniversary.month, anniversary.day))
                else:
                    strings.append("Anniversary : ")
            elif line.lower().startswith("birthday"):
                birthday = self.get_birthday()
                if birthday:
                    if isinstance(birthday, str):
                        strings.append("Birthday : text= %s" % birthday)
                    elif birthday.year == 1900 and birthday.month != 0 and \
                            birthday.day != 0 and birthday.hour == 0 and \
                            birthday.minute == 0 and birthday.second == 0 and \
                            self.get_version() == "4.0":
                        strings.append("Birthday : --%.2d-%.2d"
                                       % (birthday.month, birthday.day))
                    elif (birthday.tzname() and birthday.tzname()[3:]) or \
                            (birthday.hour != 0 or birthday.minute != 0
                             or birthday.second != 0):
                        strings.append("Birthday : %s" % birthday.isoformat())
                    else:
                        strings.append("Birthday : %.4d-%.2d-%.2d" % (
                            birthday.year, birthday.month, birthday.day))
                else:
                    strings.append("Birthday : ")
            elif line.lower().startswith("categories"):
                strings += helpers.convert_to_yaml(
                    "Categories", self._get_categories(), 0, 11, True)
            elif line.lower().startswith("note"):
                strings += helpers.convert_to_yaml(
                    "Note", self._get_notes(), 0, 5, True)
            elif line.lower().startswith("webpage"):
                strings += helpers.convert_to_yaml(
                    "Webpage", self._get_webpages(), 0, 8, True)
        return '\n'.join(strings) + "\n"   # posix standard: eof char must be \n

    def print_vcard(self, show_address_book=True, show_uid=True):
        strings = []
        # name
        if self._get_first_names() or self._get_last_names():
            names = []
            if self._get_name_prefixes():
                names += self._get_name_prefixes()
            if self._get_first_names():
                names += self._get_first_names()
            if self._get_additional_names():
                names += self._get_additional_names()
            if self._get_last_names():
                names += self._get_last_names()
            if self._get_name_suffixes():
                names += self._get_name_suffixes()
            strings.append("Name: %s" % helpers.list_to_string(names, " "))
        # organisation
        if self._get_organisations():
            strings += helpers.convert_to_yaml(
                "Organisation", self._get_organisations(), 0, -1, False)
        # address book name
        if show_address_book:
            strings.append("Address book: %s" % self.address_book.name)

        # person related information
        if self.get_birthday() is not None or self.get_anniversary() is not None \
                or self.get_nicknames() or self._get_roles() or self._get_titles():
            strings.append("General:")
            if self.get_anniversary():
                strings.append("    Anniversary: %s"
                               % self.get_formatted_anniversary())
            if self.get_birthday():
                strings.append("    Birthday: %s"
                               % self.get_formatted_birthday())
            if self.get_nicknames():
                strings += helpers.convert_to_yaml(
                    "Nickname", self.get_nicknames(), 4, -1, False)
            if self._get_roles():
                strings += helpers.convert_to_yaml(
                    "Role", self._get_roles(), 4, -1, False)
            if self._get_titles():
                strings += helpers.convert_to_yaml(
                    "Title", self._get_titles(), 4, -1, False)

        # phone numbers
        if self.get_phone_numbers().keys():
            strings.append("Phone")
            for type, number_list in sorted(
                    self.get_phone_numbers().items(),
                    key=lambda k: k[0].lower()):
                strings += helpers.convert_to_yaml(
                    type, number_list, 4, -1, False)

        # email addresses
        if self.get_email_addresses().keys():
            strings.append("E-Mail")
            for type, email_list in sorted(
                    self.get_email_addresses().items(),
                    key=lambda k: k[0].lower()):
                strings += helpers.convert_to_yaml(
                    type, email_list, 4, -1, False)

        # post addresses
        if self._get_post_addresses().keys():
            strings.append("Address")
            for type, post_adr_list in sorted(
                    self._get_formatted_post_addresses().items(),
                    key=lambda k: k[0].lower()):
                strings += helpers.convert_to_yaml(
                    type, post_adr_list, 4, -1, False)

        # private objects
        if self._get_private_objects().keys():
            strings.append("Private:")
            for object in self.supported_private_objects:
                if self._get_private_objects().get(object):
                    strings += helpers.convert_to_yaml(
                        object, self._get_private_objects().get(object), 4, -1,
                        False)

        # misc stuff
        if self._get_categories() or (show_uid and self.get_uid() != "") \
                or self._get_webpages() or self._get_notes():
            strings.append("Miscellaneous")
            if show_uid and self.get_uid():
                strings.append("    UID: %s" % self.get_uid())
            if self._get_categories():
                strings += helpers.convert_to_yaml(
                    "Categories", self._get_categories(), 4, -1, False)
            if self._get_webpages():
                strings += helpers.convert_to_yaml(
                    "Webpage", self._get_webpages(), 4, -1, False)
            if self._get_notes():
                strings += helpers.convert_to_yaml(
                    "Note", self._get_notes(), 4, -1, False)
        return '\n'.join(strings)

    def write_to_file(self, overwrite=False):
        # make sure, that every contact contains a uid
        if not self.get_uid():
            self.add_uid(helpers.get_random_uid())
        try:
            with atomic_write(self.filename, overwrite=overwrite) as f:
                f.write(self.vcard.serialize())
        except vobject.base.ValidateError as err:
            print("Error: Vcard is not valid.\n%s" % err)
            sys.exit(4)
        except IOError as err:
            print("Error: Can't write\n%s" % err)
            sys.exit(4)
        except OSError as err:
            print("Error: vcard with the file name %s already exists\n%s"
                  % (os.path.basename(self.filename), err))
            sys.exit(4)

    def delete_vcard_object(self, object_name):
        # first collect all vcard items, which should be removed
        to_be_removed = []
        for child in self.vcard.getChildren():
            if child.name == object_name:
                if child.group:
                    for label in self.vcard.getChildren():
                        if label.name == "X-ABLABEL" and \
                                label.group == child.group:
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

    #######################
    # static helper methods
    #######################

    def _get_types_for_vcard_object(self, object, default_type):
        """
        get list of types for phone number, email or post address
        :param object: vcard class object
        :type object: vobject.vCard
        :param default_type: use if the object contains no type
        :type default_type: str
        :returns: list of type labels
        :rtype: list(str)
        """
        type_list = []
        # try to find label group for custom value type
        if object.group:
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group == object.group:
                    custom_type = label.value.strip()
                    if custom_type:
                        type_list.append(custom_type)
        # then load type from params dict
        standard_types = object.params.get("TYPE")
        if standard_types is not None:
            if not isinstance(standard_types, list):
                standard_types = [standard_types]
            for type in standard_types:
                type = type.strip()
                if type and type.lower() != "pref":
                    if not type.lower().startswith("x-"):
                        type_list.append(type)
                    elif type[2:].lower() not in \
                            [x.lower() for x in type_list]:
                        # add x-custom type in case it's not already added by
                        # custom label for loop above but strip x- before
                        type_list.append(type[2:])
        # try to get pref parameter from vcard version 4.0
        try:
            type_list.append("pref=%d" % int(object.params.get("PREF")[0]))
        except (IndexError, TypeError, ValueError):
            # else try to determine, if type params contain pref attribute
            try:
                for x in object.params.get("TYPE"):
                    if x.lower() == "pref" and "pref" not in type_list:
                        type_list.append("pref")
            except TypeError:
                pass
        # return type_list or default type
        if type_list:
            return type_list
        return [default_type]

    @staticmethod
    def _parse_type_value(types, value, supported_types):
        """Parse type value of phone numbers, email and post addresses.

        :param types: list of type values
        :type types: list(str)
        :param value: the corresponding label, required for more verbose
            exceptions
        :type value: str
        :param supported_types: all allowed standard types
        :type supported_types: list(str)
        :returns: tuple of standard and custom types and pref integer
        :rtype: tuple(list(str), list(str), int)

        """
        custom_types = []
        standard_types = []
        pref = 0
        for type in types:
            type = type.strip()
            if type:
                if type.lower() in supported_types:
                    standard_types.append(type)
                elif type.lower() == "pref":
                    pref += 1
                elif re.match(r"^pref=\d{1,2}$", type.lower()):
                    pref += int(type.split("=")[1])
                else:
                    if type.lower().startswith("x-"):
                        custom_types.append(type[2:])
                        standard_types.append(type)
                    else:
                        custom_types.append(type)
                        standard_types.append("X-%s" % type)
        return (standard_types, custom_types, pref)
