#!/bin/bash -x

path_check1="$PATH_INN"
path_check2="$PATH_MX1"
path_check3="$PATH_DC1"
path_check4="$PATH_LMH"
path_check5="$PATH_VDM"
log_path="${SCRIPT_LOG}source_delay.log"

find "${path_check1}" "${path_check2}" "${path_check3}" "${path_check4}" "${path_check5}" -name "*.mov" | while IFS= read -r files; do

    source_delay=$(mediainfo -f "$files" | grep 'Source_Delay ')
    video_delay=$(echo $source_delay | awk '{ print $3 }')
    audio_delay=$(echo $source_delay | awk '{ print $6 }')

    if [ -z $audio_delay ];
      then
        echo "${files} does not have any audio delay output - okay to process"  >> "$log_path"
        # Move to transcode path
      else
        echo "$files has audio delay $audio_delay"  >> "$log_path"
    fi

    if [ -z $video_delay ];
      then
        echo "${files} does not have any video delay output ${audio_delay} - okay to process"  >> "$log_path"
        # Move to transcode path
      else
        echo "$files has video delay: $video_delay"  >> "$log_path"
    fi
    if [[ $video_delay == $audio_delay ]];
      then
        echo "${files}: Audio delay ${audio_delay} and video delay ${video_duration} match - okay to process" >> "$log_path"
        # Move to transcode path
      else
        echo "WARNING: ${files}  Audio delay and video delay did not match. Moving to Errors folder." >> "$log_path"
        # Move to error path, as delays don't match which will cause transcode failure
    fi
done
