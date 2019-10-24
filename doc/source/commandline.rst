Command line usage
==================

The following subsections give an overview of khard's main features. You may
get general help and all available actions as well as detailed information on
all available options for the specific commands with the :option:`--help`
options:

.. code-block:: shell

   khard --help
   khard command --help

Beware, that the order of the command line parameters matters.

Show contacts
-------------

After you have created a new address book and you have synced it to your local
machine, you can list all available contacts with the following command:

.. code-block:: shell

   khard list

or if you have more than one address book and you want to filter the output:

.. code-block:: shell

   khard list -a addressbook1,addressbook2

The resulting contact table only contains the first phone number and email
address. If you want to view all contact details you can pick one from the
list:

.. code-block:: shell

   khard show

or search for it:

.. code-block:: shell

   khard show [--strict-search] name of contact

or select the contact by it's uid, which you can find at the contacts table:

.. code-block:: shell

   khard show -u ID

The parameters :option:`-a` and :option:`-u` from the examples above are always
optional.  They can be given on all subcommands that select one or more
contacts.  If you don't use them or your input produces unambiguous results,
you may pick the contacts from a list instead.

The search parameter searches in all data fields. Therefore you aren't limited
to the contact's name but you also could for example search for a part of a
phone number, email address or post address. However if you explicitly want to
narrow your search to the name field, you may use the :option:`--strict-search`
parameter instead.


Create contact
--------------

Add new contact with the following command:

.. code-block:: shell

   khard new [-a "address book name"]

The template for the new contact opens in the text editor, which you can set in
the config file. It follows the yaml syntax.

Alternatively you can create the contact from stdin:

.. code-block:: shell

   echo "
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
   " | khard new

or create from input template file:

.. code-block:: shell

   khard new -i contact.yaml

You may get an empty contact template with the following command:

.. code-block:: shell

   khard template

Per default khard creates vcards of version 3.0. If your other contact
applications support vcards of the more recent version 4.0, you may change this
with the option :option:`--vcard-version`. Example:

.. code-block:: shell

   khard new --vcard-version=4.0

For a more permanent solution you may set the preferred_version parameter in
the vcard section of the khard config file (see the :download:`example config
file <examples/khard.conf.example>` for more details).  But beware, that khard
cannot convert already existing contacts from version 3.0 to 4.0. Therefore
this setting is not applicable to the modify action.


Edit contacts
-------------

Use the following to modify the contact after successful creation:

.. code-block:: shell

   khard edit [-a addr_name] [-u uid|search terms [search terms ...]]

If you want to edit the contact elsewhere, you can export the filled contact template:

.. code-block:: shell

   khard show --format=yaml -o contact.yaml [-a addr_name] [-u uid|search terms [search terms ...]]

Edit the yaml file and re-import either through stdin:

.. code-block:: shell

   cat contact.yaml | khard edit [-a addr_name] [-u uid|search terms [search terms ...]]

or file name:

.. code-block:: shell

   khard edit -i contact.yaml [-a addr_name] [-u uid|search terms [search terms ...]]

If you want to merge contacts use the following to select a first and then a
second contact:

.. code-block:: shell

   khard merge [-a source_abook] [-u uid|search terms [search terms ...]] [-A target_abook] [-U target_uid|-t target_search_terms]

You will be launched into your ``merge_editor`` (see |khard.conf|_) where you
can merge all changes from the first selected contact onto the second. Once you
are finished, the first contact is deleted and the second one updated.

Copy or move contact:

.. code-block:: shell

   khard copy [-a source_abook] [-u uid|search terms [search terms ...]] [-A target_abook]
   khard move [-a source_abook] [-u uid|search terms [search terms ...]] [-A target_abook]

Remove contact:

.. code-block:: shell

   khard remove [-a addr_name] [-u uid|search terms [search terms ...]]

.. |khard.conf| replace:: :manpage:`khard.conf`
.. _khard.conf: man/khard.conf.html
