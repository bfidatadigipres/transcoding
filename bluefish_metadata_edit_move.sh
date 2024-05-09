#!/bin/bash

# ==========================
# Bluefish metadata update =
# ==========================

# Log variable / function
function log {
    timestamp=$(date "+%Y-%m-%d - %H.%M.%S")
    echo "$1 - $timestamp"
} >> "${MKV_PROCESSING}mkv_movements.log"

# Check for list of files in MKV_Ready_for_Processing/ folder
if [ -z "$(ls -A ${MKV_PROCESSING} | grep '.mkv')" ]
  then
    echo "No files available for metadata change and movement"
    exit 1
  else
    log "==== Bluefish metadata edit / move START ===="
fi

# Find all MKV files, check metadata then update mkvtoolnix
find "$MKV_PROCESSING" -maxdepth 1 -name '*.mkv' | while IFS= read -r files; do
    filename=$(basename "$files")
    log "File found to process: ${filename}"
    library=$(mediainfo --Language=raw --Output="General;%Encoded_Library%" "$files")
    log "  Library information found: $library"
    grep_lib=$(mediainfo --Language=raw --Output="General;%Encoded_Library%" "$files" | grep 'Lavf57.71.100')
    if [ -z "$grep_lib" ]
      then
        log "  Moving Matroska straight to QNAP-08 processing source"
        mv "$files" "$QNAP08_SOURCE"
      else
        mkvpropedit "$files" --edit info --set "muxing-application=BlueFish"
        lib_update=$(mediainfo --Language=raw --Output="General;%Encoded_Library%" "$files" | grep 'BlueFish')
        if [ -z "$lib_update" ]
          then
            log "  * Metadata write failed. Leaving file for another update attempt"
          else
            log "  Metadata updated: $lib_update moving file to $QNAP08_SOURCE"
            mv "$files" "$QNAP08_SOURCE"
        fi
    fi
done

log "==== Bluefish metadata edit / move END ======"


