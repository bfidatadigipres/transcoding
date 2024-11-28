#!/bin/bash -x

# =========================================================
# Launcher script for H22 batch_transcode_h22_ffv1_v210.py
# =========================================================

date_FULL=$(date +'%Y-%m-%d - %T')

# Local variables from environmental vars
transcode_path1="${VID_IS}"
dump_to="$GIT_TRANSCODE"
log_path="${SCRIPT_LOG}batch_transcode_ofcom_ffv1_v210.log"
python_script="$SCRIPT_FFV1_V210_OFCOM"

function control {
    boole=$(cat "${CONTROL_JSON}" | grep "power_off_all" | awk -F': ' '{print $2}')
    if [ "$boole" = false, ] ; then
      echo "Control json requests script exit immediately" >> "${LOG}"
      echo 'Control json requests script exit immediately'
      exit 0
    fi
}

# Control check inserted into code
control

# replace list to ensure clean data
rm "${dump_to}batch_transcode_ofcom_ffv1_v210_dump_text.txt"
touch "${dump_to}batch_transcode_ofcom_ffv1_v210_dump_text.txt"

echo " ========================= SHELL SCRIPT LAUNCH ========================== $date_FULL" >> "${log_path}"
echo " == Start batch_transcode_h22_ffv1_v210 in $transcode_path1 and $transcode_path2 == " >> "${log_path}"
echo " == Shell script creating dump_text.txt output for parallel launch of Python scripts == " >> "${log_path}"

# Command to build MKV list from two v210 paths containing multiple archive folders
find "${transcode_path1}" -maxdepth 1 -mindepth 1 -name "*.mkv" -mmin +30 >> "${dump_to}batch_transcode_ofcom_ffv1_v210_dump_text.txt"

echo " == Launching GNU parallel to run muliple Python3 scripts for encoding == " >> "${log_path}"
grep '/mnt/' "${dump_to}batch_transcode_ofcom_ffv1_v210_dump_text.txt" | sort -u | parallel --jobs 3 "python3 $python_script {}"

echo " ========================= SHELL SCRIPT END ========================== $date_FULL" >> "${log_path}"
