Davcontroller
-------------

Khard also contains a helper script called davcontroller. It's designed to
create and remove address books and calendars at the server. I have created
davcontroller cause my previously used CalDAV server (Darwin calendarserver)
offered no simple way to create new address books and calendars. But
davcontroller should be considered as a hacky solution and it's only tested
against the Darwin calendarserver. So if your CalDAV server offers a way to
create new address books and calendars I recommend to prefer that method over
davcontroller.

If you nonetheless want to try davcontroller, you have to install the
CalDAVClientLibrary first. Unfortunately that library isn't compatible to
python3 so you have to create an extra python2 virtual environment and install
in there:

.. code-block:: shell

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

This small script helps to create and remove new address books and calendars at
the carddav and caldav server.

List available resources:

.. code-block:: shell

   davcontroller -H example.com -p 11111 -u USERNAME -P PASSWORD list

Possible actions are: list, new-addressbook, new-calendar and remove. After
creating or removing you must adapt your vdirsyncer config.
