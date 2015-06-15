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


Prerequisites
-------------

You have to install and configure a caldav and carddav server. I recommend
[Baïkal](http://baikal-server.com).

Then you must synchronize the calendars and address books to your local machine with vdirsyncer:
https://github.com/untitaker/vdirsyncer.

And you need pip to install python modules:

```
sudo aptitude install python-setuptools
sudo easy_install pip
```


Installation
------------

Khard is installable via pip. You can choose between the following three methods:

1. Install system wide:

```
sudo pip install khard
```

But that's not recommended due to security issues and cause it can damage dependencies of other
python modules.

2. Install into user space:

```
pip install --user khard
```

Then you can find the executable under ~/.local/bin.

3. Use virtualenv to create a separate python environment for every module. That's recommended cause
   it keeps your system clean:

```
# install virtualenv package
sudo pip install virtualenv
# create folder for all virtualenv's
mkdir ~/.virtualenvs
# create new virtual environment with the name "khard"
virtualenv ~/.virtualenvs/khard
# to install khard, use the pip command from that newly created environment
# otherwise it would be installed in the users home directory
~/.virtualenvs/khard/bin/pip install khard
# create a symlink to the local binary folder
ln -s ~/.virtualenvs/khard/bin/khard ~/bin
```

More information about virtualenv at http://docs.python-guide.org/en/latest/dev/virtualenvs/

To get the example config file and the twinkle plugin you can clone from git:

```
git clone https://github.com/scheibler/khard.git
cd khard/
```

Or download and extract with pip:

```
pip install --download /tmp --no-deps --no-use-wheel khard
tar xfz /tmp/khard-0.2.1.tar.gz
rm /tmp/khard-0.2.1.tar.gz
cd khard-0.2.1/
```

Now copy the example config file and adapt it's contents to your needs:

```
mkdir ~/.config/khard/
cp khard.conf.example ~/.config/khard/khard.conf
```

Khard also contains a helper utility called davcontroller. It's designed to create and remove
address books and calendars at the server. I have created davcontroller cause my previously used
CalDAV server (Darwin calendarserver) offered no simple way to create new address books and
calendars. But davcontroller should be considered as a hacky solution and it's only tested against
the Darwin calendarserver. So if your CalDAV server offers a way to create new address books and
calendars I recommend to prefer that method over davcontroller.

If you nonetheless want to try davcontroller, you have to install the CalDAVClientLibrary first:

```
sudo aptitude install subversion
svn checkout http://svn.calendarserver.org/repository/calendarserver/CalDAVClientLibrary/trunk CalDAVClientLibrary
cd CalDAVClientLibrary
```

For user space installation:

```
python setup.py install --user
```

Or if you use the virtual environment:

```
~/.virtualenvs/khard/bin/python setup.py install
ln -s ~/.virtualenvs/khard/bin/davcontroller ~/bin
```


Usage
-----

After you have created a new address book or calendar and you have synced it to your local machine,
you can list all available contacts with the following command:

```
khard list
```

Or if you have more than one address book and you want to filter the output:

```
khard list -a family,friends
```

Searching is possible too:

```
khard list -s John
```

The list only shows the first phone number and email address. If you want to view all contact's
details you type:

```
khard details -s John
```

Add new contact.  The template for the new contact opens in the text editor, which you set in the
khard.conf file.

```
khard new -a address_book_name
```

Use the following to modify the contact after successful creation:

```
khard modify -s John
```

To delete it, write "remove" instead. Use "source", to open the Vcard file directly.


davcontroller
-------------

This small utility helps to create and remove new address books and calendars at the carddav and
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
set query_command= "khard mutt --search '%s'"
bind editor <Tab> complete-query
bind editor ^T    complete
```

Then you can complete email addresses by pressing <tab> in mutt's new mail dialog.

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
[[[abook]]]
  type = shellcommand
  command = khard alot -s
  regexp = \"(?P<name>.+)\"\s*<(?P<email>.*.+?@.+?)>
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
cp -R twinkle-plugin/scripts twinkle-plugin/sounds ~/.twinkle/
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


Related projects
----------------

If you need a console based calendar too, try out khal: https://github.com/geier/khal

