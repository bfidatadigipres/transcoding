#!/bin/bash

#-----------------------------------------------------------#
# This script is a lossless transcode worker which expects  #
# to be invoked by a `watchmedo` "created" event.           #
#                                                           #
# It compares aggregate checksums of ffmpeg's `-f framemd5` #
# outputs of both source and destination to ensure that     #
# the FFV1 Matroska transcode is lossless.                  #
#                                                           #
# Bad transcodes are deleted, and their sources moved.      #
#                                                           #
# Test usage:                                               #
# ./transcode.sh /path/to/file.mov created                  #
#                                                           #
# Watchdog:                                                 #
# See: https://github.com/gorakhargosh/watchdog             #
#-----------------------------------------------------------#

# Global variables
#OUTPUT="${QNAP_VID}/processing/source"
OUTPUT="${QNAP_01}/processing/source"
SUCCESS="${QNAP_08}/processing/transcode/original"
ERROR="${QNAP_08}/processing/transcode/error"
# Receive args at launch
INPUT="$1"
EVENT="$2"

# Log function
function log {
    timestamp=$(date "+%Y-%m-%d - %H.%M.%S")
    echo "$1"
    echo -e "$timestamp\t$INPUT\t$1" >> "${LOG_PATH}f47_transcode.log"
}

# Function to check for control json activity
function control {
    boole=$(cat "${LOG_PATH}downtime_control.json" | grep "ofcom_transcode" | awk -F': ' '{print $2}')
    if [ "$boole" = false, ] ; then
      log "Control json requests script exit immediately"
      exit 0
    fi
}

# Start script
if [ "$EVENT" = "created" ]; then
    log "Start"

    # Control check
    control

    # Only process audio-visual content, but allow application/octet-stream
    MIME=$(file --mime-type -b "$INPUT")
    TYPE="${MIME%%/*}"
    if [[ "$TYPE" != "video" && "$TYPE" != "audio" && "$TYPE" != "application" ]]; then
        # Move non-compliant media to error/
        #mv "$INPUT" "${ERROR}/"
        log "Invalid MIME type"
        exit 1
    fi

    # Only process ffprobe-able content
    if ffprobe "$INPUT" 2> /dev/null; then
        # OK
        :
    else
        # Do not process non-audio-visual file
        log "Unable to ffprobe"
        exit 1
    fi

    # Wrangle filename for output
    FRAMEMD5_PATH="${LOG_PATH}framemd5"
    BASE=$(basename "$INPUT" | cut -d. -f1)
    TMP="${OUTPUT}/partial.${BASE}.mkv"
    DST="${OUTPUT}/${BASE}.mkv"
    FRAMEMD5_MOV="${FRAMEMD5_PATH}/${BASE}.mov.framemd5"
    FRAMEMD5_MKV="${FRAMEMD5_PATH}/${BASE}.mkv.framemd5"

    # Check that temporary output does not already exist,
    # to permit other instances of this script to process
    # media from the same path simultaneously
    if [ -e "$TMP" ]; then
        log "Transcoding already in progress on this file"
        log "End"
        exit 0
    fi

    # Check that destination file does not already exist
    if [ -e "$DST" ]; then
        # A fixity-checked transcode already exists, quit
        log "Transcode already exists"
        log "End"
        exit 0
    fi

    # Create MD5 checksum of all FrameMD5s for source media
    # First check whether frameMD5 for MOV exists, delete it if it does
    if [ -e "$FRAMEMD5_MOV" ]; then
        # MOV frameMD5 already exists so deleting it
        log "MOV frameMD5 already exists, deleting it"
        rm "$FRAMEMD5_MOV"
        log "Generate source MOV framemd5"
        ffmpeg -nostdin -i "$INPUT" -f framemd5 "$FRAMEMD5_MOV"
        else
        # MOV frameMD5 does not exist, so create it
        log "Generate source mov framemd5"
        ffmpeg -nostdin -i "$INPUT" -f framemd5 "$FRAMEMD5_MOV"
    fi

    # Transcode source to FFV1 Matroska
    log "Begin transcode to MKV"

    # Test for PAL or NTSC source and modify ffmpeg colour metadata parameters based on result
    INPUT_STANDARD=$(mediainfo --Inform="Video;%Standard%" "$INPUT")
    HEIGHT=$(mediainfo --Inform='Video;%Height%' "$INPUT")
    if [ "$INPUT_STANDARD" = PAL ] ||  [ "$HEIGHT" = 608 ] ; then
    log "Add PAL colour metadata"
    ffmpeg -i "$INPUT" \
           -ignore_editlist 1 \
           -sn \
           -nostdin \
           -c:v ffv1 \
           -g 1 \
           -level 3 \
           -c:a copy \
           -map 0 \
           -dn \
           -slicecrc 1 \
           -slices 24 \
           -color_primaries bt470bg \
           -color_trc bt709 \
           -colorspace bt470bg \
           -color_range 1 \
           -n \
           "$TMP"

        else
            log "Add NTSC colour metadata"
            ffmpeg -i "$INPUT" \
                   -ignore_editlist 1 \
                   -sn \
                   -nostdin \
                   -c:v ffv1 \
                   -g 1 \
                   -level 3 \
                   -c:a copy \
                   -map 0 \
                   -dn \
                   -slicecrc 1 \
                   -slices 24 \
                   -color_primaries bt709 \
                   -color_trc bt709 \
                   -colorspace bt709 \
                   -color_range 1 \
                   -n \
                   "$TMP"
        fi

    log "Finish transcode to mkv"

    # Calculate filesize of MKV to ensure no zero byte MKVs persist
    OUTPUT_FILESIZE=$(stat --format=%s "$TMP")
    log "Output mkv filesize is ${OUTPUT_FILESIZE} bytes"

    # First check whether frameMD5 for MKV exists, delete it if it does
    if [ -e "$FRAMEMD5_MKV" ]; then
        # MKV frameMD5 already exists so deleting it
        log "MKV frameMD5 already exists, deleting it"
        rm "$FRAMEMD5_MKV"
        log "Generate source MKV framemd5"
        ffmpeg -nostdin -i "${TMP}" -f framemd5 "$FRAMEMD5_MKV"
        else
        # MKV frameMD5 does not exist, so create it
        log "Generate source mkv framemd5"
        ffmpeg -nostdin -i "${TMP}" -f framemd5 "$FRAMEMD5_MKV"
    fi

    if diff "$FRAMEMD5_MOV" "$FRAMEMD5_MKV" > /dev/null; then
        # MKV filesize > 0 and frameMD5s match
        STATUS="successful transcode"
        log "FrameMD5s match and MKV is not zero bytes (size = ${OUTPUT_FILESIZE})"
        log "Add to transcode_success list, to remove temporary partial. prefix from mkv filename at ${TMP}"
        echo "mv ${TMP} ${DST}" >> "${LOG_PATH}f47_transcode_success.txt"
        log "Move source mov to transcode/original folder"
        mv -vn "$INPUT" "${SUCCESS}/"
        log "Move mov and mkv frameMD5s to pass folder"
        mv -vn "$FRAMEMD5_MOV" "${FRAMEMD5_PATH}/pass/"
        mv -vn "$FRAMEMD5_MKV" "${FRAMEMD5_PATH}/pass/"

        else
        # FrameMD5s do not match
        STATUS="failure - frameMD5 mismatch"
        log "FrameMD5s do not match"
        log "Remove invalid mkv"
        rm -vf "$TMP"
        log "Move source mov to transcode/error folder"
        mv -vn "$INPUT" "${ERROR}/"
        log "Move both frameMD5s to fail folder"
        mv -vn "$FRAMEMD5_MKV" "${FRAMEMD5_PATH}/fail/"
        mv -vn "$FRAMEMD5_MOV" "${FRAMEMD5_PATH}/fail/"
    fi

    log "End of transcode process - status: ${STATUS}"
fi

# Use transcode_success list to rename the MKV files, removing the temporary partial. prefix from filename
parallel < "${LOG_PATH}f47_transcode_success.txt"
