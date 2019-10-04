[general]
debug = boolean(default=False)
editor = string
merge_editor = string
default_action = string(default='list')

[contact table]
reverse = boolean(default=False)
group_by_addressbook = boolean(default=False)
show_nicknames = boolean(default=False)
show_uids = boolean(default=True)
sort = option('first_name', 'last_name', default='first_name')
display = option('first_name', 'last_name', default='first_name')
localize_dates = boolean
preferred_phone_number_type = string_list
preferred_email_address_type = string_list

[vcard]
private_objects = string_list(default=list()))
search_in_source_files = boolean(default=False)
skip_unparsable = boolean(default=False)
preferred_version = option('3.0', '4.0', default='3.0')

[addressbooks]
  [[__many__]]
    path = string
