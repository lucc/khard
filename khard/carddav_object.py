# -*- coding: utf-8 -*-
"""Classes and logic to handle vCards in khard.

This module explicitly supports the vCard specifications version 3.0 and 4.0
which can be found here:
- version 3.0: https://tools.ietf.org/html/rfc2426
- version 4.0: https://tools.ietf.org/html/rfc6350
"""

import copy
import datetime
import locale
import logging
import os
import re
import sys
import time

from atomicwrites import atomic_write
import vobject

import ruamel.yaml
from ruamel.yaml import YAML

from . import helpers
from .object_type import ObjectType


def convert_to_vcard(name, value, allowed_object_type):
    """converts user input into vcard compatible data structures

    :param str name: object name, only required for error messages
    :param value: user input
    :type value: str or list(str)
    :param allowed_object_type: set the accepted return type for vcard
        attribute
    :type allowed_object_type: enum of type ObjectType
    :returns: cleaned user input, ready for vcard or a ValueError
    :rtype: str or list(str)
    """
    if isinstance(value, str):
        if allowed_object_type == ObjectType.list_with_strings:
            return [value.strip()]
        return value.strip()
    if isinstance(value, list):
        if allowed_object_type == ObjectType.string:
            raise ValueError("Error: " + name + " must contain a string.")
        if not all(isinstance(entry, str) for entry in value):
            raise ValueError("Error: " + name +
                             " must not contain a nested list")
        # filter out empty list items and strip leading and trailing space
        return [x.strip() for x in value if x.strip()]
    if allowed_object_type == ObjectType.string:
        raise ValueError("Error: " + name + " must be a string.")
    if allowed_object_type == ObjectType.list_with_strings:
        raise ValueError("Error: " + name + " must be a list with strings.")
    raise ValueError("Error: " + name +
                     " must be a string or a list with strings.")


class VCardWrapper:
    """Wrapper class around a vobject.vCard object.

    This class can wrap a single vCard and presents its data in a manner
    suitable for khard.  Additionally some details of the vCard specifications
    in RFC 2426 (version 3.0) and RFC 6350 (version 4.0) that are not enforced
    by the vobject library are enforced here.
    """

    _default_version = "3.0"
    _supported_versions = ("3.0", "4.0")

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

    def __init__(self, vcard, version=None):
        """Initialize the wrapper around the given vcard.

        :param vobject.vCard vcard: the vCard to wrap
        :param version: the version of the RFC to use (if the card has none)
        :type version: str or None
        """
        self.vcard = vcard
        if not self.version:
            version = version or self._default_version
            logging.warning("Wrapping unversioned vCard object, setting "
                            "version to %s.", version)
            self.version = version
        elif self.version not in self._supported_versions:
            logging.warning("Wrapping vCard with unsupported version %s, this "
                            "might change any incompatible attributes.",
                            version)

    def __str__(self):
        return self.formatted_name

    def _get_string_field(self, field):
        """Get a string field from the underlying vCard.

        :param field: the field value to get
        :type field: str
        :returns: the field value or the empty string
        :rtype: str

        """
        try:
            return getattr(self.vcard, field).value
        except AttributeError:
            return ""

    def _get_multi_property(self, name):
        """Get a vCard property that can exist more than once.

        It does not matter what the individual vcard properties store as their
        value.  This function returnes them untouched inside an agregating
        list.

        If the property is part of a group containing exactly two items, with
        exactly one ABLABEL. the property will be prefixed with that ABLABEL.

        :param name: the name of the property (should be UPPER case)
        :type name: str
        :returns: the values from all occurences of the named property
        :rtype: list
        """
        values = []
        for child in self.vcard.getChildren():
            if child.name == name:
                ablabel = self._get_ablabel(child)
                if ablabel:
                    values.append(ablabel + ": " + child.value)
                else:
                    values.append(child.value)
        return sorted(values)

    def _delete_vcard_object(self, name):
        """Delete all fields with the given name from the underlying vCard.

        If a field that will be deleted is in a group with an X-ABLABEL field,
        that X-ABLABEL field will also be deleted.  These fields are commonly
        added by the Apple address book to attach custom labels to some fields.

        :param name: the name of the fields to delete
        :type name: str
        :returns: None
        """
        # first collect all vcard items, which should be removed
        to_be_removed = []
        for child in self.vcard.getChildren():
            if child.name == name:
                if child.group:
                    for label in self.vcard.getChildren():
                        if label.name == "X-ABLABEL" and \
                                label.group == child.group:
                            to_be_removed.append(label)
                to_be_removed.append(child)
        # then delete them one by one
        for item in to_be_removed:
            self.vcard.remove(item)

    @staticmethod
    def _parse_type_value(types, supported_types):
        """Parse type value of phone numbers, email and post addresses.

        :param types: list of type values
        :type types: list(str)
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
                        standard_types.append("X-{}".format(type))
        return (standard_types, custom_types, pref)

    def _get_types_for_vcard_object(self, object, default_type):
        """get list of types for phone number, email or post address

        :param object: vcard class object
        :type object: vobject.base.ContentLine
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
                    elif type[2:].lower() not in [x.lower()
                                                  for x in type_list]:
                        # add x-custom type in case it's not already added by
                        # custom label for loop above but strip x- before
                        type_list.append(type[2:])
        # try to get pref parameter from vcard version 4.0
        try:
            type_list.append("pref=%d" % int(object.params.get("PREF")[0]))
        except (IndexError, TypeError, ValueError):
            # else try to determine, if type params contain pref attribute
            try:
                for type in object.params.get("TYPE"):
                    if type.lower() == "pref" and "pref" not in type_list:
                        type_list.append("pref")
            except TypeError:
                pass
        # return type_list or default type
        if type_list:
            return type_list
        return [default_type]

    @property
    def version(self):
        return self._get_string_field("version")

    @version.setter
    def version(self, value):
        if value not in self._supported_versions:
            logging.warning("Setting vcard version to unsupported version %s",
                            value)
        # All vCards should only always have one version, this is a requirement
        # for version 4 but also makes sense for all other versions.
        self._delete_vcard_object("VERSION")
        version = self.vcard.add("version")
        version.value = convert_to_vcard("version", value, ObjectType.string)

    @property
    def uid(self):
        return self._get_string_field("uid")

    @uid.setter
    def uid(self, value):
        # All vCards should only always have one UID, this is a requirement
        # for version 4 but also makes sense for all other versions.
        self._delete_vcard_object("UID")
        uid = self.vcard.add('uid')
        uid.value = convert_to_vcard("uid", value, ObjectType.string)

    def _update_revision(self):
        # All vCards should only always have one revision, this is a
        # requirement for version 4 but also makes sense for all other
        # versions.
        self._delete_vcard_object("REV")
        rev = self.vcard.add('rev')
        rev.value = datetime.datetime.now().strftime("%Y%mdT%H%M%SZ")

    @property
    def birthday(self):
        """Return the birthday as a datetime object or a string depending on
        weather it is of type text or not.  If no birthday is present in the
        vcard None is returned.

        :returns: contacts birthday or None if not available
        :rtype: datetime.datetime or str or NoneType
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

    @birthday.setter
    def birthday(self, date):
        """Store the given date as BDAY in the vcard.

        :param date: the new date to store as birthday
        :type date: datetime.datetime or str
        """
        value, text = self._prepare_birthday_value(date)
        if value is None:
            logging.warning('Failed to set anniversary to %s', date)
            return
        bday = self.vcard.add('bday')
        bday.value = value
        if text:
            bday.params['VALUE'] = ['text']

    @property
    def anniversary(self):
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

    def _get_ablabel(self, item):
        """Get an ABLABEL for a specified item in the vCard.
        Will return the ABLABEL only if the item is part of a group with exactly
        two items, exactly one of which is an ABLABEL.

        :param item: the item to be labelled
        :type item: vobject.base.ContentLine
        :returns: the ABLABEL in the circumstances above or an empty string
        :rtype: str

        """
        label = ""
        if item.group:
            count = 0
            for child in self.vcard.getChildren():
                if child.group and child.group == item.group:
                    count += 1
                    if child.name == "X-ABLABEL":
                        if label == "":
                            label = child.value
                        else:
                            return ""
            if count != 2:
                label = ""
        return label

    def _get_new_group(self, group_type=""):
        """Get an unused group name for adding new groups. Uses the form item123
         or itemgroup_type123 if a grouptype is specified.

        :param group_type: (Optional) a string to add between "item" and the
                           number
        :type group_type: str
        :returns: the name of the first unused group of the specified form
        :rtype: str

        """
        counter = 1
        while True:
            group_name = "item%s%d" % (group_type, counter)
            for child in self.vcard.getChildren():
                if child.group and child.group == group_name:
                    counter += 1
                    break
            else:
                return group_name

    def _add_labelled_object(self, obj_type, user_input, name_groups=False):
        obj = self.vcard.add(obj_type)
        if isinstance(user_input, dict):
            if len(user_input) > 1:
                raise ValueError("Error: %s must be a string or a dict " +\
                                 "containing one key/value pair." % obj_type)
            label = list(user_input)[0]
            group_name = self._get_new_group(obj_type if name_groups else "")
            obj.group = group_name
            obj.value = convert_to_vcard(obj_type, user_input[label],
                                         ObjectType.string)
            ablabel_obj = self.vcard.add('X-ABLABEL')
            ablabel_obj.group = group_name
            ablabel_obj.value = label
        else:
            obj.value = convert_to_vcard(obj_type, user_input,
                                         ObjectType.string)

    @anniversary.setter
    def anniversary(self, date):
        value, text = self._prepare_birthday_value(date)
        if value is None:
            logging.warning('Failed to set anniversary to %s', date)
            return
        if text:
            anniversary = self.vcard.add('anniversary')
            anniversary.params['VALUE'] = ['text']
            anniversary.value = value
        elif self.version == "4.0":
            self.vcard.add('anniversary').value = value
        else:
            self.vcard.add('x-anniversary').value = value

    def _prepare_birthday_value(self, date):
        """Prepare a value to be stored in a BDAY or ANNIVERSARY attribute.

        :param date: the date like value to be stored
        :type date: datetime.datetime or str
        :returns: the object to set as the .value for the attribute and weather
            it should be stored as plain text
        :rtype: tuple(str,bool)
        """
        if isinstance(date, str):
            if self.version == "4.0":
                return date.strip(), True
            return None, False
        if date.year == 1900 and date.month != 0 and date.day != 0 \
                and date.hour == 0 and date.minute == 0 and date.second == 0 \
                and self.version == "4.0":
            fmt = '--%m%d'
        elif date.tzname() and date.tzname()[3:]:
            if self.version == "4.0":
                fmt = "%Y%m%dT%H%M%S{}".format(date.tzname()[3:])
            else:
                fmt = "%Y-%m-%dT%H:%M:%S{}".format(date.tzname()[3:])
        elif date.hour != 0 or date.minute != 0 or date.second != 0:
            if self.version == "4.0":
                fmt = "%Y%m%dT%H%M%SZ"
            else:
                fmt = "%Y-%m-%dT%H:%M:%SZ"
        else:
            if self.version == "4.0":
                fmt = "%Y%m%d"
            else:
                fmt = "%Y-%m-%d"
        return date.strftime(fmt), False

    @property
    def formatted_name(self):
        return self._get_string_field("fn")

    @formatted_name.setter
    def formatted_name(self, value):
        """Set the FN field to the new value.

        All previously existing FN fields are deleted.  Version 4 of the specs
        requires the vCard to only habe one FN field.  For other versions we
        enforce this equally.

        :param value: the new formatted name
        :type value: str
        """
        self._delete_vcard_object("FN")
        if value:
            value = convert_to_vcard("FN", value, ObjectType.string)
        elif self._get_first_names() or self._get_last_names():
            # autofill the FN field from the N field
            names = [self._get_name_prefixes(),
                     self._get_first_names(),
                     self._get_last_names(),
                     self._get_name_suffixes()]
            name = [x for x in names if x]
            value = helpers.list_to_string(names, " ")
        else:  # add an empty FN
            value = ""
        self.vcard.add("FN").value = value

    def _get_names_part(self, part):
        """Get some part of the "N" entry in the vCard as a list

        :param part: the name to get e.g. "prefix" or "given"
        :type part: str
        :returns: a list of entries for this name part
        :rtype: list(str)

        """
        try:
            the_list = getattr(self.vcard.n.value, part)
        except AttributeError:
            return []
        else:
            # check if list only contains empty strings
            if not ''.join(the_list):
                return []
        return the_list if isinstance(the_list, list) else [the_list]

    def _get_name_prefixes(self):
        return self._get_names_part("prefix")

    def _get_first_names(self):
        return self._get_names_part("given")

    def _get_additional_names(self):
        return self._get_names_part("additional")

    def _get_last_names(self):
        return self._get_names_part("family")

    def _get_name_suffixes(self):
        return self._get_names_part("suffix")

    def get_first_name_last_name(self):
        """
        :rtype: str
        """
        names = self._get_first_names() + self._get_additional_names() + \
            self._get_last_names()
        if names:
            return helpers.list_to_string(names, " ")
        return self.formatted_name

    def get_last_name_first_name(self):
        """
        :rtype: str
        """
        last_names = []
        if self._get_last_names():
            last_names += self._get_last_names()
        first_and_additional_names = self._get_first_names() + \
            self._get_additional_names()
        if last_names and first_and_additional_names:
            return "{}, {}".format(
                helpers.list_to_string(last_names, " "),
                helpers.list_to_string(first_and_additional_names, " "))
        if last_names:
            return helpers.list_to_string(last_names, " ")
        if first_and_additional_names:
            return helpers.list_to_string(first_and_additional_names, " ")
        return self.formatted_name

    def _add_name(self, prefix, first_name, additional_name, last_name,
                  suffix):
        name_obj = self.vcard.add('n')
        stringlist = ObjectType.string_or_list_with_strings
        name_obj.value = vobject.vcard.Name(
            prefix=convert_to_vcard("name prefix", prefix, stringlist),
            given=convert_to_vcard("first name", first_name, stringlist),
            additional=convert_to_vcard("additional name", additional_name,
                                        stringlist),
            family=convert_to_vcard("last name", last_name, stringlist),
            suffix=convert_to_vcard("name suffix", suffix, stringlist))

    @property
    def organisations(self):
        """
        :returns: list of organisations, sorted alphabetically
        :rtype: list(list(str))
        """
        return self._get_multi_property("ORG")

    def _add_organisation(self, organisation):
        org_obj = self.vcard.add('org')
        org_obj.value = convert_to_vcard("organisation", organisation,
                                         ObjectType.list_with_strings)
        # check if fn attribute is already present
        if not self.vcard.getChildValue("fn") and self.organisations:
            # if not, set fn to organisation name
            org_value = helpers.list_to_string(self.organisations[0], ", ")
            self.formatted_name = org_value.replace("\n", " ").replace("\\",
                                                                       "")
            showas_obj = self.vcard.add('x-abshowas')
            showas_obj.value = "COMPANY"

    @property
    def titles(self):
        """
        :rtype: list(list(str))
        """
        return self._get_multi_property("TITLE")

    def _add_title(self, title):
        title_obj = self.vcard.add('title')
        title_obj.value = convert_to_vcard("title", title, ObjectType.string)

    @property
    def roles(self):
        """
        :rtype: list(list(str))
        """
        return self._get_multi_property("ROLE")

    def _add_role(self, role):
        role_obj = self.vcard.add('role')
        role_obj.value = convert_to_vcard("role", role, ObjectType.string)

    @property
    def nicknames(self):
        """
        :rtype: list(list(str))
        """
        return self._get_multi_property("NICKNAME")

    def _add_nickname(self, nickname):
        nickname_obj = self.vcard.add('nickname')
        nickname_obj.value = convert_to_vcard("nickname", nickname,
                                              ObjectType.string)

    @property
    def notes(self):
        """
        :rtype: list(list(str))
        """
        return self._get_multi_property("NOTE")

    def _add_note(self, note):
        note_obj = self.vcard.add('note')
        note_obj.value = convert_to_vcard("note", note, ObjectType.string)

    @property
    def webpages(self):
        """
        :rtype: list(str)
        """
        return self._get_multi_property("URL")

    def _add_webpage(self, webpage):
        self._add_labelled_object("url", webpage, True)

    @property
    def categories(self):
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
        categories_obj.value = convert_to_vcard("category", categories,
                                                ObjectType.list_with_strings)

    @property
    def phone_numbers(self):
        """
        :returns: dict of type and phone number list
        :rtype: dict(str, list(str))
        """
        phone_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "TEL":
                # phone types
                type = helpers.list_to_string(
                    self._get_types_for_vcard_object(child, "voice"), ", ")
                if type not in phone_dict:
                    phone_dict[type] = []
                # phone value
                #
                # vcard version 4.0 allows URI scheme "tel" in phone attribute value
                # Doc: https://tools.ietf.org/html/rfc6350#section-6.4.1
                # example: TEL;VALUE=uri;PREF=1;TYPE="voice,home":tel:+1-555-555-5555;ext=5555
                if child.value.lower().startswith("tel:"):
                    # cut off the "tel:" uri prefix
                    phone_dict[type].append(child.value[4:])
                else:
                    # free text field
                    phone_dict[type].append(child.value)
        # sort phone number lists
        for number_list in phone_dict.values():
            number_list.sort()
        return phone_dict

    def _add_phone_number(self, type, number):
        standard_types, custom_types, pref = self._parse_type_value(
            helpers.string_to_list(type, ","), self.phone_types_v4 if
            self.version == "4.0" else self.phone_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for phone number " + number +
                             " is missing.")
        if len(custom_types) > 1:
            raise ValueError("Error: phone number " + number + " got more "
                             "than one custom label: " +
                             helpers.list_to_string(custom_types, ", "))
        phone_obj = self.vcard.add('tel')
        if self.version == "4.0":
            phone_obj.value = "tel:%s" % convert_to_vcard(
                "phone number", number, ObjectType.string)
            phone_obj.params['VALUE'] = ["uri"]
            if pref > 0:
                phone_obj.params['PREF'] = str(pref)
        else:
            phone_obj.value = convert_to_vcard("phone number", number,
                                               ObjectType.string)
            if pref > 0:
                standard_types.append("pref")
        if standard_types:
            phone_obj.params['TYPE'] = standard_types
        if custom_types:
            custom_label_count = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith(
                        "itemtel"):
                    custom_label_count += 1
            group_name = "itemtel%d" % (custom_label_count + 1)
            phone_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = custom_types[0]

    @property
    def emails(self):
        """
        :returns: dict of type and email address list
        :rtype: dict(str, list(str))
        """
        email_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "EMAIL":
                type = helpers.list_to_string(
                    self._get_types_for_vcard_object(child, "internet"), ", ")
                if type not in email_dict:
                    email_dict[type] = []
                email_dict[type].append(child.value)
        # sort email address lists
        for email_list in email_dict.values():
            email_list.sort()
        return email_dict

    def add_email(self, type, address):
        standard_types, custom_types, pref = self._parse_type_value(
            helpers.string_to_list(type, ","), self.email_types_v4 if
            self.version == "4.0" else self.email_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for email address " + address +
                             " is missing.")
        if len(custom_types) > 1:
            raise ValueError("Error: email address " + address + " got more "
                             "than one custom label: " +
                             helpers.list_to_string(custom_types, ", "))
        email_obj = self.vcard.add('email')
        email_obj.value = convert_to_vcard("email address", address,
                                           ObjectType.string)
        if self.version == "4.0":
            if pref > 0:
                email_obj.params['PREF'] = str(pref)
        else:
            if pref > 0:
                standard_types.append("pref")
        if standard_types:
            email_obj.params['TYPE'] = standard_types
        if custom_types:
            custom_label_count = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith(
                        "itememail"):
                    custom_label_count += 1
            group_name = "itememail%d" % (custom_label_count + 1)
            email_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = custom_types[0]

    @property
    def post_addresses(self):
        """
        :returns: dict of type and post address list
        :rtype: dict(str, list(dict(str,list|str)))
        """
        post_adr_dict = {}
        for child in self.vcard.getChildren():
            if child.name == "ADR":
                type = helpers.list_to_string(self._get_types_for_vcard_object(
                    child, "home"), ", ")
                if type not in post_adr_dict:
                    post_adr_dict[type] = []
                post_adr_dict[type].append({"box": child.value.box,
                                            "extended": child.value.extended,
                                            "street": child.value.street,
                                            "code": child.value.code,
                                            "city": child.value.city,
                                            "region": child.value.region,
                                            "country": child.value.country})
        # sort post address lists
        for post_adr_list in post_adr_dict.values():
            post_adr_list.sort(key=lambda x: (
                helpers.list_to_string(x['city'], " ").lower(),
                helpers.list_to_string(x['street'], " ").lower()))
        return post_adr_dict

    def get_formatted_post_addresses(self):
        formatted_post_adr_dict = {}
        for type, post_adr_list in self.post_addresses.items():
            formatted_post_adr_dict[type] = []
            for post_adr in post_adr_list:
                strings = []
                if "street" in post_adr:
                    strings.append(
                        helpers.list_to_string(post_adr.get("street"), "\n"))
                if "box" in post_adr and "extended" in post_adr:
                    strings.append("{} {}".format(
                        helpers.list_to_string(post_adr.get("box"), " "),
                        helpers.list_to_string(post_adr.get("extended"), " ")))
                elif "box" in post_adr:
                    strings.append(
                        helpers.list_to_string(post_adr.get("box"), " "))
                elif "extended" in post_adr:
                    strings.append(
                        helpers.list_to_string(post_adr.get("extended"), " "))
                if "code" in post_adr and "city" in post_adr:
                    strings.append("{} {}".format(
                        helpers.list_to_string(post_adr.get("code"), " "),
                        helpers.list_to_string(post_adr.get("city"), " ")))
                elif "code" in post_adr:
                    strings.append(
                        helpers.list_to_string(post_adr.get("code"), " "))
                elif "city" in post_adr:
                    strings.append(
                        helpers.list_to_string(post_adr.get("city"), " "))
                if "region" in post_adr and "country" in post_adr:
                    strings.append("{}, {}".format(
                        helpers.list_to_string(post_adr.get("region"), " "),
                        helpers.list_to_string(post_adr.get("country"), " ")))
                elif "region" in post_adr:
                    strings.append(
                        helpers.list_to_string(post_adr.get("region"), " "))
                elif "country" in post_adr:
                    strings.append(
                        helpers.list_to_string(post_adr.get("country"), " "))
                formatted_post_adr_dict[type].append('\n'.join(strings))
        return formatted_post_adr_dict

    def _add_post_address(self, type, box, extended, street, code, city,
                          region, country):
        standard_types, custom_types, pref = self._parse_type_value(
            helpers.string_to_list(type, ","),
            self.address_types_v4 if self.version == "4.0" else
            self.address_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for post address " + street +
                             " is missing.")
        if len(custom_types) > 1:
            raise ValueError("Error: post address " + street + " got more "
                             "than one custom " "label: " +
                             helpers.list_to_string(custom_types, ", "))
        adr_obj = self.vcard.add('adr')
        adr_obj.value = vobject.vcard.Address(
            box=convert_to_vcard("box address field", box,
                                 ObjectType.string_or_list_with_strings),
            extended=convert_to_vcard("extended address field", extended,
                                      ObjectType.string_or_list_with_strings),
            street=convert_to_vcard("street", street,
                                    ObjectType.string_or_list_with_strings),
            code=convert_to_vcard("post code", code,
                                  ObjectType.string_or_list_with_strings),
            city=convert_to_vcard("city", city,
                                  ObjectType.string_or_list_with_strings),
            region=convert_to_vcard("region", region,
                                    ObjectType.string_or_list_with_strings),
            country=convert_to_vcard("country", country,
                                     ObjectType.string_or_list_with_strings))
        if self.version == "4.0":
            if pref > 0:
                adr_obj.params['PREF'] = str(pref)
        else:
            if pref > 0:
                standard_types.append("pref")
        if standard_types:
            adr_obj.params['TYPE'] = standard_types
        if custom_types:
            custom_label_count = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith(
                        "itemadr"):
                    custom_label_count += 1
            group_name = "itemadr%d" % (custom_label_count + 1)
            adr_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = custom_types[0]


class YAMLEditable(VCardWrapper):

    def __init__(self, vcard, supported_private_objects=None, version=None,
                 localize_dates=False):
        """Initialize atributes needed for yaml conversions

        :param supported_private_objects: the list of private property names
            that will be loaded from the actual vcard and represented in this
            pobject
        :type supported_private_objects: list(str) or NoneType
        :param version: the version of the RFC to use in this card
        :type version: str or None
        :param bool localize_dates: should the formatted output of anniversary
            and birthday be localized or should the isoformat be used instead
        """
        self.supported_private_objects = supported_private_objects or []
        self.localize_dates = localize_dates
        super().__init__(vcard, version)

    #####################
    # getters and setters
    #####################

    def _get_private_objects(self):
        """
        :rtype: dict(str, list(str))
        """
        supported = [x.lower() for x in self.supported_private_objects]
        private_objects = {}
        for child in self.vcard.getChildren():
            lower = child.name.lower()
            if lower.startswith("x-") and lower[2:] in supported:
                key_index = supported.index(lower[2:])
                key = self.supported_private_objects[key_index]
                if key not in private_objects:
                    private_objects[key] = []
                ablabel = self._get_ablabel(child)
                private_objects[key].append(
                    ablabel + (": " if ablabel else "") + child.value)
        # sort private object lists
        for value in private_objects.values():
            value.sort()
        logging.debug("Returning private objects %s", private_objects)
        return private_objects

    def _add_private_object(self, key, value):
        self._add_labelled_object('X-' + key.upper(), value)

    def get_formatted_anniversary(self):
        return self._format_date_object(self.anniversary, self.localize_dates)

    def get_formatted_birthday(self):
        return self._format_date_object(self.birthday, self.localize_dates)

    #######################
    # object helper methods
    #######################

    @staticmethod
    def _format_date_object(date, localize):
        if not date:
            return ""
        if isinstance(date, str):
            return date
        if date.year == 1900 and date.month != 0 and date.day != 0 \
                and date.hour == 0 and date.minute == 0 and date.second == 0:
            return "--%.2d-%.2d" % (date.month, date.day)
        if (date.tzname() and date.tzname()[3:]) or (
                date.hour != 0 or date.minute != 0 or date.second != 0):
            if localize:
                return date.strftime(locale.nl_langinfo(locale.D_T_FMT))
            utc_offset = -time.timezone / 60 / 60
            return date.strftime("%Y-%m-%dT%H:%M:%S+{}:00".format(
                str(int(utc_offset)).zfill(2)))
        if localize:
            return date.strftime(locale.nl_langinfo(locale.D_FMT))
        return date.strftime("%Y-%m-%d")

    @staticmethod
    def _filter_invalid_tags(contents):
        for pat, repl in [('aim', 'AIM'), ('gadu', 'GADUGADU'),
                          ('groupwise', 'GROUPWISE'), ('icq', 'ICQ'),
                          ('xmpp', 'JABBER'), ('msn', 'MSN'),
                          ('yahoo', 'YAHOO'), ('skype', 'SKYPE'),
                          ('irc', 'IRC'), ('sip', 'SIP')]:
            contents = re.sub('X-messaging/'+pat+'-All', 'X-'+repl, contents,
                              flags=re.IGNORECASE)
        return contents

    @staticmethod
    def _parse_yaml(input):
        """Parse a YAML document into a dictinary and validate the data to some
        degree.

        :param str input: the YAML document to parse
        :returns dict: the parsed datastructure
        """
        yaml_parser = YAML(typ='base')
        # parse user input string
        try:
            contact_data = yaml_parser.load(input)
        except (ruamel.yaml.parser.ParserError,
                ruamel.yaml.scanner.ScannerError) as err:
            raise ValueError(err)
        else:
            if not contact_data:
                raise ValueError("Error: Found no contact information")

        # check for available data
        # at least enter name or organisation
        if not contact_data.get("First name") \
                and not contact_data.get("Last name") \
                and not contact_data.get("Organisation"):
            raise ValueError(
                "Error: You must either enter a name or an organisation")
        return contact_data

    @staticmethod
    def _set_string_list(setter, key, data):
        """Prepocess a string or list and set each value with the given setter

        :param callable setter: the setter method to add a value to a card
        :param value: the new value to set
        :type value: str or list(str)
        :returns: None
        """
        value = data.get(key)
        if value:
            if isinstance(value, str):
                setter(value)
            elif isinstance(value, list):
                for v in value:
                    if v:
                        setter(v)
            else:
                raise ValueError(
                    "{} must be a string or a list of strings".format(key))

    def _set_date(self, target, key, data):
        new = data.get(key)
        if not new:
            return
        if not isinstance(new, str):
            raise ValueError("Error: {} must be a string object.".format(key))
        if re.match(r"^text[\s]*=.*$", new):
            if self.version == "4.0":
                v = ', '.join(x.strip() for x in re.split(r"text[\s]*=", new)
                              if x.strip())
                if v:
                    setattr(self, target, v)
                return
            raise ValueError("Error: Free text format for {} only usable with "
                             "vcard version 4.0.".format(key.lower()))
        if re.match(r"^--\d\d-?\d\d$", new) and self.version != "4.0":
            raise ValueError(
                "Error: {} format --mm-dd and --mmdd only usable with "
                "vcard version 4.0. You may use 1900 as placeholder, if "
                "the year is unknown.".format(key))
        try:
            v = helpers.string_to_date(new)
            if v:
                setattr(self, target, v)
            return
        except ValueError:
            pass
        raise ValueError("Error: Wrong {} format or invalid date\n"
                         "Use format yyyy-mm-dd or "
                         "yyyy-mm-ddTHH:MM:SS".format(key.lower()))

    def update(self, input):
        """Update this vcard with some yaml input

        :param str input: a yaml string to parse and then use to update self
        :returns: None
        """
        contact_data = self._parse_yaml(input)
        # update rev
        self._update_revision()

        # name
        self._delete_vcard_object("N")
        # although the "n" attribute is not explisitely required by the vcard
        # specification,
        # the vobject library throws an exception, if it doesn't exist
        # so add the name regardless if it's empty or not
        self._add_name(
            contact_data.get("Prefix", ""), contact_data.get("First name", ""),
            contact_data.get("Additional", ""),
            contact_data.get("Last name", ""), contact_data.get("Suffix", ""))
        if "Formatted name" in contact_data:
            self.formatted_name = contact_data.get("Formatted name")
        if not self.formatted_name:
            # Trigger the auto filling code in the setter.
            self.formatted_name = ""

        # nickname
        self._delete_vcard_object("NICKNAME")
        self._set_string_list(self._add_nickname, "Nickname", contact_data)

        # organisation
        self._delete_vcard_object("ORG")
        self._delete_vcard_object("X-ABSHOWAS")
        self._set_string_list(self._add_organisation, "Organisation",
                              contact_data)

        # role
        self._delete_vcard_object("ROLE")
        self._set_string_list(self._add_role, "Role", contact_data)

        # title
        self._delete_vcard_object("TITLE")
        self._set_string_list(self._add_title, "Title", contact_data)

        # phone
        self._delete_vcard_object("TEL")
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
        self._delete_vcard_object("EMAIL")
        if contact_data.get("Email"):
            if isinstance(contact_data.get("Email"), dict):
                for type, email_list in contact_data.get("Email").items():
                    if isinstance(email_list, str):
                        email_list = [email_list]
                    if isinstance(email_list, list):
                        for email in email_list:
                            if email:
                                self.add_email(type, email)
                    else:
                        raise ValueError(
                            "Error: got no email or list of emails for the "
                            "email address type " + type)
            else:
                raise ValueError(
                    "Error: missing type value for email address field")

        # post addresses
        self._delete_vcard_object("ADR")
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
                                               "Country"] and value:
                                        address_not_empty = True
                                        break
                                if address_not_empty:
                                    self._add_post_address(
                                        type, post_adr.get("Box", ""),
                                        post_adr.get("Extended", ""),
                                        post_adr.get("Street", ""),
                                        post_adr.get("Code", ""),
                                        post_adr.get("City", ""),
                                        post_adr.get("Region", ""),
                                        post_adr.get("Country", ""))
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
        self._delete_vcard_object("CATEGORIES")
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
        self._delete_vcard_object("URL")
        self._set_string_list(self._add_webpage, "Webpage", contact_data)

        # anniversary
        self._delete_vcard_object("ANNIVERSARY")
        self._delete_vcard_object("X-ANNIVERSARY")
        self._set_date('anniversary', 'Anniversary', contact_data)

        # birthday
        self._delete_vcard_object("BDAY")
        self._set_date('birthday', 'Birthday', contact_data)

        # private objects
        for supported in self.supported_private_objects:
            self._delete_vcard_object("X-{}".format(supported.upper()))
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
        self._delete_vcard_object("NOTE")
        self._set_string_list(self._add_note, "Note", contact_data)

    def get_template(self):
        strings = []
        for line in helpers.get_new_contact_template().splitlines():
            if line.startswith("#"):
                strings.append(line)
            elif line == "":
                strings.append(line)

            elif line.lower().startswith("formatted name"):
                strings += helpers.convert_to_yaml(
                    "Formatted name", self.formatted_name, 0, 15, True)
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
                    "Nickname", self.nicknames, 0, 9, True)

            elif line.lower().startswith("organisation"):
                strings += helpers.convert_to_yaml(
                    "Organisation", self.organisations, 0, 13, True)
            elif line.lower().startswith("title"):
                strings += helpers.convert_to_yaml(
                    "Title", self.titles, 0, 6, True)
            elif line.lower().startswith("role"):
                strings += helpers.convert_to_yaml(
                    "Role", self.roles, 0, 6, True)

            elif line.lower().startswith("phone"):
                strings.append("Phone :")
                if not self.phone_numbers:
                    strings.append("    cell : ")
                    strings.append("    home : ")
                else:
                    longest_key = max(self.phone_numbers.keys(), key=len)
                    for type, number_list in sorted(
                            self.phone_numbers.items(),
                            key=lambda k: k[0].lower()):
                        strings += helpers.convert_to_yaml(
                            type, number_list, 4, len(longest_key) + 1, True)

            elif line.lower().startswith("email"):
                strings.append("Email :")
                if not self.emails:
                    strings.append("    home : ")
                    strings.append("    work : ")
                else:
                    longest_key = max(self.emails.keys(), key=len)
                    for type, email_list in sorted(self.emails.items(),
                                                   key=lambda k: k[0].lower()):
                        strings += helpers.convert_to_yaml(
                            type, email_list, 4, len(longest_key) + 1, True)

            elif line.lower().startswith("address"):
                strings.append("Address :")
                if not self.post_addresses:
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
                            self.post_addresses.items(),
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
                            object,
                            self._get_private_objects().get(object, ""), 4,
                            len(longest_key) + 1, True)

            elif line.lower().startswith("anniversary"):
                anniversary = self.anniversary
                if anniversary:
                    if isinstance(anniversary, str):
                        strings.append("Anniversary : text= %s" % anniversary)
                    elif (anniversary.year == 1900 and anniversary.month != 0
                          and anniversary.day != 0 and anniversary.hour == 0
                          and anniversary.minute == 0
                          and anniversary.second == 0
                          and self.version == "4.0"):
                        strings.append("Anniversary : --%.2d-%.2d"
                                       % (anniversary.month, anniversary.day))
                    elif ((anniversary.tzname() and anniversary.tzname()[3:])
                          or anniversary.hour != 0 or anniversary.minute != 0
                          or anniversary.second != 0):
                        strings.append("Anniversary : %s" %
                                       anniversary.isoformat())
                    else:
                        strings.append("Anniversary : %.4d-%.2d-%.2d" % (
                            anniversary.year, anniversary.month,
                            anniversary.day))
                else:
                    strings.append("Anniversary : ")
            elif line.lower().startswith("birthday"):
                birthday = self.birthday
                if birthday:
                    if isinstance(birthday, str):
                        strings.append("Birthday : text= %s" % birthday)
                    elif birthday.year == 1900 and birthday.month != 0 and \
                            birthday.day != 0 and birthday.hour == 0 and \
                            birthday.minute == 0 and birthday.second == 0 and \
                            self.version == "4.0":
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
                    "Categories", self.categories, 0, 11, True)
            elif line.lower().startswith("note"):
                strings += helpers.convert_to_yaml(
                    "Note", self.notes, 0, 5, True)
            elif line.lower().startswith("webpage"):
                strings += helpers.convert_to_yaml(
                    "Webpage", self.webpages, 0, 8, True)
        # posix standard: eof char must be \n
        return '\n'.join(strings) + "\n"


class CarddavObject(YAMLEditable):

    def __init__(self, vcard, address_book, filename,
                 supported_private_objects=None, vcard_version=None,
                 localize_dates=False):
        """Initialize the vcard object.

        :param vobject.vCard vcard: the vCard to wrap
        :param address_book.AddressBook address_book: a reference to the
            address book where this vcard is stored
        :param str filename: the path to the file where this vcard is stored
        :param supported_private_objects: the list of private property names
            that will be loaded from the actual vcard and represented in this
            pobject
        :type supported_private_objects: list(str) or NoneType
        :param vcard_version: the version of the RFC to use
        :type vcard_version: str or None
        :param localize_dates: should the formatted output of anniversary and
            birthday be localized or should the isoformat be used instead
        :type localize_dates: bool

        """
        self.address_book = address_book
        self.filename = filename
        super().__init__(vcard, supported_private_objects, vcard_version,
                         localize_dates)

    #######################################
    # factory methods to create new contact
    #######################################

    @classmethod
    def new(cls, address_book, supported_private_objects=None, version=None,
            localize_dates=False):
        """Create a new CarddavObject from scratch"""
        vcard = vobject.vCard()
        uid = helpers.get_random_uid()
        filename = os.path.join(address_book.path, uid + ".vcf")
        card = cls(vcard, address_book, filename, supported_private_objects,
                   version, localize_dates)
        card.uid = uid
        return card

    @classmethod
    def from_file(cls, address_book, filename, query,
                  supported_private_objects=None, localize_dates=False):
        """Load a CarddavObject object from a .vcf file if the plain file
        matches the query.

        :param address_book.AddressBook address_book: the address book where
            this contact is stored
        :param str filename: the file name of the .vcf file
        :param re.Pattern|str|NoneType query: the regex to search in the source
            file or None to load the file unconditionally
        :param list(str)|NoneType supported_private_objects: the list of
            private property names that will be loaded from the actual vcard
            and represented in this pobject
        :param str|NoneType vcard_version: the version of the RFC to use
        :param bool localize_dates: should the formatted output of anniversary
            and birthday be localized or should the isoformat be used instead
        :returns: the loaded CarddavObject or None if the file didn't match
        :rtype: CarddavObject or NoneType
        """
        with open(filename, "r") as file:
            contents = file.read()
        if query is None or \
                re.search(query, contents, re.IGNORECASE | re.DOTALL):
            try:
                vcard = vobject.readOne(contents)
            except Exception:
                logging.warning("Filtering some problematic tags from %s",
                                filename)
                # if creation fails, try to repair some vcard attributes
                vcard = vobject.readOne(cls._filter_invalid_tags(contents))
            return cls(vcard, address_book, filename, supported_private_objects,
                       None, localize_dates)

    @classmethod
    def from_yaml(cls, address_book, yaml, supported_private_objects=None,
                  version=None, localize_dates=False):
        """Use this if you want to create a new contact from user input."""
        contact = cls.new(address_book, supported_private_objects, version,
                          localize_dates=localize_dates)
        contact.update(yaml)
        return contact

    @classmethod
    def clone_with_yaml_update(cls, contact, yaml, localize_dates=False):
        """
        Use this if you want to clone an existing contact and replace its data
        with new user input in one step.
        """
        contact = cls(
            copy.deepcopy(contact.vcard), address_book=contact.address_book,
            filename=contact.filename,
            supported_private_objects=contact.supported_private_objects,
            localize_dates=localize_dates)
        contact.update(yaml)
        return contact

    ######################################
    # overwrite some default class methods
    ######################################

    def __eq__(self, other):
        return isinstance(other, CarddavObject) and \
            self.print_vcard(show_address_book=False, show_uid=False) == \
            other.print_vcard(show_address_book=False, show_uid=False)

    def __ne__(self, other):
        return not self == other

    def print_vcard(self, show_address_book=True, show_uid=True):
        strings = []

        # Every vcard must have an FN field per the RFC.
        strings.append("Name: {}".format(self.formatted_name))
        # name
        if self._get_first_names() or self._get_last_names():
            names = self._get_name_prefixes() + self._get_first_names() + \
                self._get_additional_names() + self._get_last_names() + \
                self._get_name_suffixes()
            strings.append("Full name: {}".format(
                helpers.list_to_string(names, " ")))
        # organisation
        if self.organisations:
            strings += helpers.convert_to_yaml(
                "Organisation", self.organisations, 0, -1, False)

        # address book name
        if show_address_book:
            strings.append("Address book: %s" % self.address_book)

        # person related information
        if (self.birthday is not None or self.anniversary is not None
                or self.nicknames or self.roles or self.titles):
            strings.append("General:")
            if self.anniversary:
                strings.append("    Anniversary: %s"
                               % self.get_formatted_anniversary())
            if self.birthday:
                strings.append(
                    "    Birthday: {}".format(self.get_formatted_birthday()))
            if self.nicknames:
                strings += helpers.convert_to_yaml(
                    "Nickname", self.nicknames, 4, -1, False)
            if self.roles:
                strings += helpers.convert_to_yaml(
                    "Role", self.roles, 4, -1, False)
            if self.titles:
                strings += helpers.convert_to_yaml(
                    "Title", self.titles, 4, -1, False)

        # phone numbers
        if self.phone_numbers:
            strings.append("Phone")
            for type, number_list in sorted(self.phone_numbers.items(),
                                            key=lambda k: k[0].lower()):
                strings += helpers.convert_to_yaml(
                    type, number_list, 4, -1, False)

        # email addresses
        if self.emails:
            strings.append("E-Mail")
            for type, email_list in sorted(self.emails.items(),
                                           key=lambda k: k[0].lower()):
                strings += helpers.convert_to_yaml(
                    type, email_list, 4, -1, False)

        # post addresses
        if self.post_addresses:
            strings.append("Address")
            for type, post_adr_list in sorted(
                    self.get_formatted_post_addresses().items(),
                    key=lambda k: k[0].lower()):
                strings += helpers.convert_to_yaml(
                    type, post_adr_list, 4, -1, False)

        # private objects
        if self._get_private_objects().keys():
            strings.append("Private:")
            for object in self.supported_private_objects:
                if object in self._get_private_objects():
                    strings += helpers.convert_to_yaml(
                        object, self._get_private_objects().get(object), 4, -1,
                        False)

        # misc stuff
        if self.categories or self.webpages or self.notes or (
                show_uid and self.uid):
            strings.append("Miscellaneous")
            if show_uid and self.uid:
                strings.append("    UID: {}".format(self.uid))
            if self.categories:
                strings += helpers.convert_to_yaml(
                    "Categories", self.categories, 4, -1, False)
            if self.webpages:
                strings += helpers.convert_to_yaml(
                    "Webpage", self.webpages, 4, -1, False)
            if self.notes:
                strings += helpers.convert_to_yaml(
                    "Note", self.notes, 4, -1, False)
        return '\n'.join(strings)

    def write_to_file(self, overwrite=False):
        # make sure, that every contact contains a uid
        if not self.uid:
            self.uid = helpers.get_random_uid()
        try:
            with atomic_write(self.filename, overwrite=overwrite) as f:
                f.write(self.vcard.serialize())
        except vobject.base.ValidateError as err:
            print("Error: Vcard is not valid.\n{}".format(err))
            sys.exit(4)
        except IOError as err:
            print("Error: Can't write\n{}".format(err))
            sys.exit(4)
        except OSError as err:
            print("Error: vcard with the file name {} already exists\n"
                  "{}".format(os.path.basename(self.filename), err))
            sys.exit(4)

    def delete_vcard_file(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)
        else:
            print("Error: Vcard file {} does not exist.".format(self.filename))
            sys.exit(4)
