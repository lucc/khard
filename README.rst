khard
=====

Khard is an address book for the Linux console. It creates, reads, modifies and
removes carddav address book entries at your local machine. Khard is also
compatible to the email client mutt and the SIP client twinkle.

Prerequisites
-------------

You have to install and configure a caldav and carddav server. For example you
could use calendarserver: https://wiki.debian.org/HowTo/CalendarServer

Then you must synchronize the calendars and address books to your local machine
with vdirsyncer: https://github.com/untitaker/vdirsyncer.


Installation
------------

Pull from git::

    git clone https://github.com/scheibler/khard.git
    cd khard/

And install::

    python setup.py install --user

Next copy the example config file and adapt it's contents to your needs::

    mkdir ~/.config/khard/
    cp khard.conf.example ~/.config/khard/khard.conf

Khard also contains a helper utility called davcontroller. It's designed to
create and remove address books and calendars at the server. To use it, you
have to install the CalDAVClientLibrary like this::

    sudo aptitude install subversion
    svn checkout http://svn.calendarserver.org/repository/calendarserver/CalDAVClientLibrary/trunk CalDAVClientLibrary
    cd CalDAVClientLibrary
    python setup.py install --user


Usage
-----

After you have created a new address book or calendar and you have synced it to
your local machine, you can list all available contacts with the following
command::

    khard list

Or if you have more than one address book and you want to filter the output::

    khard list -a family,friends

Searching is possible too::

    khard list -s John

The list only shows the first phone number and email address. If you want to
view all contact's details you type::

    khard details -s John

Add new contact.  The template for the new contact opens in the text editor,
which you set in the khard.conf file.

::

    khard new -a address_book_name

Use the following to modify the contact after successful creation::

    khard modify -s John

To delete it, write "remove" instead.


davcontroller
-------------

This small utility helps to create and remove new address books and calendars
at the carddav and caldav server.

List available resources::

    davcontroller -H example.com -p 11111 -u USERNAME -P PASSWORD list

Possible actions are: list, new-addressbook, new-calendar and remove. After
creating or removing you must adapt your vdirsyncer config.


mutt
----

Khard can be used as an external address book for the email client mutt. To
accomplish that, add the following to your mutt config file (mostly
~/.mutt/muttrc)::

    set query_command= "khard mutt --search '%s'"
    bind editor <Tab> complete-query
    bind editor ^T    complete

Then you can complete email addresses by pressing <tab> in mutt's new mail
dialog.


Twinkle
-------

For those who also use the SIP client twinkle to take phone calls, khard can be
used to query incoming numbers. The plugin tries to find the incoming caller id
and speaks it together with the phone's ring tone. The plugin needs the
following programs::

    sudo aptitude install ffmpeg espeak sox mpc

sox and ffmpeg are used to cut and convert the new ring tone and espeak speaks
the caller id.  mpc is a client for the music player daemon (mpd). It's needed
to stop music during an incoming call. Skip the last, if you don't use mpd.
Don't forget to set the "stop_music"-parameter in the ``config.py`` file to False
too.

After the installation, copy the scripts and sounds folders to your twinkle
config folder::

    cp -R twinkle-plugin/scripts twinkle-plugin/sounds ~/.twinkle/

Then edit your twinkle config file (mostly ~/.twinkle/twinkle.cfg) like this::

    # RING TONES
    # We need a default ring tone. Otherwise the phone would not ring at all, if
    # something with the custom ring tone creation goes wrong.
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


Related projects
----------------

If you need a console based calendar too, try out khal: https://github.com/geier/khal

