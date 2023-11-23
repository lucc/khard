Contributing
============

**Thank you for considering contributing to khard!**

.. toctree::
   :maxdepth: 1

   self
   bench
   API Reference <autoapi/index>

Khard is developed on `Github`_ where you are welcome to post `bug reports`_,
`feature requests`_ or join the discussion in general.

Bug reports
-----------

If you want to report a bug keep in mind that the following things make it much
easier for maintainers to help:

- update to the latest version if possible and verify the bug there
- report the version(s) that are affected
- state the python version you are using
- if there are stack tracebacks post them with your bug report
- supply a minimal configuration (config file and vCards) to reproduce the
  error

Feature requests
----------------

Please stick to the following standards when you open pull requests:

- Khard's development tries to follow `Vincent's branching model`_ so normal
  pull requests should be made against the `develop`_ branch. Only important
  bug fixes that affect the current release should be opened against `master`_.
- Write "good" commit messages, especially a proper subject line.  This is also
  explained in `the Git book`_.
- Format your python code according to `PEP 8`_.  Tools like `pylint`_ also
  help in writing maintainable code.
- Khard has a test suite, please provide tests for bugs that you fix and also
  for new code and new features that are introduced.
- Please verify *all* tests pass before sending a pull request, they will be
  checked again in CI but it might be a lot faster to check locally first:
  |travis|

Development
-----------

In order to start coding you need to fetch the ``develop`` branch:

.. code-block:: shell

  git clone https://github.com/lucc/khard
  cd khard

It is recommended to create a `virtualenv`_ to isolate the development
environment for Khard from your system's Python installation:

.. code-block:: shell

  python3 -m venv khard-dev-venv
  . khard-dev-venv/bin/activate

The you can install the dependencies with ``pip``:

.. code-block:: shell

  pip3 install --editable .
  khard --help

If you have the `Nix`_ package manager installed you can use the ``flake.nix``
that is provided with Khard.  It provides an isolated Python version with all
dependencies with ``nix develop``.

.. _bug reports: https://github.com/lucc/khard/issues
.. _the Git book: https://www.git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project#_commit_guidelines
.. _develop: https://github.com/lucc/khard/tree/develop
.. _feature requests: https://github.com/lucc/khard/pulls
.. _Github: https://github.com/lucc/khard
.. _master: https://github.com/lucc/khard/tree/master
.. _Nix: https://nixos.org
.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. _pylint: https://pylint.readthedocs.io/en/latest/
.. |travis| image:: https://github.com/lucc/khard/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/lucc/khard/actions/workflows/ci.yml
   :alt: ci status
.. _Vincent's branching model:
   http://nvie.com/posts/a-successful-git-branching-model/
.. _virtualenv: https://virtualenv.pypa.io/en/stable/
