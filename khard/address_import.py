import argparse
import email
import email.header
import os
import sys

from . import ui
from config import Config
from carddav_object import CarddavObject

def get_tty():
    """make sure we are connected to the currently active tty"""
    sys.stdin = open('/dev/tty')
    sys.stdout = open('/dev/tty', 'wb')
    sys.stderr = open('/dev/tty', 'wb')
    os.dup2(sys.stdin.fileno(), 0)
    os.dup2(sys.stdout.fileno(), 1)
    os.dup2(sys.stderr.fileno(), 2)


def release_tty():
    """release currently open tty"""
    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()


def parse_address(header):
    """split a header line (To, From, CC) into email address and display name"""
    if header is None:
        return None, ''

    address_string = []
    addresses = email.header.decode_header(header)
    for string, enc in addresses:
        if enc is None:
            enc = 'ascii'
        try:
            string = string.decode(enc)
        except TypeError:  # XXX what is this for?
            try:
                string = unicode(string)
            except UnicodeDecodeError:
                string = string.decode('ascii', 'replace')
        address_string.append(string)

    address_string = ' '.join(address_string)
    display_name, address = email.utils.parseaddr(address_string)

    return address, display_name


def get_names(display_name):
    first_name, last_name = '', display_name

    if display_name.find(',') > 0:
        # Parsing something like 'Doe, John Abraham'
        last_name, first_name = display_name.split(',')

    elif display_name.find(' '):
        # Parsing something like 'John Abraham Doe'
        # TODO: This fails for compound names. What is the most common case?
        name_list = display_name.split(' ')
        last_name = ''.join(name_list[-1])
        first_name = ' '.join(name_list[:-1])

    return first_name.strip().capitalize(), last_name.strip().capitalize()


def main():
    parser = argparse.ArgumentParser(description="Khard is a carddav address book for the console")
    parser.add_argument("-a", "--addressbook", default="",
            help="Specify address book names as comma separated list")
    parser.add_argument("-r", "--reverse", action="store_true", help="Sort contacts in reverse order")
    parser.add_argument("action", nargs="?", default="",
            help="Possible actions: list, details, mutt, alot, twinkle, new, modify, remove, import and source")
    args = parser.parse_args()

    books = Config().get_all_addressbooks()
    book = books[books.keys()[0]]  # FIXME proper selection of address book

    message = email.message_from_string(sys.stdin.read())
    get_tty()
    headers = ['To', 'From']
    for header in headers:
        address, full_name = parse_address(message[header])
        if address is None:
            continue
        first_name, last_name = get_names(full_name)
        vcard = CarddavObject(book['name'], book['path'])
        vcard.set_name_and_organisation(first_name, last_name, '')
        vcard.set_email_addresses([{'type': 'WORK', 'value': address}])

        ui.start_pane(ui.EditorPane(vcard, book))
    release_tty()



