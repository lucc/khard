khard
=====

Khard is an address book for the Unix console. It creates, reads, modifies and
removes vCard address book entries at your local machine. Khard is also
compatible to the email clients mutt and alot and the SIP client twinkle. You
can find more information about khard and the whole synchronization process
[here][blog].

Warning: If you want to create or modify contacts with khard, beware that the
vcard standard is very inconsistent and lacks interoperability. Different
actors in that sector have defined their own extensions and even produce
non-standard output. A good example is the type value, which is tied to phone
numbers, email and post addresses. Khard tries to avoid such incompatibilities
but if you sync your contacts with an Android or iOS device, expect problems.
You are on the safe side, if you only use khard to read contacts. For further
information about the vcard compatibility issues have a look into [this blog
post][sad].

Installation
------------

[![Packaging status][repos-badge]][repos]

Khard is already packaged for quite some distributions.  Chances are you can
install it with your default package manager.  Releases are also published on
[PyPi](https://pypi.org/project/khard/) and can be installed with `pip`.
Further instructions can be found in the
[documentation](https://khard.readthedocs.io/en/latest/#installation).

Usage
-----

[![Documentation Status][docs-badge]][docs]

There is an [example config file](doc/source/examples/khard.conf.example) which
you can copy to the default config file location: `~/.config/khard/khard.conf`.
`khard` has several subcommands which are all documented by their `--help`
option. [The docs][docs] also have a chapter on [command line
usage](https://khard.readthedocs.io/en/latest/commandline.html) and
[configuration](https://khard.readthedocs.io/en/latest/#configuration).

In order to build the documentation locally you need
[Sphinx](https://www.sphinx-doc.org/).  It can be build from the Makefile in
the `doc` directory.

Development
-----------

[![ci-badge]][ci]

Khard is developed [on GitHub](https://github.com/scheibler/khard) where you
are welcome to post [bug reports](https://github.com/scheibler/khard/issues)
and [feature requests](https://github.com/scheibler/khard/pulls).  Also see the
[notes for contributors](CONTRIBUTING.rst).

Authors
-------

Khard was started by [Eric Scheibler](http://eric-scheibler.de) and is
currently maintained by @lucc.  [Several
people](https://github.com/scheibler/khard/graphs/contributors) have
contributed over the years.

Related projects
----------------

If you need a console based calendar too, try out
[khal](https://github.com/geier/khal).

  [blog]: http://eric-scheibler.de/en/blog/2014/10/Sync-calendars-and-address-books-between-Linux-and-Android/
  [sad]: http://alessandrorossini.org/2012/11/15/the-sad-story-of-the-vcard-format-and-its-lack-of-interoperability/
  [repos]: https://repology.org/project/khard/versions
  [repos-badge]: https://repology.org/badge/tiny-repos/khard.svg
  [docs]: https://khard.readthedocs.io/en/latest/
  [docs-badge]: https://readthedocs.org/projects/khard/badge/?version=latest
  [ci]: https://github.com/lucc/khard/actions/workflows/ci.yml
  [ci-badge]: https://github.com/lucc/khard/actions/workflows/ci.yml/badge.svg
