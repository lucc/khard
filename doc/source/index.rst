#################################
Welcome to khard's documentation!
#################################

.. toctree::
   :maxdepth: 1

   self
   commandline
   scripting
   contributing
   man
   indices

Khard is an address book for the Unix command line.  It can read, create,
modify and delete vCard address book entries.  Khard only works with a local
store of vCard files.  It is intended to be used in conjunction with other
programs like an email client, text editor, vdir synchronizer or VOIP client.


Installation
============

.. image:: https://repology.org/badge/tiny-repos/khard.svg
   :target: https://repology.org/project/khard/versions
   :alt: Packaging status

Khard is available as a native package for some \*nix distributions so you
should check your package manager first.  If you want or need to install
manually you can use the release from `PyPi`_:

.. code-block:: shell

  pip3 install khard

If you want to help the development or need more advanced installation
instructions see :doc:`contributing`.

If you need a tarball use the one from `PyPi`_ and not from the Github release
page.  These are missing an auto generated python file.

.. _PyPi: https://pypi.python.org/pypi/khard/

Configuration
=============

The configuration file of khard is stored in the XDG conform config directory.
If the environment variable ``$XDG_CONFIG_HOME`` is set, it is
``$XDG_CONFIG_HOME/khard/khard.conf`` and it defaults to
``~/.config/khard/khard.conf`` otherwise.

An :download:`example configuration <examples/khard.conf.example>` is provided
in the source tree.  It looks like this:

.. literalinclude:: examples/khard.conf.example
   :language: ini
