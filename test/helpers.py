"""Helper functions for the tests."""

import contextlib
import os
import shutil
import sys
import tempfile
import unittest


def expectedFailureForVersion(major, minor):
    "A decorator to mark a test as an expected failure for one python version."
    if sys.version_info.major == major and sys.version_info.minor == minor:
        return unittest.expectedFailure
    else:
        return lambda x: x


class with_vcards(contextlib.ContextDecorator):

    def __init__(self, vcards):
        self.tempdir = None
        self.config = None
        self.vcards = vcards
        self.mock = None

    def __enter__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        for card in self.vcards:
            shutil.copy(card, self.tempdir.name)
        with tempfile.NamedTemporaryFile("w", delete=False) as config:
            config.write("""[general]
                            editor = editor
                            merge_editor = merge_editor
                            [addressbooks]
                            [[tmp]]
                            path = {}
                            """.format(self.tempdir.name))
        self.config = config
        self.mock = unittest.mock.patch.dict('os.environ',
                                             KHARD_CONFIG=config.name)
        self.mock.start()
        return self

    def __exit__(self, a, b, c):
        self.mock.stop()
        os.unlink(self.config.name)
        self.tempdir.cleanup()
        return False
