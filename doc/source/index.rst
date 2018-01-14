.. khard documentation master file, created by
   sphinx-quickstart on Sun Jan 14 10:35:27 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to khard's documentation!
=================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Khard is an address book for the Linux command line.  It can read, create,
modify and delete carddav address book entries.  Khard works with an address
book on your local machine, but you can use it together with other programs to


Installation
============

Khard is available as a native package for some Linux distributions so you
should check your package manager first.  If you want to actively develop khard
or it is not available for your distribution you can use Python's native
installation methods via ``pip`` or the ``setup.py`` script directly.

The latest release should be available from `PyPi`_ or you can download a
release tarball from `Github`_.  The development version is available on Github
in the `develop`_ branch.

This means you could install the latest release with:

.. code-block:: shell

  pip install khard

If you want to help the development it might make sense to check out the git
repository:

.. code-block:: shell

  git clone https://github.com/scheibler/khard
  cd khard
  git fetch --all
  git checkout develop
  pip install --editable .

All of these command should also work inside a `virtualenv`_ in order to
isolate the khard installation from other software on your system.

.. _PyPi: https://pypi.python.org/pypi/khard/
.. _Github: https://github.com/scheibler/khard
.. _develop: https://github.com/scheibler/khard/tree/develop
.. _virtualenv: https://virtualenv.pypa.io/en/stable/

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
