khard
=====

Synopsis
--------

:program:`khard` [:option:`-c` CONFIG] [:option:`--debug`] [:option:`--skip-unparsable`] SUBCOMMAND ...

:program:`khard` :option:`-h` | :option:`--help`

:program:`khard` :option:`-v` | :option:`--version`

Description
-----------

:program:`khard` is an address book for the Unix command line.  It can read, create,
modify and delete vCard address book entries.  :program:`khard` only works with a local
store of vCard files.  It is intended to be used in conjunction with other
programs like an email client, text editor, vdir synchronizer or VOIP client.

Options
-------

.. option:: -c CONFIG, --config CONFIG

  configuration file (default: :file:`~/.config/khard/khard.conf`)

.. option:: --debug

  output debugging information

.. option:: -h, --help

  show a help message and exit

.. option:: --skip-unparsable

  skip unparsable vcards when reading the address books

.. option:: -v, --version

  show program's version number and exit

Subcommands
-----------

The functionality of khard is divided into several subcommands.  All of these
have their own help text which can be seen with ``khard SUBCOMMAND --help``.

Many subcommands accept search terms to limit the number of contacts they
should work on, display or present for selection.  The syntax is described in
:ref:`Search query syntax`.

Listing subcommands
~~~~~~~~~~~~~~~~~~~

These subcommands list information of several contacts who match a search
query.

list
  list all (selected) contacts
birthdays
  list birthdays (sorted by month and day)
email
  list email addresses
phone
  list phone numbers
postaddress
  list postal addresses
filename
  list filenames of all matching contacts

Detailed display
~~~~~~~~~~~~~~~~

These subcommands display detailed information about one subcommand.

show
  display detailed information about one contact, supported output formats
  are "pretty", "yaml" and "vcard"

Modifying subcommands
~~~~~~~~~~~~~~~~~~~~~

These subcommands are used to modify contacts.

edit
  edit the data of a contact, supported formats for editing are "yaml" and
  "vcard"
new
  create a new contact
add-email
  Extract email address from the "From:" field of an email header and add to an
  existing contact or create a new one
merge
  merge two contacts
copy
  copy a contact to a different addressbook
move
  move a contact to a different addressbook
remove
  remove a contact

Other subcommands
~~~~~~~~~~~~~~~~~

addressbooks
  list all address books
template
  print an empty yaml template

Search query syntax
-------------------

Search queries consist of one or more command line arguments.  Each can be a
simple search term or a search term for a specific field.  The field name is
separated from the search term by a colon (``:``) without any spaces.

Spaces in the field name have to be replaced with underscores.

The available fields are the same fields as in the YAML template with the
exception of the five name components (first, last, prefix, suffix,
additional).  But there is the special pseudo field specifier ``name:`` which
will search in *any* name related field (including nicknames and formatted
names).

If a field name is not known the search term is interpreted as a plain search
term and the string (including the colon) is looked up in any field of the
contact.

Configuration
-------------

See :manpage:`khard.conf(5)`.
