#!/bin/sh

# khard requires the second file in the diff-operation to be modified in order
# to recognize a successful merge. However the file provided to sdiff's "-o"
# switch cannot be any of the source files.
#
# If you want to use sdiff to merge contacts you must set this wrapper script
# as your merge editor in khard's config file
#
# merge_editor = /path/to/sdiff_khard_wrapper.sh

set -e

# First and second argument to sdiff.
FIRST=$1
SECOND=$(mktemp)

# Cleanup for signals and normal exit.
trap 'trap "" EXIT; rm -f "$SECOND"; exit' INT HUP TERM
trap 'rm -f "$SECOND"' EXIT

# Free the filename that khard expects to change.
mv -f "$2" "$SECOND"
sdiff "$FIRST" "$SECOND" -o "$2"
