khard
=====

Khard is an address book for the Linux console. It creates, reads, modifies and
removes carddav address book entries at your local machine. Khard is also
compatible to the email clients mutt and alot and the SIP client twinkle. You
can find more information about khard and the whole synchronization process
[here](http://eric-scheibler.de/en/blog/2014/10/Sync-calendars-and-address-books-between-Linux-and-Android/).

Warning: If you want to create or modify contacts with khard, beware that the
vcard standard is very inconsistent and lacks interoperability. Different
actors in that sector have defined their own extensions and even produce
non-standard output. A good example is the type value, which is tied to phone
numbers, email and post addresses. Khard tries to avoid such incompatibilities
but if you sync your contacts with an Android or iOS device, expect problems.
You are on the safe side, if you only use khard to read contacts. For further
information about the vcard compatibility issues have a look into [this blog
post](http://alessandrorossini.org/2012/11/15/the-sad-story-of-the-vcard-format-and-its-lack-of-interoperability/).

Installation
------------

<a href="https://repology.org/project/khard/versions">
    <img src="https://repology.org/badge/tiny-repos/khard.svg"
        alt="Packaging status" align="right">
</a>

Khard is already packaged for quite some distributions.  Chances are you can
install it with your default package manager.  Further instructions can be
found in the [documentation](doc/source/index.rst#installation).

Usage
-----

There is an [example config file](doc/source/examples/khard.conf.example) which
you can copy to the default config file location: `~/.config/khard/khard.conf`.
`khard` has several subcommands which are all documented by their `--help`
option. [The docs](doc/source/index.rst) also have a chapter on [command line
usage](doc/source/commandline.rst) and
[configuration](doc/source/index.rst#configuration).

In order to build the documentation locally you need
[Sphinx](https://www.sphinx-doc.org/).  It can be build from the Makefile in
the [`doc`](doc) directory.

Development
-----------

<a href="https://travis-ci.org/scheibler/khard">
    <img src="https://travis-ci.org/scheibler/khard.svg?branch=develop"
        alt="Build status" align="right">
</a>

Khard is developed [on GitHub](https://github.com/scheibler/khard) where you
are welcome to post [bug reports](https://github.com/scheibler/khard/issues)
and [feature requests](https://github.com/scheibler/khard/pulls).  Also see the
[notes for contributors](doc/source/contributing.rst).

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
