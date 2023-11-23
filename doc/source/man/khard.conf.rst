khard.conf
==========

Summary
-------

The config file for :program:`khard` is a plain text file with an ini-like
syntax.  Many options have a corresponding command line option.  The only
mandatory section in the config file is the definition of the available address
books.

Location
--------

The file is looked up at :file:`$XDG_CONFIG_HOME/khard/khard.conf`. If the
environment variable :file:`$XDG_CONFIG_HOME` is unset :file:`~/.config/` is
used in its stead.

The location can be changed with the environment variable :file:`$KHARD_CONFIG`
or the command line option :option:`-c` (which takes precedence).

Syntax
------

The syntax of the config file is ini-style dialect.  It is parsed with
the configobj library.  The precise definition of the corresponding ini syntax
can be found at
https://configobj.readthedocs.io/en/latest/configobj.html#the-config-file-format
.

It supports sections marked with square brackets and nested sections with more
square brackets.  Each section contains several keys with values delimited by
equal signs.  The values are typed and type checked.

Options
-------

The config file consists of these four sections:

addressbooks
  This section contains several subsections, but at least one. Each subsection
  can have an arbitrary name which will be the name of an addressbook known to
  khard.  Each of these subsections **must** have a *path* key with the path to
  the folder containing the vCard files for that addressbook.  The *path* value
  supports environment variables and tilde prefixes.  :program:`khard` expects
  the vCard files to hold only one VCARD record each and end in a :file:`.vcf`
  extension.

general
  This section allows one to configure some general features about khard.  The
  following keys are available in this section:

  - *debug*: a boolean indication whether the logging level should be set to
    *debug* by default (same effect as the :option:`--debug` option on the
    command line)
  - *default_action*: the default action/subcommand to use if the first non
    option argument does not match any of the available subcommands
  - *editor*: the text editor to use to edit address book entries, if not given
    :file:`$EDITOR` will be used
  - *merge_editor*: a command used to merge two cards interactively, if not
    given, :file:`$MERGE_EDITOR` will be used

contact table
  This section is used to configure the behaviour of different output listings
  of khard.  The following keys are available:

  - *display*: which part of the name to use in listings; this can be one of
    ``first_name``, ``last_name`` or ``formatted_name``
  - *group_by_addressbook*: whether or not to group contacts by address book in
    listings
  - *localize_dates*: whether to localize dates or to use ISO date formats
  - *preferred_email_address_type*: labels of email addresses to prefer
  - *preferred_phone_number_type*: labels of telephone numbers to prefer
  - *reverse*: whether to reverse the order of contact listings or not
  - *show_nicknames*: whether to show nick names
  - *show_uids*: whether to show uids
  - *show_kinds*: whether to show kinds
  - *sort*: field by which to sort contact listings

vcard
  - *private_objects*: a list of strings, these are the names of private vCard
    fields (starting with ``X-``)  that will be loaded and displayed by khard
  - *search_in_source_files*: whether to search in the vCard files before
    parsing them in order to speed up searches
  - *skip_unparsable*: whether to skip unparsable vCards, otherwise khard
    exits on the first unparsable card it encounters
  - *preferred_version*: the preferred vCard version to use for new cards

Example
-------

This is the :download:`example config file <../examples/khard.conf.example>`:

.. literalinclude :: ../examples/khard.conf.example
   :language: ini
