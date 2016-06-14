# -*- coding: utf-8 -*-

# tutorials:
#   - https://packaging.python.org/en/latest/distributing.html
#   - https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
#   - https://gehrcke.de/2014/02/distributing-a-python-command-line-application/

import re
import sys
from setuptools import setup

if sys.version_info.major < 3:
    print("Error: khard runs under python3 only. Please upgrade your system "
            "wide python installation or create a python3 virtual environment "
            "first.")
    sys.exit(1)

setup(
    name = 'khard',
    version = re.sub("[^0-9.]", "", open('khard/version.py').read()),
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
        "Programming Language :: Python :: 3 :: Only",
    ],
    install_requires = ['atomicwrites', 'configobj', 'pyyaml', 'vobject'],
    packages = [ 'khard' ],
    entry_points = {
        'console_scripts': [ 'khard = khard.khard:main' ]
    },
)
