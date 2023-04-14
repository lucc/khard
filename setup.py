# -*- coding: utf-8 -*-

# tutorials:
#  - https://packaging.python.org/en/latest/distributing.html
#  - https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
#  - https://gehrcke.de/2014/02/distributing-a-python-command-line-application/

from setuptools import setup

with open('README.md', 'rb') as f:
    readme = f.read().decode("utf-8")

setup(
    long_description=readme,
    long_description_content_type='text/markdown',
    extras_require={'doc': [
        'sphinx',
        'sphinx-autoapi',
        'sphinx-autodoc-typehints'
    ]},
    packages=['khard', 'khard.helpers'],
    package_data={'khard': ['data/*']},
    test_suite="test",
    include_package_data=True,
)
