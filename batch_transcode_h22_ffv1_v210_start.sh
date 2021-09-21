#!/bin/bash -x

# =========================================================
# Launcher script for H22 batch_transcode_h22_ffv1_v210.py
# =========================================================

date_FULL=$(date +'%Y-%m-%d - %T')

# Local variables from environmental vars
transcode_path1="$H22_PATH1"
transcode_path2="$H22_PATH2"
dump_to="$TRANSCODE"
log_path="$SCRIPT_LOG"
python_script="$SCRIPT_FFV1_V210"

# replace list to ensure clean data
rm "${dump_to}batch_transcode_h22_ffv1_v210_dump_text.txt"
touch "${dump_to}batch_transcode_h22_ffv1_v210_dump_text.txt"

echo " ========================= SHELL SCRIPT LAUNCH ========================== $date_FULL" >> "${log_path}batch_transcode_h22_ffv1_v210.log"
echo " == Start batch_transcode_h22_ffv1_v210 in $transcode_path1 and $transcode_path2 == " >> "${log_path}batch_transcode_h22_ffv1_v210.log"
echo " == Shell script creating dump_text.txt output for parallel launch of Python scripts == " >> "${log_path}batch_transcode_h22_ffv1_v210.log"

# Command to build MKV list from two v210 paths containing multiple archive folders
find "${transcode_path1}" -maxdepth 3 -mindepth 3 -name "*.mkv" -mmin +10 >> "${dump_to}batch_transcode_h22_ffv1_v210_dump_text.txt"
find "${transcode_path2}" -maxdepth 3 -mindepth 3 -name "*.mkv" -mmin +10 >> "${dump_to}batch_transcode_h22_ffv1_v210_dump_text.txt"

echo " == Launching GNU parallel to run muliple Python3 scripts for encoding == " >> "${log_path}batch_transcode_h22_ffv1_v210.log"
grep '/mnt/' "${dump_to}batch_transcode_h22_ffv1_v210_dump_text.txt" | parallel --jobs 3 "python3 $python_script {}"

echo " ========================= SHELL SCRIPT END ========================== $date_FULL" >> "${log_path}batch_transcode_h22_ffv1_v210.log"
