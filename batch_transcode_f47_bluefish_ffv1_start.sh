#!/bin/bash -x

# =========================================================
# Launcher script for H22 batch_transcode_h22_ffv1_v210.py
# =========================================================

date_FULL=$(date +'%Y-%m-%d - %T')

# Local variables from environmental vars
transcode_path1="${BLUEFISH_MKV}"
dump_to="${GIT_TRANSCODE}"
log_path="${SCRIPT_LOG}QNAP_08_bluefish_ffv1_tbc_fix.log"
python_script="${GIT_TRANSCODE}f47_bluefish_ffv1_tbc_fix.py"

# replace list to ensure clean data
rm "${dump_to}batch_transcode_f47_bluefish_fix_dump_text.txt"
touch "${dump_to}batch_transcode_f47_bluefish_fix_dump_text.txt"

echo " ========================= SHELL SCRIPT LAUNCH ========================== $date_FULL" >> "${log_path}"
echo " == Start transcode of BlueFish MKV to MKV in $transcode_path1 == " >> "${log_path}"
echo " == Shell script creating dump_text.txt output for parallel launch of Python scripts == " >> "${log_path}"

# Command to build MKV list from two v210 paths containing multiple archive folders
find "${transcode_path1}" -maxdepth 1 -mindepth 1 -name "*.mkv" -mmin +30 >> "${dump_to}batch_transcode_f47_bluefish_fix_dump_text.txt"

echo " == Launching GNU parallel to run muliple Python3 scripts for encoding == " >> "${log_path}"
grep '/mnt/' "${dump_to}batch_transcode_f47_bluefish_fix_dump_text.txt" | sort -u | shuf | parallel --jobs 3 "${PY3_ENV} ${python_script} {}"

echo " ========================= SHELL SCRIPT END ========================== $(date +'%Y-%m-%d - %T')" >> "${log_path}"
