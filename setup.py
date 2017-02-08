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

# get long description of package (either rst or markdown)
# see https://gist.github.com/aubricus/9184003#gistcomment-1488025
with open('README.md', 'rb') as f:
    ld_md = f.read().decode("utf-8")
try:
    # pypi wants the long description as restructured text (rst)
    # so try to convert from markdown to rst
    import pypandoc
    ld = pypandoc.convert_text(ld_md, 'rst', format='md')
except Exception:
    # else use long description in markdown format
    ld = ld_md

setup(
    name = 'khard',
    version = re.sub("[^0-9.]", "", open('khard/version.py').read()),
    author = 'Eric Scheibler',
    author_email = 'email@eric-scheibler.de',
    url = 'https://github.com/scheibler/khard/',
    description = 'A console carddav client',
    long_description = ld,
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
