"""Helper functions for the tests."""

import sys
import unittest


def expectedFailureForVersion(major, minor):
    "A decorator to mark a test as an expected failure for one python version."
    if sys.version_info.major == major and sys.version_info.minor == minor:
        return unittest.expectedFailure
    else:
        return lambda x: x
