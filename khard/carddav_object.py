"""Classes and logic to handle vCards in khard.

This module explicitly supports the vCard specifications version 3.0 and 4.0
which can be found here:
- version 3.0: https://tools.ietf.org/html/rfc2426
- version 4.0: https://tools.ietf.org/html/rfc6350
"""

import copy
import datetime
import io
import locale
import logging
import os
import re
import sys
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, \
    TypeVar, Union, Sequence, overload

from atomicwrites import atomic_write
from ruamel import yaml
from ruamel.yaml import YAML
import vobject

from . import address_book  # pylint: disable=unused-import # for type checking
from . import helpers
from .helpers.typing import (Date, ObjectType, PostAddress, StrList,
    convert_to_vcard, list_to_string, string_to_date, string_to_list)
from .query import AnyQuery, Query


logger = logging.getLogger(__name__)
T = TypeVar("T")


@overload
def multi_property_key(item: str) -> Tuple[Literal[0], str]: ...
@overload
def multi_property_key(item: Dict[T, Any]) -> Tuple[Literal[1], T]: ...
def multi_property_key(item: Union[str, Dict[T, Any]]
                       ) -> Tuple[int, Union[T, str]]:
    """Key function to pass to sorted(), allowing sorting of dicts with lists
    and strings. Dicts will be sorted by their label, after other types.

    :param item: member of the list being sorted
    :type item: a dict with a single entry or any sortable type
    :returns: a pair, the first item is int(isinstance(item, dict).
        The second is either the key from the dict or the unchanged item if it
        is not a dict.
    """
    if isinstance(item, dict):
        return (1, next(iter(item)))
    return (0, item)


class VCardWrapper:
    """Wrapper class around a vobject.vCard object.

    This class can wrap a single vCard and presents its data in a manner
    suitable for khard.  Additionally some details of the vCard specifications
    in RFC 2426 (version 3.0) and RFC 6350 (version 4.0) that are not enforced
    by the vobject library are enforced here.
    """

    _default_kind = "individual"
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

    def __init__(self, vcard: vobject.vCard, version: Optional[str] = None
                 ) -> None:
        """Initialize the wrapper around the given vcard.

        :param vobject.vCard vcard: the vCard to wrap
        :param version: the version of the RFC to use (if the card has none)
        """
        self.vcard = vcard
        if not self.version:
            version = version or self._default_version
            logger.warning("Wrapping unversioned vCard object, setting "
                           "version to %s.", version)
            self.version = version
        elif self.version not in self._supported_versions:
            logger.warning("Wrapping vCard with unsupported version %s, this "
                           "might change any incompatible attributes.",
                           self.version)

    def __str__(self) -> str:
        return self.formatted_name

    def _get_string_field(self, field: str) -> str:
        """Get a string field from the underlying vCard.

        :param field: the field value to get
        :returns: the field value or the empty string
        """
        try:
            return getattr(self.vcard, field).value
        except AttributeError:
            return ""

    def _get_multi_property(self, name: str) -> List:
        """Get a vCard property that can exist more than once.

        It does not matter what the individual vcard properties store as their
        value.  This function returns them untouched inside an aggregating
        list.

        If the property is part of a group containing exactly two items, with
        exactly one ABLABEL. the property will be prefixed with that ABLABEL.

        :param name: the name of the property (should be UPPER case)
        :returns: the values from all occurrences of the named property
        """
        values = []
        for child in self.vcard.getChildren():
            if child.name == name:
                ablabel = self._get_ablabel(child)
                if ablabel:
                    values.append({ablabel: child.value})
                else:
                    values.append(child.value)
        return sorted(values, key=multi_property_key)

    def _delete_vcard_object(self, name: str) -> None:
        """Delete all fields with the given name from the underlying vCard.

        If a field that will be deleted is in a group with an X-ABLABEL field,
        that X-ABLABEL field will also be deleted.  These fields are commonly
        added by the Apple address book to attach custom labels to some fields.

        :param name: the name of the fields to delete
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
    def _parse_type_value(types: Sequence[str], supported_types: Sequence[str]
                          ) -> Tuple[List[str], List[str], int]:
        """Parse type value of phone numbers, email and post addresses.

        :param types: list of type values
        :param supported_types: all allowed standard types
        :returns: tuple of standard and custom types and pref integer
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

    def _get_types_for_vcard_object(self, object: vobject.base.ContentLine,
                                    default_type: str) -> List[str]:
        """get list of types for phone number, email or post address

        :param object: vcard class object
        :param default_type: use if the object contains no type
        :returns: list of type labels
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
            type_list.append("pref={}".format(
                int(object.params.get("PREF")[0])))
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
    def version(self) -> str:
        return self._get_string_field("version")

    @version.setter
    def version(self, value: str) -> None:
        if value not in self._supported_versions:
            logger.warning("Setting vcard version to unsupported version %s",
                           value)
        # All vCards should only always have one version, this is a requirement
        # for version 4 but also makes sense for all other versions.
        self._delete_vcard_object("VERSION")
        version = self.vcard.add("version")
        version.value = convert_to_vcard("version", value, ObjectType.str)

    @property
    def uid(self) -> str:
        return self._get_string_field("uid")

    @uid.setter
    def uid(self, value: str) -> None:
        # All vCards should only always have one UID, this is a requirement
        # for version 4 but also makes sense for all other versions.
        self._delete_vcard_object("UID")
        uid = self.vcard.add('uid')
        uid.value = convert_to_vcard("uid", value, ObjectType.str)

    def _update_revision(self) -> None:
        """Generate a new REV field for the vCard, replace any existing

        All vCards should only always have one revision, this is a
        requirement for version 4 but also makes sense for all other
        versions.

        :rtype: NoneType
        """
        self._delete_vcard_object("REV")
        rev = self.vcard.add('rev')
        rev.value = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")

    @property
    def birthday(self) -> Optional[Date]:
        """Return the birthday as a datetime object or a string depending on
        whether it is of type text or not.  If no birthday is present in the
        vcard None is returned.

        :returns: contacts birthday or None if not available
        """
        # vcard 4.0 could contain a single text value
        try:
            if self.vcard.bday.params.get("VALUE")[0] == "text":
                return self.vcard.bday.value
        except (AttributeError, IndexError, TypeError):
            pass
        # else try to convert to a datetime object
        try:
            return string_to_date(self.vcard.bday.value)
        except (AttributeError, ValueError):
            pass
        return None

    @birthday.setter
    def birthday(self, date: Date) -> None:
        """Store the given date as BDAY in the vcard.

        :param date: the new date to store as birthday
        """
        value, text = self._prepare_birthday_value(date)
        if value is None:
            logger.warning('Failed to set anniversary to %s', date)
            return
        bday = self.vcard.add('bday')
        bday.value = value
        if text:
            bday.params['VALUE'] = ['text']

    @property
    def anniversary(self) -> Optional[Date]:
        """
        :returns: contacts anniversary or None if not available
        """
        # vcard 4.0 could contain a single text value
        try:
            if self.vcard.anniversary.params.get("VALUE")[0] == "text":
                return self.vcard.anniversary.value
        except (AttributeError, IndexError, TypeError):
            pass
        # else try to convert to a datetime object
        try:
            return string_to_date(self.vcard.anniversary.value)
        except (AttributeError, ValueError):
            # vcard 3.0: x-anniversary (private object)
            try:
                return string_to_date(self.vcard.x_anniversary.value)
            except (AttributeError, ValueError):
                pass
        return None

    @anniversary.setter
    def anniversary(self, date: Date) -> None:
        value, text = self._prepare_birthday_value(date)
        if value is None:
            logger.warning('Failed to set anniversary to %s', date)
            return
        if text:
            anniversary = self.vcard.add('anniversary')
            anniversary.params['VALUE'] = ['text']
            anniversary.value = value
        elif self.version == "4.0":
            self.vcard.add('anniversary').value = value
        else:
            self.vcard.add('x-anniversary').value = value

    def _get_ablabel(self, item: vobject.base.ContentLine) -> str:
        """Get an ABLABEL for a specified item in the vCard.
        Will return the ABLABEL only if the item is part of a group with
        exactly two items, exactly one of which is an ABLABEL.

        :param item: the item to be labelled
        :returns: the ABLABEL in the circumstances above or an empty string
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

    def _get_new_group(self, group_type: str = "") -> str:
        """Get an unused group name for adding new groups. Uses the form
        item123 or itemgroup_type123 if a grouptype is specified.

        :param group_type: (Optional) a string to add between "item" and
            the number
        :returns: the name of the first unused group of the specified form
        """
        counter = 1
        while True:
            group_name = "item{}{}".format(group_type, counter)
            for child in self.vcard.getChildren():
                if child.group and child.group == group_name:
                    counter += 1
                    break
            else:
                return group_name

    def _add_labelled_object(
            self, obj_type: str, user_input, name_groups: bool = False,
            allowed_object_type: ObjectType = ObjectType.str) -> None:
        """Add an object to the VCARD. If user_input is a dict, the object will
         be added to a group with an ABLABEL created from the key of the dict.

        :param obj_type: type of object to add to the VCARD.
        :param user_input: Contents of the object to add. If a dict
        :type user_input: str or list(str) or dict(str) or dict(list(str))
        :param name_groups: (Optional) If True, use the obj_type in the
            group name for labelled objects.
        :param allowed_object_type: (Optional) set the accepted return type
            for vcard attribute
        """
        obj = self.vcard.add(obj_type)
        if isinstance(user_input, dict):
            if len(user_input) > 1:
                raise ValueError(
                    "Error: {} must be a string or a dict containing one "
                    "key/value pair.".format(obj_type))
            label = list(user_input)[0]
            group_name = self._get_new_group(obj_type if name_groups else "")
            obj.group = group_name
            obj.value = convert_to_vcard(obj_type, user_input[label],
                                         allowed_object_type)
            ablabel_obj = self.vcard.add('X-ABLABEL')
            ablabel_obj.group = group_name
            ablabel_obj.value = label
        else:
            obj.value = convert_to_vcard(obj_type, user_input,
                                         allowed_object_type)

    def _prepare_birthday_value(self, date: Date) -> Tuple[Optional[str],
                                                           bool]:
        """Prepare a value to be stored in a BDAY or ANNIVERSARY attribute.

        :param date: the date like value to be stored
        :returns: the object to set as the .value for the attribute and whether
            it should be stored as plain text
        :rtype: tuple(str,bool)
        """
        if isinstance(date, str):
            if self.version == "4.0":
                return date.strip(), True
            return None, False
        tz = date.tzname()
        if date.year == 1900 and date.month != 0 and date.day != 0 \
                and date.hour == 0 and date.minute == 0 and date.second == 0 \
                and self.version == "4.0":
            fmt = '--%m%d'
        elif tz and tz[3:]:
            if self.version == "4.0":
                fmt = "%Y%m%dT%H%M%S{}".format(tz[3:])
            else:
                fmt = "%FT%T{}".format(tz[3:])
        elif date.hour != 0 or date.minute != 0 or date.second != 0:
            if self.version == "4.0":
                fmt = "%Y%m%dT%H%M%SZ"
            else:
                fmt = "%FT%TZ"
        else:
            if self.version == "4.0":
                fmt = "%Y%m%d"
            else:
                fmt = "%F"
        return date.strftime(fmt), False

    @property
    def kind(self) -> str:
        kind = self._get_string_field("kind") or self._default_kind
        return kind if kind != "org" else "organisation"

    @property
    def formatted_name(self) -> str:
        return self._get_string_field("fn")

    @formatted_name.setter
    def formatted_name(self, value: str) -> None:
        """Set the FN field to the new value.

        All previously existing FN fields are deleted.  Version 4 of the specs
        requires the vCard to only have one FN field.  For other versions we
        enforce this equally.

        :param str value: the new formatted name
        :returns: None
        """
        self._delete_vcard_object("FN")
        if value:
            final = convert_to_vcard("FN", value, ObjectType.str)
        elif self._get_first_names() or self._get_last_names():
            # autofill the FN field from the N field
            names = [self._get_name_prefixes(), self._get_first_names(),
                     self._get_last_names(), self._get_name_suffixes()]
            names = [x for x in names if x]
            final = list_to_string(names, " ")
        else:  # add an empty FN
            final = ""
        self.vcard.add("FN").value = final

    def _get_names_part(self, part: str) -> List[str]:
        """Get some part of the "N" entry in the vCard as a list

        :param part: the name to get e.g. "prefix" or "given"
        :returns: a list of entries for this name part
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

    def _get_name_prefixes(self) -> List[str]:
        return self._get_names_part("prefix")

    def _get_first_names(self) -> List[str]:
        return self._get_names_part("given")

    def _get_additional_names(self) -> List[str]:
        return self._get_names_part("additional")

    def _get_last_names(self) -> List[str]:
        return self._get_names_part("family")

    def _get_name_suffixes(self) -> List[str]:
        return self._get_names_part("suffix")

    def get_first_name_last_name(self) -> str:
        """Compute the full name of the contact by joining first, additional
        and last names together
        """
        names = self._get_first_names() + self._get_additional_names() + \
            self._get_last_names()
        if names:
            return list_to_string(names, " ")
        return self.formatted_name

    def get_last_name_first_name(self) -> str:
        """Compute the full name of the contact by joining the last names and
        then after a comma the first and additional names together
        """
        last_names: List[str] = []
        if self._get_last_names():
            last_names += self._get_last_names()
        first_and_additional_names = self._get_first_names() + \
            self._get_additional_names()
        if last_names and first_and_additional_names:
            return "{}, {}".format(
                list_to_string(last_names, " "),
                list_to_string(first_and_additional_names, " "))
        if last_names:
            return list_to_string(last_names, " ")
        if first_and_additional_names:
            return list_to_string(first_and_additional_names, " ")
        return self.formatted_name

    @property
    def first_name(self) -> str:
        return list_to_string(self._get_first_names(), " ")

    @property
    def last_name(self) -> str:
        return list_to_string(self._get_last_names(), " ")

    def _add_name(self, prefix: StrList, first_name: StrList,
                  additional_name: StrList, last_name: StrList,
                  suffix: StrList) -> None:
        """Add an N entry to the vCard. No old entries are affected.

        :param prefix:
        :param first_name:
        :param additional_name:
        :param last_name:
        :param suffix:
        """
        name_obj = self.vcard.add('n')
        name_obj.value = vobject.vcard.Name(
            prefix=convert_to_vcard("name prefix", prefix, ObjectType.both),
            given=convert_to_vcard("first name", first_name, ObjectType.both),
            additional=convert_to_vcard("additional name", additional_name,
                                        ObjectType.both),
            family=convert_to_vcard("last name", last_name, ObjectType.both),
            suffix=convert_to_vcard("name suffix", suffix, ObjectType.both))

    @property
    def organisations(self) -> List[Union[List[str], Dict[str, List[str]]]]:
        """
        :returns: list of organisations, sorted alphabetically
        """
        return self._get_multi_property("ORG")

    def _add_organisation(self, organisation: StrList) -> None:
        """Add one ORG entry to the underlying vcard

        :param organisation: the value to add
        """
        self._add_labelled_object("org", organisation, True, ObjectType.list)
        # check if fn attribute is already present
        if not self.vcard.getChildValue("fn") and self.organisations:
            # if not, set fn to organisation name
            first_org = self.organisations[0]
            if isinstance(first_org, dict):
                first_org = list(first_org.values())[0]
            org_value = list_to_string(first_org, ", ")
            self.formatted_name = org_value.replace("\n", " ").replace("\\",
                                                                       "")
            showas_obj = self.vcard.add('x-abshowas')
            showas_obj.value = "COMPANY"

    @property
    def titles(self) -> List[Union[str, Dict[str, str]]]:
        return self._get_multi_property("TITLE")

    def _add_title(self, title) -> None:
        self._add_labelled_object("title", title, True)

    @property
    def roles(self) -> List[Union[str, Dict[str, str]]]:
        return self._get_multi_property("ROLE")

    def _add_role(self, role) -> None:
        self._add_labelled_object("role", role, True)

    @property
    def nicknames(self) -> List[Union[str, Dict[str, str]]]:
        return self._get_multi_property("NICKNAME")

    def _add_nickname(self, nickname) -> None:
        self._add_labelled_object("nickname", nickname, True)

    @property
    def notes(self) -> List[Union[str, Dict[str, str]]]:
        return self._get_multi_property("NOTE")

    def _add_note(self, note) -> None:
        self._add_labelled_object("note", note, True)

    @property
    def webpages(self) -> List[Union[str, Dict[str, str]]]:
        return self._get_multi_property("URL")

    def _add_webpage(self, webpage) -> None:
        self._add_labelled_object("url", webpage, True)

    @property
    def categories(self) -> Union[List[str], List[List[str]]]:
        category_list = []
        for child in self.vcard.getChildren():
            if child.name == "CATEGORIES":
                value = child.value
                category_list.append(
                    value if isinstance(value, list) else [value])
        if len(category_list) == 1:
            return category_list[0]
        return sorted(category_list)

    def _add_category(self, categories: List[str]) -> None:
        """Add categories to the vCard

        :param categories:
        """
        categories_obj = self.vcard.add('categories')
        categories_obj.value = convert_to_vcard("category", categories,
                                                ObjectType.list)

    @property
    def phone_numbers(self) -> Dict[str, List[str]]:
        """
        :returns: dict of type and phone number list
        """
        phone_dict: Dict[str, List[str]] = {}
        for child in self.vcard.getChildren():
            if child.name == "TEL":
                # phone types
                type = list_to_string(
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

    def _add_phone_number(self, type: str, number: str) -> None:
        standard_types, custom_types, pref = self._parse_type_value(
            string_to_list(type, ","), self.phone_types_v4 if
            self.version == "4.0" else self.phone_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for phone number " + number +
                             " is missing.")
        if len(custom_types) > 1:
            raise ValueError("Error: phone number " + number + " got more "
                             "than one custom label: " +
                             list_to_string(custom_types, ", "))
        phone_obj = self.vcard.add('tel')
        if self.version == "4.0":
            phone_obj.value = "tel:{}".format(
                convert_to_vcard("phone number", number, ObjectType.str))
            phone_obj.params['VALUE'] = ["uri"]
            if pref > 0:
                phone_obj.params['PREF'] = str(pref)
        else:
            phone_obj.value = convert_to_vcard("phone number", number,
                                               ObjectType.str)
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
            group_name = "itemtel{}".format(custom_label_count + 1)
            phone_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = custom_types[0]

    @property
    def emails(self) -> Dict[str, List[str]]:
        """
        :returns: dict of type and email address list
        """
        email_dict: Dict[str, List[str]] = {}
        for child in self.vcard.getChildren():
            if child.name == "EMAIL":
                type = list_to_string(
                    self._get_types_for_vcard_object(child, "internet"), ", ")
                if type not in email_dict:
                    email_dict[type] = []
                email_dict[type].append(child.value)
        # sort email address lists
        for email_list in email_dict.values():
            email_list.sort()
        return email_dict

    def add_email(self, type: str, address: str) -> None:
        standard_types, custom_types, pref = self._parse_type_value(
            string_to_list(type, ","), self.email_types_v4 if
            self.version == "4.0" else self.email_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for email address " + address +
                             " is missing.")
        if len(custom_types) > 1:
            raise ValueError("Error: email address " + address + " got more "
                             "than one custom label: " +
                             list_to_string(custom_types, ", "))
        email_obj = self.vcard.add('email')
        email_obj.value = convert_to_vcard("email address", address,
                                           ObjectType.str)
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
            group_name = "itememail{}".format(custom_label_count + 1)
            email_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = custom_types[0]

    @property
    def post_addresses(self) -> Dict[str, List[PostAddress]]:
        """
        :returns: dict of type and post address list
        """
        post_adr_dict: Dict[str, List[PostAddress]] = {}
        for child in self.vcard.getChildren():
            if child.name == "ADR":
                type = list_to_string(self._get_types_for_vcard_object(
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
                list_to_string(x['city'], " ").lower(),
                list_to_string(x['street'], " ").lower()))
        return post_adr_dict

    def get_formatted_post_addresses(self) -> Dict[str, List[str]]:
        formatted_post_adr_dict: Dict[str, List[str]] = {}
        for type, post_adr_list in self.post_addresses.items():
            formatted_post_adr_dict[type] = []
            for post_adr in post_adr_list:
                get: Callable[[str], str] = lambda name: list_to_string(
                    post_adr.get(name, ""), " ")

                # remove empty fields to avoid empty lines
                for x in list(post_adr.keys()):
                    if post_adr.get(x) == "":
                        del post_adr[x]

                strings = []
                if "street" in post_adr:
                    strings.append(list_to_string(
                        post_adr.get("street", ""), "\n"))
                if "box" in post_adr and "extended" in post_adr:
                    strings.append("{} {}".format(get("box"), get("extended")))
                elif "box" in post_adr:
                    strings.append(get("box"))
                elif "extended" in post_adr:
                    strings.append(get("extended"))
                if "code" in post_adr and "city" in post_adr:
                    strings.append("{} {}".format(get("code"), get("city")))
                elif "code" in post_adr:
                    strings.append(get("code"))
                elif "city" in post_adr:
                    strings.append(get("city"))
                if "region" in post_adr and "country" in post_adr:
                    strings.append("{}, {}".format(get("region"),
                                                   get("country")))
                elif "region" in post_adr:
                    strings.append(get("region"))
                elif "country" in post_adr:
                    strings.append(get("country"))
                formatted_post_adr_dict[type].append('\n'.join(strings))
        return formatted_post_adr_dict

    def _add_post_address(self, type, box, extended, street, code, city,
                          region, country):
        standard_types, custom_types, pref = self._parse_type_value(
            string_to_list(type, ","), self.address_types_v4
            if self.version == "4.0" else self.address_types_v3)
        if not standard_types and not custom_types and pref == 0:
            raise ValueError("Error: label for post address " + street +
                             " is missing.")
        if len(custom_types) > 1:
            raise ValueError("Error: post address " + street + " got more "
                             "than one custom " "label: " +
                             list_to_string(custom_types, ", "))
        adr_obj = self.vcard.add('adr')
        adr_obj.value = vobject.vcard.Address(
            box=convert_to_vcard("box address field", box, ObjectType.both),
            extended=convert_to_vcard("extended address field", extended,
                                      ObjectType.both),
            street=convert_to_vcard("street", street, ObjectType.both),
            code=convert_to_vcard("post code", code, ObjectType.both),
            city=convert_to_vcard("city", city, ObjectType.both),
            region=convert_to_vcard("region", region, ObjectType.both),
            country=convert_to_vcard("country", country, ObjectType.both))
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
            group_name = "itemadr{}".format(custom_label_count + 1)
            adr_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = custom_types[0]


class YAMLEditable(VCardWrapper):
    """Conversion of vcards to YAML and updating the vcard from YAML"""

    def __init__(self, vcard: vobject.vCard,
                 supported_private_objects: Optional[List[str]] = None,
                 version: Optional[str] = None, localize_dates: bool = False
                 ) -> None:
        """Initialize attributes needed for yaml conversions

        :param supported_private_objects: the list of private property names
            that will be loaded from the actual vcard and represented in this
            pobject
        :param version: the version of the RFC to use in this card
        :param localize_dates: should the formatted output of anniversary
            and birthday be localized or should the iso format be used instead
        """
        self.supported_private_objects = supported_private_objects or []
        self.localize_dates = localize_dates
        super().__init__(vcard, version)

    #####################
    # getters and setters
    #####################

    def _get_private_objects(self) -> Dict[str, List[str]]:
        supported = [x.lower() for x in self.supported_private_objects]
        private_objects: Dict[str, List[str]] = {}
        for child in self.vcard.getChildren():
            lower = child.name.lower()
            if lower.startswith("x-") and lower[2:] in supported:
                key_index = supported.index(lower[2:])
                key = self.supported_private_objects[key_index]
                if key not in private_objects:
                    private_objects[key] = []
                ablabel = self._get_ablabel(child)
                private_objects[key].append(
                    {ablabel: child.value} if ablabel else child.value)
        # sort private object lists
        for value in private_objects.values():
            value.sort(key=multi_property_key)
        return private_objects

    def _add_private_object(self, key: str, value) -> None:
        self._add_labelled_object('X-' + key.upper(), value)

    def get_formatted_anniversary(self) -> str:
        return self._format_date_object(self.anniversary, self.localize_dates)

    def get_formatted_birthday(self) -> str:
        return self._format_date_object(self.birthday, self.localize_dates)

    #######################
    # object helper methods
    #######################

    @staticmethod
    def _format_date_object(date: Optional[Date], localize: bool) -> str:
        if not date:
            return ""
        if isinstance(date, str):
            return date
        if date.year == 1900 and date.month != 0 and date.day != 0 \
                and date.hour == 0 and date.minute == 0 and date.second == 0:
            return date.strftime("--%m-%d")
        tz = date.tzname()
        if (tz and tz[3:]) or (date.hour != 0 or date.minute != 0
                               or date.second != 0):
            if localize:
                return date.strftime(locale.nl_langinfo(locale.D_T_FMT))
            utc_offset = -time.timezone / 60 / 60
            return date.strftime("%FT%T+{:02}:00".format(int(utc_offset)))
        if localize:
            return date.strftime(locale.nl_langinfo(locale.D_FMT))
        return date.strftime("%F")

    @staticmethod
    def _filter_invalid_tags(contents: str) -> str:
        for pat, repl in [('aim', 'AIM'), ('gadu', 'GADUGADU'),
                          ('groupwise', 'GROUPWISE'), ('icq', 'ICQ'),
                          ('xmpp', 'JABBER'), ('msn', 'MSN'),
                          ('yahoo', 'YAHOO'), ('skype', 'SKYPE'),
                          ('irc', 'IRC'), ('sip', 'SIP')]:
            contents = re.sub('X-messaging/'+pat+'-All', 'X-'+repl, contents,
                              flags=re.IGNORECASE)
        return contents

    @staticmethod
    def _parse_yaml(input: str) -> Dict:
        """Parse a YAML document into a dictionary and validate the data to
        some degree.

        :param str input: the YAML document to parse
        :returns: the parsed data structure
        :rtype: dict
        """
        yaml_parser = YAML(typ='base')
        # parse user input string
        try:
            contact_data = yaml_parser.load(input)
        except (yaml.parser.ParserError, yaml.scanner.ScannerError,
                yaml.constructor.DuplicateKeyError) as err:
            raise ValueError(err)
        else:
            if not contact_data:
                raise ValueError("Error: Found no contact information")

        # check for available data
        # at least enter name or organisation
        if not (contact_data.get("First name") or contact_data.get("Last name")
                or contact_data.get("Organisation")):
            raise ValueError(
                "Error: You must either enter a name or an organisation")
        return contact_data

    @staticmethod
    def _set_string_list(setter: Callable[[Union[str, List]], None], key: str,
                         data: Dict) -> None:
        """Pre-process a string or list and set each value with the given
        setter

        :param setter: the setter method to add a value to a card
        :param key:
        :param data:
        """
        value = data.get(key)
        if value:
            if isinstance(value, str):
                setter(value)
            elif isinstance(value, list):
                for val in value:
                    if val:
                        setter(val)
            else:
                raise ValueError(
                    "{} must be a string or a list of strings".format(key))

    def _set_date(self, target: str, key: str, data: Dict) -> None:
        new = data.get(key)
        if not new:
            return
        if not isinstance(new, str):
            raise ValueError("Error: {} must be a string object.".format(key))
        if re.match(r"^text[\s]*=.*$", new):
            if self.version == "4.0":
                v1 = ', '.join(x.strip() for x in re.split(r"text[\s]*=", new)
                               if x.strip())
                if v1:
                    setattr(self, target, v1)
                return
            raise ValueError("Error: Free text format for {} only usable with "
                             "vcard version 4.0.".format(key.lower()))
        if re.match(r"^--\d\d-?\d\d$", new) and self.version != "4.0":
            raise ValueError(
                "Error: {} format --mm-dd and --mmdd only usable with "
                "vcard version 4.0. You may use 1900 as placeholder, if "
                "the year is unknown.".format(key))
        try:
            v2 = string_to_date(new)
            if v2:
                setattr(self, target, v2)
            return
        except ValueError:
            pass
        raise ValueError("Error: Wrong {} format or invalid date\n"
                         "Use format yyyy-mm-dd or "
                         "yyyy-mm-ddTHH:MM:SS".format(key.lower()))

    def update(self, input: str) -> None:
        """Update this vcard with some yaml input

        :param input: a yaml string to parse and then use to update self
        """
        contact_data = self._parse_yaml(input)
        # update rev
        self._update_revision()

        # name
        self._delete_vcard_object("N")
        # although the "n" attribute is not explicitly required by the vcard
        # specification,
        # the vobject library throws an exception, if it doesn't exist
        # so add the name regardless if it's empty or not
        self._add_name(
            contact_data.get("Prefix", ""), contact_data.get("First name", ""),
            contact_data.get("Additional", ""),
            contact_data.get("Last name", ""), contact_data.get("Suffix", ""))
        if "Formatted name" in contact_data:
            self.formatted_name = contact_data.get("Formatted name", "")
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
        phone_data = contact_data.get("Phone")
        if phone_data:
            if isinstance(phone_data, dict):
                for type, number_list in phone_data.items():
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
        email_data = contact_data.get("Email")
        if email_data:
            if isinstance(email_data, dict):
                for type, email_list in email_data.items():
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
        address_data = contact_data.get("Address")
        if address_data:
            if isinstance(address_data, dict):
                for type, post_adr_list in address_data.items():
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
        cat_data = contact_data.get("Categories")
        if cat_data:
            if isinstance(cat_data, str):
                self._add_category([cat_data])
            elif isinstance(cat_data, list):
                only_contains_strings = True
                for sub_category in cat_data:
                    if not isinstance(sub_category, str):
                        only_contains_strings = False
                        break
                # if the category list only contains strings, pack all of them
                # in a single CATEGORIES vcard tag
                if only_contains_strings:
                    self._add_category(cat_data)
                else:
                    for sub_category in cat_data:
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
        private_data = contact_data.get("Private")
        if private_data:
            if isinstance(private_data, dict):
                for key, value_list in private_data.items():
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

    def to_yaml(self) -> str:
        """Convert this contact to a YAML string

        The conversion follows the implicit schema that is given by the
        internal YAML template of khard.

        :returns: a YAML representation of this contact
        """

        translation_table = {
            "Formatted name": self.formatted_name,
            "Prefix": self._get_name_prefixes(),
            "First name": self._get_first_names(),
            "Additional": self._get_additional_names(),
            "Last name": self._get_last_names(),
            "Suffix": self._get_name_suffixes(),
            "Nickname": self.nicknames,
            "Organisation": self.organisations,
            "Title": self.titles,
            "Role": self.roles,
            "Phone": helpers.yaml_dicts(
                self.phone_numbers, defaults=["cell", "home"]),
            "Email": helpers.yaml_dicts(
                self.emails, defaults=["home", "work"]),
            "Categories": self.categories,
            "Note": self.notes,
            "Webpage": self.webpages,
            "Anniversary":
                helpers.yaml_anniversary(self.anniversary, self.version),
            "Birthday":
                helpers.yaml_anniversary(self.birthday, self.version),
            "Address": helpers.yaml_addresses(
                self.post_addresses, ["Box", "Extended", "Street", "Code",
                    "City", "Region", "Country"], defaults=["home"])
        }
        template = helpers.get_new_contact_template()
        yaml = YAML()
        yaml.indent(mapping=4, sequence=4, offset=2)
        template_obj = yaml.load(template)
        for key in template_obj:
            value = translation_table.get(key, None)
            template_obj[key] = helpers.yaml_clean(value)

        if self.supported_private_objects:
            template_obj["Private"] = helpers.yaml_clean(
                helpers.yaml_dicts(
                    self._get_private_objects(),
                    self.supported_private_objects
                ))

        stream = io.StringIO()
        yaml.dump(template_obj, stream)
        # posix standard: eof char must be \n
        return stream.getvalue() + "\n"


class CarddavObject(YAMLEditable):

    def __init__(self, vcard: vobject.vCard,
                 address_book: "address_book.VdirAddressBook", filename: str,
                 supported_private_objects: Optional[List[str]] = None,
                 vcard_version: Optional[str] = None,
                 localize_dates: bool = False) -> None:
        """Initialize the vcard object.

        :param vcard: the vCard to wrap
        :param address_book: a reference to the address book where this vcard
            is stored
        :param filename: the path to the file where this vcard is stored
        :param supported_private_objects: the list of private property names
            that will be loaded from the actual vcard and represented in this
            object
        :param vcard_version: the version of the RFC to use
        :param localize_dates: should the formatted output of anniversary and
            birthday be localized or should the iso format be used instead
        """
        self.address_book = address_book
        self.filename = filename
        super().__init__(vcard, supported_private_objects, vcard_version,
                         localize_dates)

    #######################################
    # factory methods to create new contact
    #######################################

    @classmethod
    def new(cls, address_book: "address_book.VdirAddressBook",
            supported_private_objects: Optional[List[str]] = None,
            version: Optional[str] = None, localize_dates: bool = False
            ) -> "CarddavObject":
        """Create a new CarddavObject from scratch"""
        vcard = vobject.vCard()
        uid = helpers.get_random_uid()
        filename = os.path.join(address_book.path, uid + ".vcf")
        card = cls(vcard, address_book, filename, supported_private_objects,
                   version, localize_dates)
        card.uid = uid
        return card

    @classmethod
    def from_file(cls, address_book: "address_book.VdirAddressBook",
                  filename: str, query: Query = AnyQuery(),
                  supported_private_objects: Optional[List[str]] = None,
                  localize_dates: bool = False) -> Optional["CarddavObject"]:
        """Load a CarddavObject object from a .vcf file if the plain file
        matches the query.

        :param address_book: the address book where this contact is stored
        :param filename: the file name of the .vcf file
        :param query: the query to search in the source file or None to load
            the file unconditionally
        :param supported_private_objects: the list of private property names
            that will be loaded from the actual vcard and represented in this
            object
        :param localize_dates: should the formatted output of anniversary
            and birthday be localized or should the iso format be used instead
        :returns: the loaded CarddavObject or None if the file didn't match
        """
        with open(filename, "r") as file:
            contents = file.read()
        if query.match(contents):
            try:
                vcard = vobject.readOne(contents)
            except Exception:
                logger.warning("Filtering some problematic tags from %s",
                               filename)
                # if creation fails, try to repair some vcard attributes
                vcard = vobject.readOne(cls._filter_invalid_tags(contents))
            return cls(vcard, address_book, filename,
                       supported_private_objects, None, localize_dates)
        return None

    @classmethod
    def from_yaml(cls, address_book: "address_book.VdirAddressBook", yaml: str,
                  supported_private_objects: Optional[List[str]] = None,
                  version: Optional[str] = None, localize_dates: bool = False
                  ) -> "CarddavObject":
        """Use this if you want to create a new contact from user input."""
        contact = cls.new(address_book, supported_private_objects, version,
                          localize_dates=localize_dates)
        contact.update(yaml)
        return contact

    @classmethod
    def clone_with_yaml_update(cls, contact: "CarddavObject", yaml: str,
                               localize_dates: bool = False
                               ) -> "CarddavObject":
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

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CarddavObject) and \
            self.pretty(False) == other.pretty(False)

    def __ne__(self, other: object) -> bool:
        return not self == other

    def pretty(self, verbose: bool = True) -> str:
        strings = []

        # Every vcard must have an FN field per the RFC.
        strings.append("Name: {}".format(self.formatted_name))
        # name
        if self._get_first_names() or self._get_last_names():
            names = self._get_name_prefixes() + self._get_first_names() + \
                self._get_additional_names() + self._get_last_names() + \
                self._get_name_suffixes()
            strings.append("Full name: {}".format(list_to_string(names, " ")))
        # organisation
        if self.organisations:
            strings += helpers.convert_to_yaml(
                "Organisation", self.organisations, 0, -1, False)

        # address book name
        if verbose:
            strings.append("Address book: {}".format(self.address_book))

        # kind
        if self.kind is not None:
            strings.append("Kind: {}".format(self.kind))

        # person related information
        if (self.birthday is not None or self.anniversary is not None
                or self.nicknames or self.roles or self.titles):
            strings.append("General:")
            if self.anniversary:
                strings.append("    Anniversary: {}".format(
                    self.get_formatted_anniversary()))
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
        if self.categories or self.webpages or self.notes or (verbose
                                                              and self.uid):
            strings.append("Miscellaneous")
            if verbose and self.uid:
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
        return '\n'.join(strings) + '\n'

    def write_to_file(self, overwrite: bool = False) -> None:
        # make sure, that every contact contains a uid
        if not self.uid:
            self.uid = helpers.get_random_uid()
        try:
            with atomic_write(self.filename, overwrite=overwrite) as f:
                f.write(self.vcard.serialize())
        except vobject.base.ValidateError as err:
            print("Error: Vcard is not valid.\n{}".format(err))
            sys.exit(4)
        except OSError as err:
            print("Error: Can't write\n{}".format(err))
            sys.exit(4)

    def delete_vcard_file(self) -> None:
        try:
            os.remove(self.filename)
        except OSError as err:
            logger.error("Can not remove vCard file: %s", err)

    @classmethod
    def get_properties(cls) -> List[str]:
        """Return the property names that are defined on this class."""
        return [name for name in dir(CarddavObject)
                if isinstance(getattr(CarddavObject, name), property)]
