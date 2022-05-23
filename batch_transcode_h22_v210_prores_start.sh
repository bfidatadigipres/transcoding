#!/bin/bash -x

# ==========================================================
# Launcher script for H22 batch_transcode_h22_v210_ProRes.py
# ==========================================================

date_FULL=$(date +'%Y-%m-%d - %T')

# Local variables from environmental vars
transcode_path1="${QNAP04_H22}hdd/prores/SASE/success/"
transcode_path2="${QNAP04_H22}lto/prores/YFA/success/"
transcode_path3="${QNAP04_H22}lto/prores/NEFA/success/"
dump_to="$GIT_TRANSCODE"
log_path="$SCRIPT_LOG"
script_path="$SCRIPT_V210_PRORES"

# replace list to ensure clean data
rm "${dump_to}batch_transcode_h22_v210_prores_dump_text.txt"
touch "${dump_to}batch_transcode_h22_v210_prores_dump_text.txt"

echo " ========================= SHELL SCRIPT LAUNCH ========================== $date_FULL" >> "${log_path}batch_transcode_h22_v210_prores.log"
echo " == Start trancode: $transcode_path1, $transcode_path2 and $transcode_path3 == " >> "${log_path}batch_transcode_h22_v210_prores.log"
echo " == Shell script creating dump_text.txt output for parallel launch of Python scripts == " >> "${log_path}batch_transcode_h22_v210_prores.log"

# Command to build MKV list from two v210 paths containing multiple archive folders
find "${transcode_path1}" -maxdepth 1 -mindepth 1 -name "*.mov" -mmin +10 >> "${dump_to}batch_transcode_h22_v210_prores_dump_text.txt"
find "${transcode_path2}" -maxdepth 1 -mindepth 1 -name "*.mov" -mmin +10 >> "${dump_to}batch_transcode_h22_v210_prores_dump_text.txt"
find "${transcode_path3}" -maxdepth 1 -mindepth 1 -name "*.mov" -mmin +10 >> "${dump_to}batch_transcode_h22_v210_prores_dump_text.txt"

echo " == Launching GNU parallel to run multiple Python3 scripts for encoding == " >> "${log_path}batch_transcode_h22_v210_prores.log"
grep '/mnt/' "${dump_to}batch_transcode_h22_v210_prores_dump_text.txt" | sort -u | parallel --jobs 2 "python3 $script_path {}"

echo " ========================= SHELL SCRIPT END ========================== $date_FULL" >> "${log_path}batch_transcode_h22_v210_prores.log"
