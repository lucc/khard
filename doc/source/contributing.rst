Contributing
============

**Thank you for considering contributing to khard!**

.. toctree::
   :maxdepth: 1

   self
   bench

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
- supply a minimal configuration (config file and vcards) to reproduce the
  error

Feature requests
----------------

Please stick to the following standards when you open pull requests:

- Khard's development tries to follow `Vincent's branching model`_ so normal
  pull requests should be made against the `develop`_ branch. Only important
  bug fixes that affect the current release should be opened against `master`_.
- Write "good" commit messages, especially a proper subject line.  This is also
  explained in `the Git book`_.
- Format your python code according to `PEP 8`_.
- Khard has a test suite, please provide tests for bugs that you fix and also
  for new code and new features that are introduced.
- Please verify *all* tests pass before sending a pull request, they will be
  checked again by travis but it might be a lot faster to check locally first:
  |travis|

Development
-----------

In order to start coding you need to fetch the develop branch:

.. code-block:: shell

  git clone https://github.com/scheibler/khard
  cd khard
  git fetch --all
  git checkout develop
  python -m kard --help
  # or
  pip3 install --editable .
  khard --help

Alternatively you can use the ``setup.py`` script directly.  If you want to
isolate khard from your system Python environment you can use a `virtualenv`_
to do so.

.. _bug reports: https://github.com/scheibler/khard/issues
.. _the Git book: https://www.git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project#_commit_guidelines
.. _develop: https://github.com/scheibler/khard/tree/develop
.. _feature requests: https://github.com/scheibler/khard/pulls
.. _Github: https://github.com/scheibler/khard
.. _master: https://github.com/scheibler/khard/tree/master
.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. |travis| image:: https://travis-ci.org/scheibler/khard.svg?branch=develop
   :target: https://travis-ci.org/scheibler/khard
   :alt: build status
.. _Vincent's branching model:
   http://nvie.com/posts/a-successful-git-branching-model/
.. _virtualenv: https://virtualenv.pypa.io/en/stable/
