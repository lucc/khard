Manpage
=======

Location
--------

The config file for khard is looked up at $XDG_CONFIG_HOME/khard/khard.conf.
If the environment variable $XDG_CONFIG_HOME is unset ~/.config/ is used in its
stead.

The location can be changed with the environment variable $KHARD_CONFIG or the
command line option *-c* (which takes precedence).

Description
-----------

This is the example config file:

.. literalinclude :: ../../../misc/khard/khard.conf.example
   :language: ini
