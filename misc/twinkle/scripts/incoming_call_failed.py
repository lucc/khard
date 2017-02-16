#!/usr/bin/env python

import os, subprocess, time, datetime
import config

# current date and time
datetime = datetime.datetime.now()
current_date = "%.2d.%.2d.%.4d" % (datetime.day, datetime.month, datetime.year)
current_time = "%.2d:%.2d:%.2d" % (datetime.hour, datetime.minute, datetime.second)

# if music was stopped, resume again
if os.path.exists(config.mpd_lockfile) == True:
    os.remove(config.mpd_lockfile)
    subprocess.call(["mpc", "-h", config.mpd_host, "-p", str(config.mpd_port), "play"])

# try to get the caller name / id from the previously created temp file
try:
    with open(config.caller_id_filename, "r") as caller_id_file:
        caller_id = caller_id_file.read().strip()
except:
    caller_id = "anonymous"
if config.language == "de":
    message = "Anruf in Abwesenheit von %s am %s um %s\n" % (caller_id, current_date, current_time)
else:
    message = "Call in absence of %s in %s at %s\n" % (caller_id, current_date, current_time)
try:
    os.remove(config.caller_id_filename)
except:
    pass

# log into file
with open(config.call_log_file, "a") as log:
    log.write(message)
