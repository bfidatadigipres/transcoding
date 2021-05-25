#!/bin/bash -x

# =============================================================
# Launcher script for H22 Film batch_transcode_proresHD_mp4.py
# =============================================================
date_FULL=$(date +'%Y-%m-%d - %T')

log="$SCRIPT_LOG"
transcode_path1="$H22_FILM_PATH1"
transcode_path2="$H22_FILM_PATH2"
transcode_path3="$H22_FILM_PATH3"
dump_to="$TRANSCODE"

rm "${dump_to}proresHD_dump_text.txt"
touch "${dump_to}proresHD_dump_text.txt"

# Directory path to run shell script temporarily
cd "${dump_to}"

echo " ======================== SHELL SCRIPT START =========================== " >> "${log}batch_transcode_proresHD_mp4.log"
echo " == Start batch_transcode_proresHD_mp4 in folder path - $date_FULL == " >> "${log}batch_transcode_proresHD_mp4.log"
echo " == Shell script creating proresHD_dump_text.txt for folder path - $date_FULL == " >> "${log}batch_transcode_proresHD_mp4.log"

find "${transcode_path1}" -name "*.mov" -mmin +10 >> "${dump_to}proresHD_dump_text.txt"
find "${transcode_path2}" -name "*.mov" -mmin +10 >> "${dump_to}proresHD_dump_text.txt"
find "${transcode_path3}" -name "*.mov" -mmin +10 >> "${dump_to}proresHD_dump_text.txt"

grep '/mnt/' "${dump_to}proresHD_dump_text.txt" | parallel --jobs 3 "python3 batch_transcode_proresHD_mp4.py {}"

echo " ===================== SHELL SCRIPT END ======================== " >> "${log}batch_transcode_proresHD_mp4.log"
