"""Helper functions for the tests."""
# pylint: disable=invalid-name

import contextlib
import io
import os
import shutil
import tempfile
from unittest import mock

import vobject

from khard import address_book
from khard import carddav_object


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
    return carddav_object.VCardWrapper(vCard(**kwargs))


def TestYAMLEditable(**kwargs):
    """Create a simple YAMLEditable for tests."""
    return carddav_object.YAMLEditable(vCard(**kwargs))


def TestCarddavObject(**kwargs):
    """Create a siple CarddavObject for tests."""
    return carddav_object.CarddavObject(vCard(**kwargs), None, None)


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


class TmpAbook:
    """Context manager to create a temporary address book folder"""

    def __init__(self, vcards):
        self.vcards = vcards

    def __enter__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        for card in self.vcards:
            shutil.copy(self._card_path(card), self.tempdir.name)
        return address_book.VdirAddressBook("tmp", self.tempdir.name)

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
