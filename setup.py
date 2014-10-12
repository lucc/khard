#!/usr/bin/python
# -*- coding: utf-8 -*-

# tutorial: http://www.scotttorborg.com/python-packaging/minimal.html

import os
from setuptools import setup

setup(
    name = 'khard',
    version = '0.2',
    author = 'Eric Scheibler',
    author_email = 'email@eric-scheibler.de',
    url = 'https://github.com/scheibler/khard/',
    description = 'A console carddav client',
    long_description = open('README.rst').read(),
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
        'vdirsyncer',
    ]
)
