khard.conf
==========

Summary
-------

The config file for :manpage:`khard` is a plain text file with an ini-like
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

Description
-----------

This is the example config file:

.. literalinclude :: ../../../misc/khard/khard.conf.example
   :language: ini
