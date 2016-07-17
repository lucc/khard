khard
=====

Khard is an address book for the Linux console. It creates, reads, modifies and removes carddav
address book entries at your local machine. Khard is also compatible to the email clients mutt and
alot and the SIP client twinkle. You can find more information about khard and the whole
synchronization process
[here](http://eric-scheibler.de/en/blog/2014/10/Sync-calendars-and-address-books-between-Linux-and-Android/).

Khard is developed and tested on Debian operating system, version 7 and 8 but should run on
all Unix-like systems.

If you encounter bugs, please contact me via email: email (at) eric-scheibler (dot) de.

Warning: If you want to create or modify contacts with khard, beware that the vcard standard is very
inconsistent and lacks interoperability. Different actors in that sector have defined their own
extensions and even produce non-standard output. A good example is the type value, which is tied to
phone numbers, email and post addresses. Khard tries to avoid such incompatibilities but if you sync
your contacts with an Android or iOS device, expect problems. You are on the save side, if you only
use khard to read contacts. For further information about the vcard compatibility issues have a look
into [this blog post](http://alessandrorossini.org/2012/11/15/the-sad-story-of-the-vcard-format-and-its-lack-of-interoperability/).

With version 0.11.0, khard changed from python2 to python3.  So if you come from a prior khard
version, it may be necessary to reinstall in a newly created python3 virtual environment.


Prerequisites
-------------

You have to install and configure a caldav and carddav server. I recommend
[Baïkal](http://baikal-server.com).

Then you must synchronize the calendars and address books to your local machine with
[vdirsyncer](https://github.com/untitaker/vdirsyncer).

And you need pip to install python modules:

```
sudo aptitude install python-setuptools
sudo easy_install pip
```


Installation
------------

Khard is installable via pip. I recommend virtualenv to create a separate python3 environment. So
your system stays clean. Additionally you don't have to struggle with different python instances,
especially if your operating system still defaults to python2.

```
# install virtualenv package
sudo pip install virtualenv
# create folder for all virtualenv's and put ~/.virtualenvs/bin in your shell's executable path
mkdir ~/.virtualenvs
# create new python3 virtual environment with the name "khard"
virtualenv -p python3 ~/.virtualenvs/khard
# to install khard, use the pip command from that newly created environment
# otherwise it would be installed in the users home directory
~/.virtualenvs/khard/bin/pip install khard
# create subfolder for symlinks of local binaries
# and don't forget to add it to your shell's executable path too
mkdir ~/.virtualenvs/bin
# create a symlink to the local binary folder
ln -s ~/.virtualenvs/khard/bin/khard ~/.virtualenvs/bin
```

More information about virtualenv at http://docs.python-guide.org/en/latest/dev/virtualenvs/

To get the example config file and the other extra data, you can clone from git:

```
git clone https://github.com/scheibler/khard.git
cd khard/
```

Or download and extract with pip:

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
khard new -a "address book name"
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
""" | khard new -a "address book name"
```

or create from input template file:

```
khard new -a "address book name" -i contact.yaml
```

You may get an empty contact template with the following command:

```
khard export --empty-contact-template -o empty.yaml
```


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


mutt
----

Khard may be used as an external address book for the email client mutt. To accomplish that, add the
following to your mutt config file (mostly ~/.mutt/muttrc):

```
set query_command= "khard email --parsable %s"
bind editor <Tab> complete-query
bind editor ^T    complete
```

Then you can complete email addresses by pressing the Tab-key in mutt's new mail dialog. If your
address books contain hundreds or even thousands of contacts and the query process is very slow, you
may try the --search-in-source-files option to speed up the search:

```
set query_command= "khard email --parsable --search-in-source-files %s"
```

To add email addresses to khard's address book, you may also add the following lines to your muttrc file:

```
macro index,pager A \
    "<pipe-message>khard add-email<return>" \
    "add the sender email address to khard"
```

Then navigate to an email message in mutt's index view and press "A" to start the address import dialog.


Alot
----

Add the following lines to your alot config file:

```
[accounts]
    [[youraccount]]
        [[[abook]]]
            type = shellcommand
            command = khard email --parsable
            regexp = '^(?P<email>[^@]+@[^\t]+)\t+(?P<name>[^\t]+)'
            ignorecase = True
```


Twinkle
-------

For those who also use the SIP client twinkle to take phone calls, khard can be used to query
incoming numbers. The plugin tries to find the incoming caller id and speaks it together with the
phone's ring tone. The plugin needs the following programs:

```
sudo aptitude install ffmpeg espeak sox mpc
```

sox and ffmpeg are used to cut and convert the new ring tone and espeak speaks the caller id.  mpc is a client
for the music player daemon (mpd). It's required to stop music during an incoming call. Skip the last,
if you don't use mpd. Don't forget to set the "stop_music"-parameter in the config.py file to
    False too.

After the installation, copy the scripts and sounds folders to your twinkle config folder:

```
cp -R misc/twinkle/* ~/.twinkle/
```

Then edit your twinkle config file (mostly ~/.twinkle/twinkle.cfg) like this:

```
# RING TONES
# We need a default ring tone. Otherwise the phone would not ring at all, if something with the
# custom ring tone creation goes wrong.
ringtone_file=/home/USERNAME/.twinkle/sounds/incoming_call.wav
ringback_file=/home/USERNAME/.twinkle/sounds/outgoing_call.wav

# SCRIPTS
script_incoming_call=/home/USERNAME/.twinkle/scripts/incoming_call.py
script_in_call_answered=
script_in_call_failed=/home/USERNAME/.twinkle/scripts/incoming_call_failed.py
script_outgoing_call=
script_out_call_answered=
script_out_call_failed=
script_local_release=/home/USERNAME/.twinkle/scripts/incoming_call_ended.py
script_remote_release=/home/USERNAME/.twinkle/scripts/incoming_call_ended.py
```


Zsh
---

The file misc/zsh/_khard contains a zsh completion definition for khard.

Install by copying to a directory where zsh searches for completion functions (the $fpath array).
If you, for example, put all completion functions into the folder ~/.zsh/completions you must add
the following to your zsh main config file:

```
fpath=( $HOME/.zsh/completions $fpath )
autoload -U compinit
compinit
```


sdiff
-----

Use the wrapper script misc/sdiff/sdiff_khard_wrapper.sh if you want to use sdiff as your contact
merging tool. Just make the script executable and set it as your merge editor in khard's config file:

```
merge_editor = /path/to/sdiff_khard_wrapper.sh
```


Related projects
----------------

If you need a console based calendar too, try out [khal](https://github.com/geier/khal).

