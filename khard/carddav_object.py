# -*- coding: utf-8 -*-

import os, sys, string, random, datetime, re
import vobject

class CarddavObject:
    def __init__(self, address_book, filename = None):
        self.vcard = None
        self.address_book = address_book
        self.filename = filename

        if self.filename is None:
            # create new vcard object
            self.vcard = vobject.vCard()
            # uid
            choice = string.ascii_uppercase + string.digits
            uid_obj = self.vcard.add('uid')
            uid_obj.value = ''.join([random.choice(choice) for _ in range(36)])
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
                and self.print_vcard(show_address_book = False) == other.print_vcard(show_address_book = False)

    def __ne__(self, other):
        return not self == other


    #####################
    # getters and setters
    #####################

    def get_address_book(self):
        return self.address_book

    def get_filename(self):
        return self.filename

    def set_filename(self, filename):
        self.filename = filename

    def get_title(self):
        try:
            return self.vcard.title.value.encode("utf-8")
        except AttributeError as e:
            return ""

    def get_first_name(self):
        try:
            return self.vcard.n.value.given.encode("utf-8")
        except AttributeError as e:
            return ""

    def get_last_name(self):
        try:
            return self.vcard.n.value.family.encode("utf-8")
        except AttributeError as e:
            return ""

    def get_full_name(self):
        try:
            return self.vcard.fn.value.encode("utf-8")
        except AttributeError as e:
            if self.get_first_name() != "" and self.get_last_name() != "":
                return "%s %s" % (self.get_first_name(), self.get_last_name())
            elif self.get_first_name() != "":
                return self.get_first_name()
            elif self.get_last_name() != "":
                return self.get_last_name()
            elif self.get_organisation() != "":
                return self.get_organisation()
            else:
                return ""

    def get_organisation(self):
        try:
            return ' '.join(self.vcard.org.value).encode("utf-8")
        except AttributeError as e:
            return ""

    def get_role(self):
        try:
            return self.vcard.role.value.encode("utf-8")
        except AttributeError as e:
            return ""

    def set_name_and_organisation(self, title, first_name, last_name, organisation, role):
        if first_name == "" and last_name == "":
            name_obj = self.vcard.add('fn')
            name_obj.value = organisation
            name_obj = self.vcard.add('n')
            name_obj.value = vobject.vcard.Name(family="", given="")
            showas_obj = self.vcard.add('x-abshowas')
            showas_obj.value = "COMPANY"
        else:
            name_obj = self.vcard.add('fn')
            name_obj.value = "%s %s" % (first_name, last_name)
            name_obj = self.vcard.add('n')
            name_obj.value = vobject.vcard.Name(family=last_name, given=first_name)
        if organisation != "":
            org_obj = self.vcard.add('org')
            org_obj.value = [organisation]
        if title != "":
            title_obj = self.vcard.add('title')
            title_obj.value = title
        if role != "":
            role_obj = self.vcard.add('role')
            role_obj.value = role

    def get_phone_numbers(self):
        phone_list = []
        for child in self.vcard.getChildren():
            if child.name != "TEL":
                continue
            type = "voice"
            if child.params.has_key("TYPE"):
                type = ','.join(child.params['TYPE']).encode("utf-8")
            elif child.group != None:
                for label in self.vcard.getChildren():
                    if label.name == "X-ABLABEL" and label.group == child.group:
                        type = label.value.encode("utf-8")
                        break
            phone_list.append({"type":type, "value":child.value.encode("utf-8")})
        return sorted(phone_list, key=lambda k: k['type'].lower())

    def add_phone_number(self, type, number):
        phone_obj = self.vcard.add('tel')
        phone_obj.value = number
        if type.lower() in ["cell", "home", "work",]:
            phone_obj.type_param = type
        else:
            number_of_custom_phone_number_labels = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith("itemtel"):
                    number_of_custom_phone_number_labels += 1
            group_name = "itemtel%d" % (number_of_custom_phone_number_labels+1)
            phone_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = type

    def get_email_addresses(self):
        email_list = []
        for child in self.vcard.getChildren():
            if child.name != "EMAIL":
                continue
            type = "home"
            if child.params.has_key("TYPE"):
                type = ','.join(child.params['TYPE']).encode("utf-8")
            elif child.group != None:
                for label in self.vcard.getChildren():
                    if label.name == "X-ABLABEL" and label.group == child.group:
                        type = label.value.encode("utf-8")
                        break
            email_list.append({"type":type, "value":child.value.encode("utf-8")})
        return sorted(email_list, key=lambda k: k['type'].lower())

    def add_email_address(self, type, address):
        email_obj = self.vcard.add('email')
        email_obj.value = address
        if type.lower() in ["home", "work",]:
            email_obj.type_param = type
        else:
            number_of_custom_email_labels = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith("itememail"):
                    number_of_custom_email_labels += 1
            group_name = "itememail%d" % (number_of_custom_email_labels+1)
            email_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = type

    def get_post_addresses(self):
        address_list = []
        for child in self.vcard.getChildren():
            if child.name != "ADR":
                continue
            type = "home"
            if child.params.has_key("TYPE"):
                type = ','.join(child.params['TYPE']).encode("utf-8")
            elif child.group != None:
                for label in self.vcard.getChildren():
                    if label.name == "X-ABLABEL" and label.group == child.group:
                        type = label.value.encode("utf-8")
                        break
            try:
                street_and_house_number = child.value.street.encode("utf-8")
            except AttributeError as e:
                street_and_house_number = ', '.join([ x.strip() for x in child.value.street ]).encode("utf-8")
            address_list.append({"type":type,
                    "street_and_house_number":street_and_house_number,
                    "postcode":child.value.code.encode("utf-8"),
                    "city":child.value.city.encode("utf-8"),
                    "region":child.value.region.encode("utf-8"),
                    "country":child.value.country.encode("utf-8")})
        return sorted(address_list, key=lambda k: k['type'].lower())

    def add_post_address(self, type, street_and_house_number, postcode, city, region, country):
        adr_obj = self.vcard.add('adr')
        adr_obj.value = vobject.vcard.Address(street=street_and_house_number,
                city=city, region=region, code=postcode, country=country)
        if type.lower() in ["home", "work",]:
            adr_obj.type_param = type
        else:
            number_of_custom_post_address_labels = 0
            for label in self.vcard.getChildren():
                if label.name == "X-ABLABEL" and label.group.startswith("itemadr"):
                    number_of_custom_post_address_labels += 1
            group_name = "itemadr%d" % (number_of_custom_post_address_labels+1)
            adr_obj.group = group_name
            label_obj = self.vcard.add('x-ablabel')
            label_obj.group = group_name
            label_obj.value = type

    def get_categories(self):
        category_list = []
        for child in self.vcard.getChildren():
            if child.name == "CATEGORIES":
                category_list = [child.value[ii].encode('utf-8') for ii in xrange(len(child.value))]
        return category_list

    def get_nickname(self):
        try:
            return self.vcard.nickname.value.encode("utf-8")
        except AttributeError as e:
            return ""

    def set_nickname(self, name):
        nickname_obj = self.vcard.add('nickname')
        nickname_obj.value = name

    def get_jabber_id(self):
        try:
            return self.vcard.x_jabber.value.encode("utf-8")
        except AttributeError as e:
            return ""

    def set_jabber_id(self, jabber_id):
        jabber_obj = self.vcard.add('x-jabber')
        jabber_obj.value = jabber_id

    def get_skype_id(self):
        try:
            return self.vcard.x_skype.value.encode("utf-8")
        except AttributeError as e:
            return ""

    def set_skype_id(self, skype_id):
        skype_obj = self.vcard.add('x-skype')
        skype_obj.value = skype_id

    def get_twitter_id(self):
        try:
            return self.vcard.x_twitter.value.encode("utf-8")
        except AttributeError as e:
            return ""

    def set_twitter_id(self, twitter_id):
        twitter_obj = self.vcard.add('x-twitter')
        twitter_obj.value = twitter_id

    def get_webpage(self):
        try:
            return self.vcard.url.value.encode("utf-8")
        except AttributeError as e:
            return ""

    def set_webpage(self, webpage):
        webpage_obj = self.vcard.add('url')
        webpage_obj.value = webpage

    def get_birthday(self):
        """:returns: contacts birthday or None if not available
            :rtype: datetime.datetime
        """
        try:
            return datetime.datetime.strptime(self.vcard.bday.value.replace('-', ''), "%Y%m%d")
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
        # title
        try:
            self.vcard.remove(self.vcard.title)
        except AttributeError as e:
            pass
        # name
        try:
            self.vcard.remove(self.vcard.n)
            self.vcard.remove(self.vcard.fn)
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
        # role
        try:
            self.vcard.remove(self.vcard.role)
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
        # nickname
        try:
            self.vcard.remove(self.vcard.nickname)
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
        contact_data = {}
        counter = 1
        for line in input.splitlines():
            if line == "" or line.startswith("#"):
                continue
            try:
                key = line.split("=")[0].strip().lower()
                value = line.split("=")[1].strip()
                if value == "":
                    continue
                if contact_data.has_key(key):
                    print("Error in input line %d: key %s already exists" % (counter, key))
                    sys.exit(1)
                contact_data[key] = value.decode("utf-8")
                counter += 1
            except IndexError as e:
                print("Error in input line %d: Malformed input\nLine: %s" % (counter, line))
                sys.exit(1)

        # clean vcard
        self.clean_vcard()

        # process data
        # update ref
        dt = datetime.datetime.now()
        rev_obj = self.vcard.add('rev')
        rev_obj.value = "%.4d%.2d%.2dT%.2d%.2d%.2dZ" \
                % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second) 

        # name, title, organisation and role
        # at least enter name or organisation
        if contact_data.has_key("title") == False:
            contact_data['title'] = ""
        if contact_data.has_key("first name") == False:
            contact_data['first name'] = ""
        if contact_data.has_key("last name") == False:
            contact_data['last name'] = ""
        if contact_data.has_key("organisation") == False:
            contact_data['organisation'] = ""
        if contact_data.has_key("role") == False:
            contact_data['role'] = ""
        if contact_data['first name'] == "" \
                and contact_data['last name'] == "" \
                and contact_data['organisation'] == "":
            print("Error: You must either enter a name or an organisation")
            sys.exit(1)
        else:
            self.set_name_and_organisation(contact_data['title'],
                    contact_data['first name'], contact_data['last name'],
                    contact_data['organisation'], contact_data['role'])

        # phone
        for key in contact_data.keys():
            if key.startswith("phone") == False:
                continue
            try:
                label = contact_data[key].split(":")[0].strip()
                if label == "":
                    print("Error: Missing label for line %s" % key)
                    sys.exit(1)
                number = contact_data[key].split(":")[1].strip()
                if number == "":
                    continue
            except IndexError as e:
                print("Error: The %s line is malformed" % key)
                sys.exit(1)
            self.add_phone_number(label, number)

        # email
        for key in contact_data.keys():
            if key.startswith("email") == False:
                continue
            try:
                label = contact_data[key].split(":")[0].strip()
                if label == "":
                    print("Error: Missing label for line %s" % key)
                    sys.exit(1)
                email = contact_data[key].split(":")[1].strip()
                if email == "":
                    continue
            except IndexError as e:
                print("Error: The %s line is malformed" % key)
                sys.exit(1)
            self.add_email_address(label, email)

        # post addresses
        for key in contact_data.keys():
            if key.startswith("address") == False:
                continue
            try:
                label = contact_data[key].split(":")[0].strip()
                if label == "":
                    print("Error: Missing label for line %s" % key)
                    sys.exit(1)
                address = contact_data[key].split(":")[1].strip()
                if address == "; ; ; ;":
                    continue
            except IndexError as e:
                print("Error: The %s line is malformed" % key)
                sys.exit(1)
            if address.split(";").__len__() != 5:
                print("Error: The %s line is malformed" % key)
                sys.exit(1)
            street_and_house_number = address.split(";")[0].strip()
            postcode = address.split(";")[1].strip()
            city = address.split(";")[2].strip()
            region = address.split(";")[3].strip()
            country = address.split(";")[4].strip()
            self.add_post_address(label, street_and_house_number, postcode, city, region, country)

        # instant messaging and social networks
        if contact_data.has_key("jabber") and contact_data['jabber'] != "":
            self.set_jabber_id(contact_data['jabber'])
        if contact_data.has_key("skype") and contact_data['skype'] != "":
            self.set_skype_id(contact_data['skype'])
        if contact_data.has_key("twitter") and contact_data['twitter'] != "":
            self.set_twitter_id(contact_data['twitter'])
        if contact_data.has_key("webpage") and contact_data['webpage'] != "":
            self.set_webpage(contact_data['webpage'])

        # miscellaneous stuff
        # nickname
        if contact_data.has_key("nickname") and contact_data['nickname'] != "":
            self.set_nickname(contact_data['nickname'])
        # birthday
        if contact_data.has_key("birthday") and contact_data['birthday'] != "":
            try:
                date = datetime.datetime.strptime(contact_data['birthday'], "%d.%m.%Y")
                self.set_birthday(date)
            except ValueError as e:
                print("Error: Birthday date in the wrong format. Example: 31.12.1989")
                sys.exit(1)

    def print_vcard(self, show_address_book = True):
        strings = []
        # name or organisation
        if self.get_organisation() == "" and self.get_full_name() == "":
            strings.append("Name:")
        elif self.get_organisation() != self.get_full_name():
            if self.get_title() != "":
                strings.append("Name: %s %s" % (self.get_title(), self.get_full_name()))
            else:
                strings.append("Name: %s" % self.get_full_name())
        if self.get_organisation() != "":
            strings.append("Organisation: %s" % self.get_organisation())
        if self.get_role() != "":
            strings.append("Role: %s" % self.get_role())
        if self.get_nickname() != "":
            strings.append("Nickname: %s" % self.get_nickname())
        if show_address_book:
            strings.append("Address book: %s" % self.address_book.get_name())
        if self.get_categories().__len__() > 0:
            strings.append("Categories\n    %s" % ', '.join(self.get_categories()))
        if self.get_phone_numbers().__len__() > 0:
            strings.append("Phone")
            for index, entry in enumerate(self.get_phone_numbers()):
                strings.append("    %s: %s" % (entry['type'], entry['value']))
        if self.get_email_addresses().__len__() > 0:
            strings.append("E-Mail")
            for index, entry in enumerate(self.get_email_addresses()):
                strings.append("    %s: %s" % (entry['type'], entry['value']))
        if self.get_post_addresses().__len__() > 0:
            strings.append("Addresses")
            for index, entry in enumerate(self.get_post_addresses()):
                strings.append("    %s:" % entry['type'])
                if entry['street_and_house_number'] != "":
                    strings.append("        %s" % entry['street_and_house_number'])
                if entry['postcode'] != "" and entry['city'] != "":
                    strings.append("        %s %s" % (entry['postcode'], entry['city']))
                elif entry['postcode'] != "":
                    strings.append("        %s" % entry['postcode'])
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
        if self.get_birthday() != None:
            strings.append("Miscellaneous")
            if self.get_birthday() != None:
                date = self.get_birthday()
                strings.append("    Birthday: %.2d.%.2d.%.4d" % (date.day, date.month, date.year))
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

