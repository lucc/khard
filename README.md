khard
=====

Khard is an address book for the Linux console. It creates, reads, modifies and removes carddav
address book entries at your local machine. Khard is also compatible to the email clients mutt and
alot and the SIP client twinkle. You can find more information about khard and the whole
synchronization process
[here](http://eric-scheibler.de/en/blog/2014/10/Sync-calendars-and-address-books-between-Linux-and-Android/).

Khard is developed and tested on Debian operating system, versions 7, 8 and 9 but should run
on all Unix-like systems.

If you encounter bugs, please contact me via email: email (at) eric-scheibler (dot) de.

Warning: If you want to create or modify contacts with khard, beware that the vcard standard is very
inconsistent and lacks interoperability. Different actors in that sector have defined their own
extensions and even produce non-standard output. A good example is the type value, which is tied to
phone numbers, email and post addresses. Khard tries to avoid such incompatibilities but if you sync
your contacts with an Android or iOS device, expect problems. You are on the safe side, if you only
use khard to read contacts. For further information about the vcard compatibility issues have a look
into [this blog post](http://alessandrorossini.org/2012/11/15/the-sad-story-of-the-vcard-format-and-its-lack-of-interoperability/).

With version 0.11.0, khard changed from python2 to python3.  So if you come from a prior khard
version, it may be necessary to reinstall in a newly created python3 virtual environment.



Prerequisites
-------------

You have to install and configure a caldav and carddav server. I recommend
[Baïkal](https://github.com/sabre-io/Baikal).

Then you must synchronize the calendars and address books to your local machine with
[vdirsyncer](https://github.com/untitaker/vdirsyncer).

And you need pip to install python modules:

```
sudo aptitude install python-setuptools
sudo easy_install pip
```

Installation
------------

[![Packaging
status](https://repology.org/badge/tiny-repos/khard.svg)](https://repology.org/project/khard/versions)
Khard is already packaged for quite some distributions.  Chances are you can
install it with your default package manager.  Further instructions can be
found in the [documentation](doc/source/index.rst#installation).

### Configuration ###

To get the example config file and the other extra data, you can clone from git (see above) or
download package from pypi:

```
pip install --download /tmp --no-deps --no-use-wheel khard
tar xfz /tmp/khard-x.x.x.tar.gz
rm /tmp/khard-x.x.x.tar.gz
cd khard-x.x.x/
```

Now copy the example config file and adapt it's contents to your needs:

```
mkdir ~/.config/khard/
cp misc/khard/khard.conf.example ~/.config/khard/khard.conf
```

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

Usage
-----

The following subsections give an overview of khard's main features.

You may get general help and all available actions with

```
khard --help
```

If you need help on a specific action, use:

```
khard action --help
```

Beware, that the order of the command line parameters matters.

### Show contacts ###

After you have created a new address book or calendar and you have synced it to your local machine,
you can list all available contacts with the following command:

```
khard list
```

or if you have more than one address book and you want to filter the output:

```
khard list -a addressbook1,addressbook2
```

The resulting contact table only contains the first phone number and email address. If you want to view all contact
details you can pick one from the list:

```
khard details
```

or search for it:

```
khard details [--strict-search] name of contact
```

or select the contact by it's uid, which you can find at the contacts table:

```
khard details -u ID
```

The parameters -a and -u from the examples above are always optional. If you don't use them or your
input produces unambiguous results, you may pick the contacts from a list instead.

The search parameter searches in all data fields. Therefore you aren't limited to the contact's name
but you also could for example search for a part of a phone number, email address or post address.
However if you explicitly want to narrow your search to the name field, you may use the
--strict-search parameter instead.


### Create contact ###

Add new contact with the following command:

```
khard new [-a "address book name"]
```

The template for the new contact opens in the text editor, which you can set in the khard.conf file.
It follows the yaml syntax.

Alternatively you can create the contact from stdin:

```
echo """
First name : John
Last name  : Smith
Email :
    work : john.smith@example.org
Phone :
    home : xxx 555 1234
Categories :
    - cat1
    - cat2
    - cat3
""" | khard new [-a "address book name"]
```

or create from input template file:

```
khard new -i contact.yaml [-a "address book name"]
```

You may get an empty contact template with the following command:

```
khard export --empty-contact-template -o empty.yaml
```

Per default khard creates vcards of version 3.0. If your other contact applications support vcards
of the more recent version 4.0, you may change this with the option --vcard-version. Example:

```
khard new --vcard-version=4.0 [-a "address book name"]
```

For a more permanent solution you may set the preferred_version parameter in the vcard section of
the khard config file (see misc/khard/khard.conf.example for more details).  But beware, that khard
cannot convert already existing contacts from version 3.0 to 4.0. Therefore this setting is not
applicable to the modify action.


### Edit contacts ###

Use the following to modify the contact after successful creation:

```
khard modify [-a addr_name] [-u uid|search terms [search terms ...]]
```

If you want to edit the contact elsewhere, you can export the filled contact template:

```
khard export -o contact.yaml [-a addr_name] [-u uid|search terms [search terms ...]]
```

Edit the yaml file and re-import either through stdin:

```
cat contact.yaml | khard modify [-a addr_name] [-u uid|search terms [search terms ...]]
```

or file name:

```
khard modify -i contact.yaml [-a addr_name] [-u uid|search terms [search terms ...]]
```

If you want to merge contacts use the following to select a first and then a second contact:

```
khard merge [-a source_abook] [-u uid|search terms [search terms ...]] [-A target_abook] [-U target_uid|-t target_search_terms]
```

You will be launched into your merge_editor ( see the "merge_editor" option in khard.conf)
where you can merge all changes from the first selected contact onto the second.
Once you are finished, the first contact is deleted and the second one updated.

Copy or move contact:

```
khard copy [-a source_abook] [-u uid|search terms [search terms ...]] [-A target_abook]
khard move [-a source_abook] [-u uid|search terms [search terms ...]] [-A target_abook]
```

Remove contact:

```
khard remove [-a addr_name] [-u uid|search terms [search terms ...]]
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
