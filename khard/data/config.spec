[general]
debug = boolean(default=False)
default_action = action(default=None)
editor = command(default=None)
merge_editor = command(default=None)

[contact table]
display = option('first_name', 'last_name', 'formatted_name', default='first_name')
group_by_addressbook = boolean(default=False)
localize_dates = boolean(default=True)
preferred_email_address_type = string_list(default=list('pref'))
preferred_phone_number_type = string_list(default=list('pref'))
reverse = boolean(default=False)
show_nicknames = boolean(default=False)
show_uids = boolean(default=True)
show_kinds = boolean(default=False)
sort = option('first_name', 'last_name', 'formatted_name', default='first_name')

[vcard]
preferred_version = option('3.0', '4.0', default='3.0')
private_objects = private_objects(default=list()))
search_in_source_files = boolean(default=False)
skip_unparsable = boolean(default=False)

[addressbooks]
  [[__many__]]
    path = string
