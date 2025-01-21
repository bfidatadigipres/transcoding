#!/usr/bin/env LANG=en_UK.UTF-8 /usr/local/bin/python3

'''
*** THIS SCRIPT MUST RUN WITH SHELL SCRIPT LAUNCH TO PASS FILES TO SYS.ARGV[1] AND DRIVE PARALLEL ***
Script that takes V210 Matroska files and encodes to ProRes mov:

1. Shell script searches in paths for files that end in '.mov' not modified in the last ten minutes and at a depth of 1 folder,
   then passes any found one at a time to batch_transcode_h22_v210_prores.py
2. Python script receives single path as sys.argv[1] and populates fullpath variable
3. Populates FFmpeg subprocess command based on supplied fullpath, new generated output_fullpath and fixed FFmpeg command.*
4. Transcodes new file into 'prores_transcode/' folder named as {filename}.mov
5. Runs mediaconch checks against the ProRes file
   - If pass:
      i. Moves ProRes to finished_prores/ folder
      ii. Deletes original V210 mov file (currently offline)
   - If fails:
      i. Moves ProRes mov to failures/ folder and appends failures log
      ii. Deletes ProRes from failures folder (currently offline)
     iii. Leaves original V210 mov for repeated encoding attempt

*Note:  There may need to be adjustments to the fixed command in time if this ‘one command fits all’ approach
is found to be lacking. For example -flags +ildct may not be the best option for all interlacing/progressive
files where found. If this is the case then additional mediainfo metadata enquiries will be added to ensure
a customised command is provided.

Python 3.7+
2021
'''

import os
import sys
import time
import json
import shutil
import logging
import subprocess

# Global paths from server environmental variables
PATH_POLICY = os.environ['H22_POLICIES']
PRORES_POLICY = os.path.join(PATH_POLICY, 'h22_video_transcode_policy_ProRes.xml')
LOG = os.environ['SCRIPT_LOG']
CONTROL_JSON = os.path.join(LOG, 'downtime_control.json')

# Setup logging
logger = logging.getLogger('batch_transcode_h22_v210_prores.log')
hdlr = logging.FileHandler(os.path.join(LOG, 'batch_transcode_h22_v210_prores.log'))
formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

logger.info("================== START Python3 v210 to ProRes transcode START ==================")


def check_control():
    '''
    Check control json for downtime requests
    '''
    with open(CONTROL_JSON) as control:
        j = json.load(control)
        if not j['rna_transcode']:
            logger.info('Script run prevented by downtime_control.json. Script exiting.')
            sys.exit('Script run prevented by downtime_control.json. Script exiting.')


def change_path(fullpath, use):
    '''
    Takes fullpath and use argument and returns formatted path
    '''
    path_split = os.path.split(fullpath)
    path_split2 = os.path.split(path_split[0])

    if 'transcode' in use:
        return os.path.join(path_split2[0], f'prores_transcode/{path_split[1]}')
    elif 'pass' in use:
        return os.path.join(path_split2[0], f'finished_prores/{path_split[1]}')
    elif 'fail' in use:
        return os.path.join(path_split2[0], f'failures/{path_split[1]}')
    elif 'fail_log' in use:
        return os.path.join(path_split2[0], "failures/h22_mov_failure.log")


def create_ffmpeg_command(fullpath):
    '''
    Subprocess command build, with variations
    added based on metadata extraction
    '''
    output_fullpath = change_path(fullpath, 'transcode')

    # Build subprocess call from data list
    ffmpeg_program_call = [
        "ffmpeg"
    ]

    input_video_file = [
        "-i", fullpath,
        "-nostdin"
    ]

    map_command = [
        "-map", "0"
    ]

    video_settings = [
        "-c:v", "prores_ks",
        "-profile:v", "3"
    ]

    colour_build = [
        "-pix_fmt", "yuv422p10le",
        "-vendor", "ap10"
    ]

    interlace = [
        "-flags", "+ildct",
        "-movflags", "faststart"
    ]
    # "copy" temp replaced with "pcm_s16le"
    audio_settings = [
        "-c:a", "pcm_s24le"
    ]

    mov_settings = [
        "-n", output_fullpath
    ]

    return ffmpeg_program_call + input_video_file + map_command + video_settings + colour_build + \
           interlace + audio_settings + mov_settings


def conformance_check(filepath):
    '''
    Checks mediaconch policy against new V210 mov
    '''

    mediaconch_cmd = [
        'mediaconch', '--force',
        '-p', PRORES_POLICY,
        filepath
    ]

    try:
        success = subprocess.check_output(mediaconch_cmd)
        success = str(success)
    except Exception:
        success = ""
        logger.exception("Mediaconch policy retrieval failure for %s", filepath)

    if 'N/A!' in success:
        logger.info("***** FAIL! Problem with the MediaConch policy suspected. Check <%s> manually *****\n%s", filepath, success)
        return "FAIL!"
    elif 'pass!' in success:
        logger.info("PASS: %s has passed the mediaconch policy", filepath)
        return "PASS!"
    elif 'fail!' in success:
        logger.warning("FAIL! The policy has failed for %s:\n %s", filepath, success)
        return "FAIL!"
    else:
        logger.warning("FAIL! The policy has failed for %s", filepath)
        return "FAIL!"


def fail_log(fullpath, message):
    '''
    Appends failure message if log present, otherwise creates fail log
    and appends new message to it
    '''
    fail_log_path = change_path(fullpath, 'log')
    message = str(message)
    if os.path.isfile(fail_log_path):
        with open(fail_log_path, 'a') as log_data:
            log_data.write("================= {} PRORES ================\n".format(fullpath))
            log_data.write(message)
            log_data.write("\n")
            log_data.close()
    else:
        with open(fail_log_path, 'x') as log_data:
            log_data.close()
        with open(fail_log_path, 'a') as log_data:
            log_data.write("================= {} PRORES ================\n".format(fullpath))
            log_data.write(message)
            log_data.write("\n")
            log_data.close()


def main():
    '''
    Receives sys.argv[1] path to MOV from shell start script via GNU parallel
    Passes to FFmpeg subprocess command, transcodes ProRes mov then checks
    finished encoding against custom prores mediaconch policy
    If pass, cleans up files moving to finished_prores/ folder and deletes V210 mov (temp offline).
    '''
    if len(sys.argv) < 2:
        logger.warning("SCRIPT EXITING: Error with shell script input:\n %s", sys.argv)
        sys.exit()

    check_control()
    fullpath = sys.argv[1]
    path_split = os.path.split(fullpath)
    file = path_split[1]
    output_fullpath = change_path(fullpath, 'transcode')
    if file.startswith("N_") and '/prores/' in fullpath:
        logger_data = []

        # Execute FFmpeg subprocess call
        logger_data.append(f"******** {fullpath} being processed ********")
        ffmpeg_call = create_ffmpeg_command(fullpath)
        ffmpeg_call_neat = (" ".join(ffmpeg_call), "\n")
        logger_data.append(f"FFmpeg call: {ffmpeg_call_neat}")

        # tic/toc record encoding time
        tic = time.perf_counter()
        try:
            subprocess.call(ffmpeg_call)
            logger_data.append("Subprocess call for FFmpeg command successful")
        except Exception as err:
            logger_data.append(f"WARNING: FFmpeg command failed: {ffmpeg_call_neat}\n{err}")
        toc = time.perf_counter()
        encoding_time = (toc - tic) // 60
        seconds_time = (toc - tic)
        logger_data.append(f"*** Encoding time for {file}: {encoding_time} minutes or as seconds: {seconds_time}")
        logger_data.append("Checking if new Prores file passes Mediaconch policy")

        for line in logger_data:
            if 'WARNING' in str(line):
                logger.warning("%s", line)
            else:
                logger.info("%s", line)
        clean_up(fullpath, output_fullpath)

    else:
        logger.info("SKIPPING: %s is not a '/prores/' path ** NOT FOR TRANSCODING **", fullpath)

    logger.info("================== END v210 to ProRes transcode END ==================")


def clean_up(fullpath, new_fullpath):
    '''
    Run mediaconch check against new prores
    Clean up V210 MOV or ProRes file depending on pass/fail
    '''
    new_file = os.path.split(new_fullpath)
    logger.info("Clean up begins for %s", new_fullpath)
    if os.path.isfile(new_fullpath):
        if new_fullpath.endswith(".mov"):
            logger.info("Conformance check: comparing %s with policy", new_file[1])
            result = conformance_check(new_fullpath)
            if "PASS!" in result:
                logger.info("%s passed the policy checker and it's V210 can be deleted", new_file[1])
                try:
                    new_file_path = change_path(fullpath, 'pass')
                    shutil.move(new_fullpath, new_file_path)
                    logger.info("Moving passed prores %s to completed folder: %s", new_file[1], new_file_path)
                except Exception:
                    logger.exception("Unable to move %s to success folder: %s", new_file[1], new_file_path)
                try:
                    # Delete V210 MOV after successful encode to ProRes mov
                    logger.info("*** Deletion of V210 following successful transcode: %s", fullpath)
                    os.remove(fullpath)
                except Exception:
                    logger.exception("Deletion failure: %s", fullpath)
            else:
                logger.warning("FAIL: %s failed the policy checker. Leaving V210 mov for second encoding attempt", new_file[1])
                fail_log(new_fullpath, result)
                fail_path = change_path(fullpath, 'fail')
                try:
                    # Delete MOV from failures/ path
                    logger.info("Moving %s to failures/ folder: %s", new_file[1], fail_path)
                    shutil.move(new_fullpath, fail_path)
                except Exception:
                    logger.exception("Unable to move %s to failures/ folder: %s", new_file[1], fail_path)
                try:
                    logger.info("Deleting %s file as failed mediaconch policy")
                    os.remove(fail_path)
                except Exception:
                    logger.exception("Unable to delete %s", fail_path)
        else:
            logger.info("Skipping %s, as this file is not ended .mov", new_file[1])
    else:
        logger.warning("NOT A FILE: %s what is this?", new_file[1])


if __name__ == "__main__":
    main()
