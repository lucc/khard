#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# tutorials:
#   - https://packaging.python.org/en/latest/distributing.html
#   - https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/

import os
from setuptools import setup
from khard.version import khard_version

setup(
    name = 'khard',
    version = khard_version,
    author = 'Eric Scheibler',
    author_email = 'email@eric-scheibler.de',
    url = 'https://github.com/scheibler/khard/',
    description = 'A console carddav client',
    long_description = open('README.md').read(),
    license = 'GPL',
    keywords = 'Carddav console addressbook',
    classifiers = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 2 :: Only",
    ],
    packages = [
        'khard',
        'davcontroller'
    ],
    entry_points = {
        'console_scripts': [
            'khard = khard.khard:main',
            'davcontroller = davcontroller.davcontroller:main',
        ]
    },
    install_requires = [
        'configobj',
        'vobject',
        'argparse',
    ],
)
