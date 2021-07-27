#!/bin/bash -x

# ==========================================================
# Launcher script for H22 batch_transcode_h22_v210_ProRes.py
# ==========================================================

date_FULL=$(date +'%Y-%m-%d - %T')

# Local variables from environmental vars
transcode_path1="${H22_PATH1}prores/SASE/success/"
transcode_path2="${H22_PATH2}prores/YFA/success/"
transcode_path3="${H22_PATH2}prores/NEFA/success/"
dump_to="$TRANSCODE"
log_path="$SCRIPT_LOG"

# Directory path change just to run shell find commands
cd "${dump_to}"

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
grep '/mnt/' "${dump_to}batch_transcode_h22_v210_prores_dump_text.txt" | parallel --jobs 4 "python3 batch_transcode_h22_v210_prores.py {}"

echo " ========================= SHELL SCRIPT END ========================== $date_FULL" >> "${log_path}batch_transcode_h22_v210_prores.log"
