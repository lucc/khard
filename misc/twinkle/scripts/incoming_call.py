#!/usr/bin/env python

# This script speaks the incoming caller ID for the SIP client Twinkle
# The following programs are needed: espeak, ffmpeg and sox, mpc is optional
# aptitude install ffmpeg espeak sox mpc
# Further information about Twinkle scripts can be found at
# http://mfnboer.home.xs4all.nl/twinkle/manual.html#profile_scripts

import os, subprocess, sys, re
import config

def get_caller_id(from_hdr):
    caller_id = from_hdr[from_hdr.find(":")+1:from_hdr.find("@")]
    # remove all non digits from caller id
    caller_id = re.sub("\D", "", caller_id)
    # remove two digit country identification if present
    if not caller_id.startswith("0"):
        return caller_id[2:]
    return caller_id

def caller_from_addressbook(caller_id):
    try:
        callers = subprocess.check_output([config.khard_exe, "phone", "--parsable", caller_id]).strip()
    except subprocess.CalledProcessError:
        return caller_id
    if len(callers.split("\n")) == 1:
        return callers.split("\t")[1]
    else:
        # the contact contains multiple phone numbers and we have to obtain the right phone label
        regexp = re.compile(caller_id, re.IGNORECASE)
        for entry in callers.split("\n"):
            if regexp.search(re.sub("\D", "", entry.split("\t")[0])) != None:
                return "%s (%s)" % (entry.split("\t")[1], entry.split("\t")[2])
        return callers.split("\n")[0].split("\t")[1]

def create_ringtone(caller_id):
    if os.path.exists(config.new_ringtone) == True:
        os.remove(config.new_ringtone)
    if config.language == "de":
        subprocess.call(["espeak", "-v", "de", "-s", "300", "-w", config.tmp_mono_file, caller_id])
    else:
        subprocess.call(["espeak", "-v", "en-us", "-s", "300", "-w", config.tmp_mono_file, caller_id])
    subprocess.call(["ffmpeg", "-i", config.tmp_mono_file, "-ar", "48000", "-ac", "2", "-y", config.tmp_file_stereo],
            stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))
    subprocess.call(["sox", config.constant_ringtone_segment, config.tmp_file_stereo, config.new_ringtone])


# main part of the script
if os.path.exists(config.constant_ringtone_segment) == False:
    print "The constant part of the ringtone file is missing. Create the sounds folder in your twinkle config and put a wav file in it"
    sys.exit(1)

# pause the music playback
# I use a MPD server for playing music so I pause it with the client MPC
# You can disable that in the config.py file
if config.stop_music:
    mpc_output = subprocess.check_output(["mpc", "-h", config.mpd_host, "-p", str(config.mpd_port), "status"])
    if "playing" in mpc_output:
        subprocess.call(["mpc", "-h", config.mpd_host, "-p", str(config.mpd_port), "pause"])
        music_tmp_file = open(config.mpd_lockfile, "w")
        music_tmp_file.close()

if "SIP_FROM" in os.environ:
    from_hdr = os.environ["SIP_FROM"]
    # parse the caller ID of the string
    caller_id = get_caller_id(from_hdr)
    # look into the addressbook
    if caller_id != "":
        caller_id = caller_from_addressbook(caller_id)
    else:
        caller_id = "anonymous"
    # create the ringtone
    if config.language == "de":
        create_ringtone("Anruf von " + caller_id)
    else:
        create_ringtone("Call from " + caller_id)
    # save the caller id for later use
    caller_id_file = open(config.caller_id_filename, "w")
    caller_id_file.write(caller_id)
    caller_id_file.close()
    # if the file creation was successful and the file exists, tell twinkle to use it as the ringtone
    # else do nothing and play the standard ringtone
    if os.path.exists(config.new_ringtone) == True:
        print "ringtone=" + config.new_ringtone
sys.exit()
