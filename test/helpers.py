"""Helper functions for the tests."""
# pylint: disable=invalid-name

import contextlib
import io
import locale
import os
import shutil
import tempfile
from typing import Generator
from unittest import SkipTest, mock

import vobject

from khard import address_book
from khard import contacts


def vCard(**kwargs):
    """Create a simple vobject.vCard for tests."""
    vcard = vobject.vCard()
    if 'fn' not in kwargs:
        kwargs['fn'] = 'Test vCard'
    if 'version' not in kwargs:
        kwargs['version'] = '3.0'
    for key, value in kwargs.items():
        vcard.add(key.upper()).value = value
    return vcard


def TestVCardWrapper(**kwargs):
    """Create a simple VCardWrapper for tests."""
    return contacts.VCardWrapper(vCard(**kwargs))


def TestYAMLEditable(**kwargs):
    """Create a simple YAMLEditable for tests."""
    return contacts.YAMLEditable(vCard(**kwargs))


def TestContact(**kwargs):
    """Create a siple Contact for tests."""
    return contacts.Contact(vCard(**kwargs), None, None)


def mock_stream(name="stdout"):
    """A context manager to replace a stdio stream with a string buffer.

    >>> with mock_stream() as s:
    >>>     print("hello world")
    >>> assert s.getvalue() == "hello world"
    >>> with mock_stream("stderr") as e:
    >>>     print("hallo error", file=sys.stderr)
    >>> assert e.getvalue() == "hello error"
    """
    stream = io.StringIO()
    context_manager = mock.patch('sys.'+name, stream)
    context_manager.getvalue = stream.getvalue
    return context_manager


def load_contact(path: str) -> contacts.Contact:
    """Load a contact from the fixture directory.

    :param path: the file name (full, relative to cwd or the fixture dir)
    """
    abook = address_book.VdirAddressBook("test", "/tmp")
    if not os.path.exists(path):
        path = os.path.join("test/fixture/vcards", path)
    contact = contacts.Contact.from_file(abook, path)
    if contact is None:
        raise FileNotFoundError(path)
    return contact


@contextlib.contextmanager
def mock_locale(cat: int, loc: str) -> Generator[None, None, None]:
    if not check_locale(loc):
        raise SkipTest(f"Locale {loc} is not installed")
    old = locale.getlocale(cat)
    if loc in locale.locale_alias:
        loc = locale.locale_alias[loc]
    try:
        locale.setlocale(cat, loc)
        yield
    finally:
        locale.setlocale(cat, old)


_installed_locales: dict[str, str] = {}
def check_locale(loc: str) -> bool:
    if not _installed_locales:
        collate = locale.getlocale(locale.LC_COLLATE)
        ctype = locale.getlocale(locale.LC_CTYPE)
        messages = locale.getlocale(locale.LC_MESSAGES)
        monetary = locale.getlocale(locale.LC_MONETARY)
        numeric = locale.getlocale(locale.LC_NUMERIC)
        time = locale.getlocale(locale.LC_TIME)
        try:
            for key, value in locale.locale_alias.items():
                try:
                    locale.setlocale(locale.LC_ALL, value)
                    _installed_locales[key] = value
                except locale.Error:
                    pass
        finally:
            locale.setlocale(locale.LC_COLLATE, collate)
            locale.setlocale(locale.LC_CTYPE, ctype)
            locale.setlocale(locale.LC_MESSAGES, messages)
            locale.setlocale(locale.LC_MONETARY, monetary)
            locale.setlocale(locale.LC_NUMERIC, numeric)
            locale.setlocale(locale.LC_TIME, time)
    return loc in _installed_locales or loc in _installed_locales.values()


class TmpAbook:
    """Context manager to create a temporary address book folder"""

    def __init__(self, vcards, name="tmp"):
        self.vcards = vcards
        self.name = name

    def __enter__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        for card in self.vcards:
            shutil.copy(self._card_path(card), self.tempdir.name)
        return address_book.VdirAddressBook(self.name, self.tempdir.name)

    def __exit__(self, _a, _b, _c):
        self.tempdir.cleanup()

    @staticmethod
    def _card_path(card):
        if os.path.exists(card):
            return card
        return os.path.join("test/fixture/vcards", card)


class TmpConfig(contextlib.ContextDecorator):
    """Context manager to create a temporary khard configuration.

    The given vcards will be copied to the only address book in the
    configuration which will be called "tmp".
    """

    def __init__(self, vcards):
        self.tempdir = None
        self.config = None
        self.vcards = vcards
        self.mock = None

    def __enter__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        for card in self.vcards:
            shutil.copy(self._card_path(card), self.tempdir.name)
        with tempfile.NamedTemporaryFile("w", delete=False) as config:
            config.write("""[general]
                            editor = editor
                            merge_editor = merge_editor
                            [addressbooks]
                            [[tmp]]
                            path = {}
                            """.format(self.tempdir.name))
        self.config = config
        self.mock = mock.patch.dict('os.environ', KHARD_CONFIG=config.name)
        self.mock.start()
        return self

    def __exit__(self, _a, _b, _c):
        self.mock.stop()
        os.unlink(self.config.name)
        self.tempdir.cleanup()

    @staticmethod
    def _card_path(card):
        if os.path.exists(card):
            return card
        return os.path.join("test/fixture/vcards", card)
