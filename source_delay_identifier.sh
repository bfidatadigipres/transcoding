#!/bin/bash

PATH1="$PATH_INN"
LOG="${SCRIPT_LOG}source_delay_locator1.log"

find "${PATH1}/validate/" -name "*.mov" | while IFS= read -r files; do
    echo "$files"
    source_delay=$(mediainfo -f "$files" | grep 'Source_Delay ')
    video_delay=$(echo $source_delay | awk '{ print $3 }')
    audio_delay=$(echo $source_delay | awk '{ print $6 }')
    echo " " >> "$LOG"
    echo "------------------------ $files ------------------------" >> "$LOG"
    if [[ $video_delay == $audio_delay ]];
      then
        echo "$files: Delay [0] $audio_delay and delay [1] $video_duration match - okay to process" >> "$LOG"
      else
        echo "WARNING: Delay [0] and delay [1] did not match. Checking if both values are populated" >> "$LOG"
        if [ -z $video_delay ];
          then
            echo "$files does not have any video delay output - okay to process"  >> "$LOG"
          else
            echo "$files has delay in mediainfo data [0] assumed to be video: $video_delay"  >> "$LOG"
            if [ -z $audio_delay ];
              then
                echo "$files does not have any audio delay output - okay to process"  >> "$LOG"
              else
                echo "$files has delay in mediainfo data [1] assumed to be audio: $audio_delay."  >> "$LOG"
                echo "WARNING: video/audio delay are populated and do not match. Moving to failures folder: ${PATH1}/failures/source_delay/" >> "$LOG"
                mv "$files" "${PATH1}/failures/source_delay/"
            fi
        fi
    fi
done
