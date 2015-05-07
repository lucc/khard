#!/usr/bin/python
# -*- coding: utf-8 -*-

import os

# twinkle config folder
twinkle_config = os.path.join(os.environ['HOME'], ".twinkle")

# khard executable
khard_exe = os.path.join(os.environ['HOME'], ".virtualenvs", "bin", "khard")

# user language
language = "de"

# stop mpd
stop_music = True
mpd_host = "192.168.2.100"
mpd_port = 6600

# log file for calls
call_log_file = os.path.join(twinkle_config, "calls.log")

# audio files
constant_ringtone_segment = os.path.join(twinkle_config, "sounds", "ringtone_segment.wav")
new_ringtone = os.path.join(twinkle_config, "sounds", "special_ringtone.wav")

# temp files
tmp_mono_file = "/tmp/caller_id.wav"
tmp_file_stereo = "/tmp/caller_id_stereo.wav"
mpd_lockfile = "/tmp/mpd_stopped"
caller_id_filename = "/tmp/current_caller_id"

