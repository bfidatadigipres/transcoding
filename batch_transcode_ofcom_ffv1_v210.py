#!/usr/bin/env python3

'''
*** THIS SCRIPT MUST RUN WITH SHELL SCRIPT LAUNCH TO PASS FILES TO SYS.ARGV[1] AND DRIVE PARALLEL ***

Script that takes FFv1 Matroska files and encodes to v210 mov:
1. Shell script searches in paths for files that end in '.mkv' and passes on one at a time to Python
2. Receives single path as sys.argv[1], checks metadata of file acquiring field order, colour data etc
3. Populates FFmpeg subprocess command based on format decisiong from retrieved data
4. Transcodes new file into transcode/ path named as {filename}.mov
5. Runs framemd5 checks against the FFV1 matroska and V210 mov file, checks if they're identical
   If identical:
     i. verifies V210 mov passes mediaconch policy
     ii. If yes, moves identical V210 mov to success/ folder
         If no, moves V210 mov to failures/ folder and appends failures log. Deletes V210 mov
     iii. If mediaconch passed FFV1 matroska is deleted
   If not identical:
     i. File is not mediaconch checked but moved to failures/ and failure log updated
     ii. V210 mov is deleted and FFV1 matroska is left in place for another transcoding attempt
     iii. MKV is moved to framemd5_fail folder

Python 3.7+
2021
'''

import os
import sys
import json
import time
import shutil
import logging
import subprocess

# Global paths from server environmental variables
MOV_POLICY_PAL = os.environ.get('MOV_POLICY_H22')
MOV_POLICY_NTSC = os.environ.get('MOV_NTSC_GEN')
STORAGE = os.environ.get('QNAP08_AUTOMATION')
LOG = os.environ.get('SCRIPT_LOG')
CONTROL_JSON = os.path.join(LOG, 'downtime_control.json')

# Setup logging
logger = logging.getLogger('batch_transcode_ofcom_ffv1_v210')
hdlr = logging.FileHandler(os.path.join(LOG, 'batch_transcode_ofcom_ffv1_v210.log'))
formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)


def check_control():
    '''
    Check control json for downtime requests
    '''
    with open(CONTROL_JSON) as control:
        j = json.load(control)
        if not j['ofcom_transcode']:
            logger.info('Script run prevented by downtime_control.json. Script exiting.')
            sys.exit('Script run prevented by downtime_control.json. Script exiting.')


def get_colour(fullpath):
    '''
    Retrieves colour information via mediainfo and returns in correct FFmpeg format
    '''
    mediainfo_cmd1 = [
        'mediainfo',
        '--Language=raw',
        '--Output=Video;%colour_primaries%',
        fullpath
    ]

    colour_prim = subprocess.check_output(mediainfo_cmd1)
    colour_prim = str(colour_prim)

    mediainfo_cmd3 = [
        'mediainfo',
        '--Language=raw',
        '--Output=Video;%matrix_coefficients%',
        fullpath
    ]

    col_matrix = subprocess.check_output(mediainfo_cmd3)
    col_matrix = str(col_matrix)

    if 'BT.709' in colour_prim:
        color_primaries = 'bt709'
    elif 'BT.601' in colour_prim and 'NTSC' in colour_prim:
        color_primaries = 'smpte170m'
    elif 'BT.601' in colour_prim and 'PAL' in colour_prim:
        color_primaries = 'bt470bg'
    else:
        color_primaries = ''

    if 'BT.709' in col_matrix:
        colormatrix = 'bt709'
    elif 'BT.601' in col_matrix:
        colormatrix = 'smpte170m'
    elif 'BT.470' in col_matrix:
        colormatrix = 'bt470bg'
    else:
        colormatrix = ''

    return (color_primaries, colormatrix)


def get_interl(fullpath):
    '''
    Retrieves interlacing data and returns in correct FFmpeg format
    '''
    mediainfo_cmd = [
        'mediainfo',
        '--Language=raw',
        '--Output=Video;%ScanOrder%',
        fullpath
    ]

    interl_setting = subprocess.check_output(mediainfo_cmd)
    interl_setting = str(interl_setting)

    if 'TFF' in interl_setting:
        setfield = 'tff'
    elif 'BFF' in interl_setting:
        setfield = 'bff'
    elif 'PROG' in interl_setting:
        setfield = 'prog'
    else:
        setfield = ''

    return setfield


def change_path(fullpath, use):
    '''
    Takes fullpath and use argument and returns formatted path
    for one of four RNA paths
    '''
    path_split = os.path.split(fullpath)
    filename, extension = os.path.splitext(path_split[1])
    fail_log = "ofcom_transcode_failures.log"

    if 'transcode' in use:
        return os.path.join(STORAGE, 'transcode/', f'{filename}.mov')
    elif 'move' in use:
        return os.path.join(STORAGE, 'success/', f'{filename}_v210.mov')
    elif 'failed' in use:
        return os.path.join(STORAGE, 'failures/', f'{filename}.mov')
    elif 'mkv_fail' in use:
        return os.path.join(STORAGE, 'framemd5_fail/', path_split[1])
    elif 'log' in use:
        return os.path.join(STORAGE, 'failures/', fail_log)


def create_ffmpeg_command(fullpath, data=None):
    '''
    Subprocess command build, with variations
    added based on metadata extraction
    '''

    output_fullpath = change_path(fullpath, 'transcode')

    if data is None:
        data = []

    # Build subprocess call from data list
    ffmpeg_program_call = [
        "ffmpeg"
    ]

    input_video_file = [
        "-i", fullpath,
        "-nostdin"
    ]

    map_command = [
        "-map", "0",
        "-dn",
        "-movflags", "write_colr"
    ]

    video_settings = [
        "-c:v", f"{data[0]}"
    ]

    colour_build = [
        "-color_primaries", f"{data[4]}",
        "-color_trc", f"{data[3]}",
        "-colorspace", f"{data[2]}",
        "-color_range", "1",
        "-metadata:s:v:0", f"'encoder={data[1]}'"
    ]

    interlace = [
        "-vf", f"setfield={data[5]},fps=fps={data[6]}"
    ]

    audio_settings = [
        "-c:a", "copy"
    ]

    mov_settings = [
        "-f", "mov",
        "-n", output_fullpath
    ]

    return ffmpeg_program_call + input_video_file + map_command + video_settings + colour_build + \
           interlace + audio_settings + mov_settings


def conformance_check(filepath, mov_policy):
    '''
    Checks mediaconch policy against new V210 mov
    '''

    mediaconch_cmd = [
        'mediaconch', '--force',
        '-p', mov_policy,
        filepath
    ]

    try:
        success = subprocess.check_output(mediaconch_cmd)
        success = str(success)
    except Exception:
        success = ""
        logger.warning("Mediaconch policy retrieval failure for %s", filepath)

    if 'N/A!' in success:
        logger.info("***** FAIL! Problem with the MediaConch policy suspected. Check <%s> manually *****\n%s", filepath, success)
        return f"FAIL! {success}"
    elif 'pass!' in success:
        logger.info("PASS: %s has passed the mediaconch policy", filepath)
        return "PASS!"
    elif 'fail!' in success:
        logger.warning("FAIL! The policy has failed for %s:\n %s", filepath, success)
        return f"FAIL! {success}"
    else:
        return f"FAIL! {success}"
        logger.warning("FAIL! The policy has failed for %s:\n%s", filepath, success)


def make_framemd5(fullpath):
    '''
    Creates MKV and MOV framemd5 and returns results in variables
    Uses lutyuv trim due to non-compliant yuv data capture at source (fault of capture cards)
    This losslessly passed to matroska, but in transcoding back to V210 mov yuv regions
    0-4 and 1019-1023 become lossy failing framemd5 comparison. lutyuv command courtesy Dave Rice.
    '''
    new_filepath = change_path(fullpath, 'transcode')

    framemd5_mkv = [
        "ffmpeg", "-nostdin", "-y",
        "-i", fullpath, "-an",
        "-vf", "lutyuv=y=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):u=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):v=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val))",
        "-f", "framemd5",
        "-"
    ]

    try:
        md5_mkv = subprocess.check_output(framemd5_mkv)
    except Exception:
        logger.exception("Framemd5 command failure: %s", fullpath)
        md5_mkv = None

    framemd5_mov = [
        "ffmpeg", "-nostdin", "-y",
        "-i", new_filepath, "-an",
        "-vf", "lutyuv=y=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):u=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):v=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val))",
        "-f", "framemd5",
        "-"
    ]

    try:
        md5_mov = subprocess.check_output(framemd5_mov)
    except Exception:
        logger.exception("Framemd5 command failure: %s", new_filepath)
        md5_mov = None

    return md5_mkv, md5_mov


def framemd5_cut(framemd5):
    '''
    This function to chop up framemd5 so only checksum remain for comparison
    avoiding errors with non-matching duration columns, split on comma
    JMW new function 08/09/2022
    '''

    new_manifest = []
    lines =  framemd5.decode('utf-8').split('\n')
#    framemd5_decode = framemd5.decode('utf-8')
#    lines = framemd5_decode.split('\n')

    for line in lines:
        if line.startswith('#'):
            continue
        new_manifest.append(line.split(',')[-1])

    print(''.join(new_manifest))
    return ''.join(new_manifest)


def diff_check(md5_mkv, md5_mov):
    '''
    Compare two framemd5s for exact match
    '''

    logger.info("Diff command received: %s and %s paths", md5_mkv, md5_mov)

    diff_cmd = [
        'diff', '-s',
        md5_mkv, md5_mov
    ]

    try:
        success = subprocess.check_output(diff_cmd)
    except Exception as e:
        success = ""
        logger.warning("Diff check failed for %s and %s\n%s", md5_mkv, md5_mov, e)

    if 'are identical' in str(success):
        return 'MATCH'
    else:
        return 'FAIL'


def get_framerate(fullpath):
    '''
    Retrieve framerate metadata
    '''
    mediainfo_cmd = [
        'mediainfo',
        '-f',
        '--Language=raw',
        '--Output=General;%FrameRate/String%',
        fullpath
    ]

    framerate = subprocess.check_output(mediainfo_cmd)
    framerate = framerate.decode('utf-8')
    if '.' in framerate:
        return framerate.split('.')[0]
    return framerate


def fail_log(fullpath, message):
    '''
    Creates fail log if not in existence
    Appends new message to log
    '''
    fail_log_path = change_path(fullpath, 'log')
    message = str(message)
    fname = os.path.split(fullpath)[1]
    if not os.path.isfile(fail_log_path):
        with open(fail_log_path, 'x') as log_data:
            log_data.close()

    with open(fail_log_path, 'a+') as log_data:
        log_data.write(f"================= {fname} ================\n")
        log_data.write(message)
        log_data.write("\n")
        log_data.close()


def main():
    '''
    Receives sys.argv[1] path to FFV1 mkv from shell start script via GNU parallel
    Extracts metadata of file, passes to FFmpeg subprocess command, transcodes V210
    Makes framemd5 comparison, and passes V210 mov through mediaconch policy
    If all pass, cleans up files moving to success/ folder and deletes FFV1 mkv.
    '''
    logger_list = []
    if len(sys.argv) < 2:
        logger.warning("SCRIPT EXITING: Error with shell script input:\n %s", sys.argv)
        sys.exit()
    else:
        logger.info("================== START Python3 ffv1 to v210 transcode START ==================")
        check_control()
        fullpath = sys.argv[1]
        file = os.path.split(fullpath)[1]
        if os.path.isfile(fullpath):
            # Build and execute FFmpeg subprocess call
            logger_list.append(f"******** {fullpath} being processed ********")
            ffmpeg_data = []
            # Extract MKV metadata to list and pass to subprocess blocks
            setfield = get_interl(fullpath)
            colour_data = get_colour(fullpath)
            framerate = get_framerate(fullpath)
            color_primaries = colour_data[0]
            color_trc = 'bt709'
            colormatrix = colour_data[1]
            codec = 'v210'
            codec_desc = 'Uncompressed 10-bit 4:2:2'
            ffmpeg_data = [codec, codec_desc, colormatrix, color_trc, color_primaries, setfield, framerate]

            ffmpeg_call = create_ffmpeg_command(fullpath, ffmpeg_data)
            ffmpeg_call_neat = (" ".join(ffmpeg_call), "\n")
            logger_list.append(f"FFmpeg call: {ffmpeg_call_neat}")

            tic = time.perf_counter()
            try:
                subprocess.call(ffmpeg_call)
            except Exception:
                logger_list.append(f"WARNING: FFmpeg command failed: {ffmpeg_call}")
            toc = time.perf_counter()
            encode_time = (toc - tic) // 60
            seconds_time = (toc - tic)
            logger_list.append(f"* Encoding time for {file} was {encode_time} minutes // or in seconds {seconds_time}")

            # Ensure that permissions allow framemd5 work
            os.chmod(change_path(fullpath, 'transcode'), 0o777)

            # Check framemd5's match for MKV and MOV
            tic2 = time.perf_counter()
            md5_mov, md5_mkv = make_framemd5(fullpath)
            toc2 = time.perf_counter()
            md5_time = (toc2 - tic2) // 60
            md5_seconds = (toc2 - tic2)
            logger_list.append(f"* MD5 creation time for FFV1 and MOV: {md5_time} minutes or {md5_seconds} seconds")

            md5_mkv_trim = framemd5_cut(md5_mkv)
            md5_mov_trim = framemd5_cut(md5_mov)
            if md5_mkv_trim == md5_mov_trim:
                logger_list.append(f"*** Framemd5 check passed for MKV and MOV")
                # Collate and output all logs at once for concurrent runs
                for line in logger_list:
                    if 'WARNING' in str(line):
                        logger.warning("%s", line)
                    else:
                        logger.info("%s", line)
                clean_up(fullpath)

            else:
                fail_path = change_path(fullpath, 'failed')
                new_file = change_path(fullpath, 'transcode')
                mkv_fail_path = change_path(fullpath, 'mkv_fail')
                logger_list.append(f"--- {mkv_fail_path} ---")
                fail_log(fullpath, f"{fail_path} being deleted due to Framemd5 mis-match.")
                logger_list.append("*** FRAMEMD5 FILES DO NOT MATCH. Moving Matroska to framemd5_fail/ folder for review")
                try:
                    shutil.move(fullpath, mkv_fail_path)
                    logger_list.append("Moving MKV to framemd5_fail/ folder for review")
                except Exception as err:
                    logger_list.append(f"WARNING: Failed to move MKV to framemd5_fail/ folder: {mkv_fail_path}\n{err}")
                try:
                    shutil.move(new_file, fail_path)
                    logger_list.append(f"Moving {new_file} to failures/ folder: {fail_path} before deletion")
                except Exception:
                    logger_list.append(f"WARNING: Unable to move {new_file} to failures/ folder: {fail_path}")
                try:
                    logger_list.append(f"Deleting {fail_path} file")
                    #os.remove(fail_path)
                except Exception:
                    logger_list.append(f"WARNING: Unable to delete {fail_path}")

                # Collate and output all logs at once for concurrent runs
                for line in logger_list:
                    if 'WARNING' in str(line):
                        logger.warning("%s", line)
                    else:
                        logger.info("%s", line)
        else:
            logger.info("SKIPPING: %s is not a file.", fullpath)

    logger.info("================== END ffv1 to v210 transcode END ==================")


def clean_up(fullpath):
    '''
    Runs conformance check with MediaConch, and pass or fail
    removes the relevant file and appends logs
    '''
    clean = False
    new_file = change_path(fullpath, 'transcode')
    logger.info("Clean up begins for %s", new_file)
    if os.path.isfile(new_file):
        if new_file.endswith(".mov"):
            logger.info("Conformance check: comparing %s with PAL/NTSC policies", new_file)
            result = conformance_check(new_file, MOV_POLICY_PAL)
            if "PASS!" in result:
                logger.info("%s passed the PAL policy checker and it's Matroska can be deleted", new_file)
                clean = True
            result2 = conformance_check(new_file, MOV_POLICY_NTSC)
            if "PASS!" in result2:
                logger.info("%s passed the NTSC policy checker and it's Matroska can be deleted", new_file)
                clean = True

            if clean is False:
                logger.warning("FAIL: %s failed the policy checker. Leaving Matroska for second encoding attempt", new_file)
                fail_log(fullpath, "MOV file failed Mediaconch policy:")
                fail_log(fullpath, result)
                fail_path = change_path(fullpath, 'failed')
                try:
                    # Delete MOV from failures/ path
                    shutil.move(new_file, fail_path)
                    logger.info("Moving %s to failures/ folder: %s", new_file, fail_path)
                except Exception:
                    logger.warning("Unable to move %s to failures/ folder: %s", new_file, fail_path)
                try:
                    logger.info("Deleting %s file as failed mediaconch policy", fail_path)
                    #os.remove(fail_path)
                except Exception:
                    logger.warning("Unable to delete %s", fail_path)

            if clean is True:
                try:
                    new_file_path = change_path(fullpath, 'move')
                    shutil.move(new_file, new_file_path)
                except Exception:
                    logger.warning("Unable to move %s to success folder: %s", new_file, new_file_path)
                try:
                    # Delete FFV1 mkv after successful transcode to V210 mov
                    logger.info("*** DELETION OF MKV FOLLOWING SUCCESSFUL TRANSCODE: %s", fullpath)
                    os.remove(fullpath)
                except Exception:
                    logger.warning("Deletion failure: %s", fullpath)
        else:
            logger.info("Skipping %s, as this file is not ended .mov", new_file)
    else:
        logger.warning("NOT A FILE: %s what is this?", new_file)




if __name__ == "__main__":
    main()
