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

### Configuration ###

There is an [example config file](misc/khard/khard.conf.example) which you can
copy to the default config file location: `~/.config/khard/khard.conf`.  See
[the docs](doc/source/index.rst#configuration) for more.

### Davcontroller ###

Khard also contains a helper script called davcontroller. It's designed to create and remove address
books and calendars at the server. I have created davcontroller cause my previously used CalDAV
server (Darwin calendarserver) offered no simple way to create new address books and calendars. But
davcontroller should be considered as a hacky solution and it's only tested against the Darwin
calendarserver. So if your CalDAV server offers a way to create new address books and calendars I
recommend to prefer that method over davcontroller.

If you nonetheless want to try davcontroller, you have to install the CalDAVClientLibrary first.
Unfortunately that library isn't compatible to python3 so you have to create an extra python2
virtual environment and install in there:

```
# create python2 virtual environment
virtualenv -p python2 ~/.virtualenvs/davcontroller
# get library from svn repository
sudo aptitude install subversion
svn checkout http://svn.calendarserver.org/repository/calendarserver/CalDAVClientLibrary/trunk CalDAVClientLibrary
cd CalDAVClientLibrary
# install library
~/.virtualenvs/davcontroller/bin/python setup.py install
# start davcontroller script
~/.virtualenvs/davcontroller/bin/python /path/to/khard-x.x.x/misc/davcontroller/davcontroller.py
```



davcontroller
-------------

This small script helps to create and remove new address books and calendars at the carddav and
caldav server.

List available resources:

```
davcontroller -H example.com -p 11111 -u USERNAME -P PASSWORD list
```

Possible actions are: list, new-addressbook, new-calendar and remove. After creating or removing you
must adapt your vdirsyncer config.


Related projects
----------------

If you need a console based calendar too, try out [khal](https://github.com/geier/khal).
