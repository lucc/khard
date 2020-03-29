# -*- coding: utf-8 -*-

# tutorials:
#  - https://packaging.python.org/en/latest/distributing.html
#  - https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
#  - https://gehrcke.de/2014/02/distributing-a-python-command-line-application/

from setuptools import setup

with open('README.md', 'rb') as f:
    readme = f.read().decode("utf-8")

setup(
    name='khard',
    author='Eric Scheibler',
    author_email='email@eric-scheibler.de',
    url='https://github.com/scheibler/khard/',
    description='A console carddav client',
    long_description=readme,
    long_description_content_type='text/markdown',
    license='GPL',
    keywords='Carddav console addressbook',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Topic :: Utilities",
        "Topic :: Communications :: Email :: Address Book",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3 :: Only",
    ],
    install_requires=[
        'atomicwrites',
        'configobj',
        'ruamel.yaml',
        'unidecode',
        'vobject'
    ],
    extras_require={'doc': ['sphinx', 'sphinx-autoapi',
                            'sphinx-autodoc-typehints']},
    use_scm_version={'write_to': 'khard/version.py'},
    setup_requires=['setuptools_scm'],
    packages=['khard'],
    entry_points={'console_scripts': ['khard = khard.khard:main']},
    test_suite="test",
    # the dependency ruamel.yaml requires >=3.5
    python_requires=">=3.5",
    include_package_data=True,
)
