#!/bin/bash -x

# =============================================================
# Launcher script for H22 Film batch_transcode_proresHD_mp4.py
# =============================================================
date_FULL=$(date +'%Y-%m-%d - %T')

log="$SCRIPT_LOG"
transcode_path1="$H22_FILM_PATH1"
transcode_path2="$H22_FILM_PATH2"
transcode_path3="$H22_FILM_PATH3"
dump_to="$GIT_TRANSCODE"
python="$GIT_TRANSCODE"

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

grep '/mnt/' "${dump_to}proresHD_dump_text.txt" | parallel --jobs 2 "python3 ${python}batch_transcode_proresHD_mp4.py {}"

echo " ===================== SHELL SCRIPT END ======================== " >> "${log}batch_transcode_proresHD_mp4.log"
