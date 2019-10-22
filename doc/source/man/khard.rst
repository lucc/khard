Manpage
=======

Synopsis
--------

khard [-c CONFIG] [--debug] [--skip-unparsable] SUBCOMMAND ...

khard -h|--help

khard -v|--version

Description
-----------

Khard is an address book for the Linux command line.  It can read, create,
modify and delete carddav address book entries.  Khard only works with a local
store of VCARD files.  It is intended to be used in conjunction with other
programs like an email client, text editor, vdir synchronizer or VOIP client.

Options
-------

-c CONFIG, --config CONFIG
  configuration file (default: ~/.config/khard/khard.conf)

--debug
  output debugging information

--skip-unparsable
  skip unparsable vcards when reading the address books

Subcommands
-----------

The functionality of khard is divided into several subcommands.  All of these
have their own help text which can be seen with ``khard SUBCOMMAND --help``.

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

details
  display detailed information about one contact
export
  export a contact to the custom yaml format that is also used for editing and
  creating contacts

Modifying subcommands
~~~~~~~~~~~~~~~~~~~~~

These subcommands are used to modify contacts.

source
  edit the vcard file of a contact directly
new
  create a new contact
add-email
  Extract email address from the "From:" field of an email header and add to an
  existing contact or create a new one
merge
  merge two contacts
modify
  edit the data of a contact
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

Configuration
-------------

See :manpage:`khard.conf(5)`.
