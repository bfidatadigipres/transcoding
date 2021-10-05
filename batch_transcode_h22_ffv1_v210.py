#!/usr/bin/env LANG=en_UK.UTF-8 /usr/local/bin/python3

'''
*** THIS SCRIPT MUST RUN WITH SHELL SCRIPT LAUNCH TO PASS FILES TO SYS.ARGV[1] AND DRIVE PARALLEL ***

Script that takes FFv1 Matroska files and encodes to v210 mov:
1. Shell script searches in paths for files that end in '.mkv' and passes on one at a time to Python
2. Receives single path as sys.argv[1], checks metadata of file acquiring field order, colour data etc
3. Populates FFmpeg subprocess command based on format decisiong from retrieved data
4. Transcodes new file into 'transcode/' folder named as {filename}.mov
5. Runs framemd5 checks against the FFV1 matroska and V210 mov file, checks if they're identical
   If identical:
     i. verifies V210 mov passes mediaconch policy
     ii. If yes, moves identical V210 mov to success/ folder
         If no, moves V210 mov to failures/ folder and appends failures log. Deletes V210 mov
     iii. If mediaconch passed FFV1 matroska is deleted
   If not identical:
     i. File is not mediaconch checked but moved to failures/ and failure log updated
     ii. V210 mov is deleted and FFV1 matroska is left in place for another transcoding attempt

Python 3.7+
Joanna White 2021
'''

import os
import subprocess
import shutil
import logging
import time
import sys

# Global paths from server environmental variables
MOV_POLICY = os.environ['MOV_POLICY_H22']
FRAMEMD5_PATH = os.environ['FRAMEMD5_PATH']
LOG = os.environ['SCRIPT_LOG']

# Setup logging
logger = logging.getLogger('batch_transcode_h22_ffv1_v210')
hdlr = logging.FileHandler(os.path.join(LOG, 'batch_transcode_h22_ffv1_v210.log'))
formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

logger.info("================== START Python3 ffv1 to v210 transcode START ==================")


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
    '''

    if 'transcode' in use:
        path_split = os.path.split(fullpath)
        filename = os.path.splitext(path_split[1])
        return os.path.join(path_split[0], 'transcode/', '{}.mov'.format(filename[0]))

    elif 'move' in use:
        path_split = os.path.split(fullpath)
        filename = os.path.splitext(path_split[1])
        return os.path.join(path_split[0], 'success/', '{}.mov'.format(filename[0]))

    elif 'fail' in use:
        path_split = os.path.split(fullpath)
        filename = os.path.splitext(path_split[1])
        return os.path.join(path_split[0], 'failures/', '{}.mov'.format(filename[0]))

    elif 'log' in use:
        path_split = os.path.split(fullpath)
        new_filename = "failures/h22_mov_failure.log"
        return os.path.join(path_split[0], new_filename)


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
        "-c:v", "{}".format(data[0])
    ]

    colour_build = [
        "-color_primaries", "{}".format(data[4]),
        "-color_trc", "{}".format(data[3]),
        "-colorspace", "{}".format(data[2]),
        "-color_range", "1",
        "-metadata:s:v:0", "'encoder={}'".format(data[1])
    ]

    interlace = [
        "-vf", "setfield={}".format(data[5])
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


def conformance_check(filepath):
    '''
    Checks mediaconch policy against new V210 mov
    '''

    mediaconch_cmd = [
        'mediaconch', '--force',
        '-p', MOV_POLICY,
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
        return "FAIL!"
    elif 'pass!' in success:
        logger.info("PASS: %s has passed the mediaconch policy", filepath)
        return "PASS!"
    elif 'fail!' in success:
        logger.warning("FAIL! The policy has failed for %s:\n %s", filepath, success)
        return "FAIL!"
    else:
        return "FAIL!"
        logger.warning("FAIL! The policy has failed for %s:\n%s", filepath, success)


def make_framemd5(fullpath):
    '''
    Creates MKV and MOV framemd5 and returns path locations for generated files
    Uses lutyuv trim due to non-compliant yuv data capture at source (fault of capture cards)
    This losslessly passed to matroska, but in transcoding back to V210 mov yuv regions
    0-4 and 1019-1023 become lossy failing framemd5 comparison. lutyuv command courtesy Dave Rice.
    '''
    new_filepath = change_path(fullpath, 'transcode')
    fullpath_split = os.path.split(fullpath)
    filename = os.path.splitext(fullpath_split[1])
    output_mkv = os.path.join(fullpath_split[0] + '/' + filename[0] + '.mkv.framemd5')
    output_mov = os.path.join(fullpath_split[0] + '/' + filename[0] + '.mov.framemd5')

    framemd5_mkv = [
        "ffmpeg", "-nostdin",
        "-i", fullpath,
        "-vf", "lutyuv=y=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):u=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):v=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val))",
        "-f", "framemd5",
        output_mkv
    ]

    try:
        logger.info("Beginning FRAMEMD5 generation for Matroska file %s", fullpath)
        subprocess.call(framemd5_mkv)
    except Exception:
        logger.exception("Framemd5 command failure: %s", fullpath)

    framemd5_mov = [
        "ffmpeg", "-nostdin",
        "-i", new_filepath,
        "-vf", "lutyuv=y=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):u=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):v=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val))",
        "-f", "framemd5",
        output_mov
    ]

    try:
        logger.info("Beginning FRAMEMD5 generation for MOV file %s", new_filepath)
        subprocess.call(framemd5_mov)
    except Exception:
        logger.exception("Framemd5 command failure: %s", new_filepath)

    return (output_mkv, output_mov)


def diff_check(md5_mkv, md5_mov):
    '''
    Compare two framemd5s for exact match
    '''
    diff_cmd = [
        'diff', '-s',
        md5_mkv, md5_mov
    ]

    try:
        success = subprocess.check_output(diff_cmd)
        success = str(success)
    except:
        success = ""
        logger.warning("Diff check failed for %s and %s", md5_mkv, md5_mov)

    if 'are identical' in success:
        return 'MATCH'
    else:
        return 'FAIL'


def fail_log(fullpath, message):
    '''
    Appends failure message if log present, otherwise creates fail log
    and appends new message to it
    '''
    fail_log_path = change_path(fullpath, 'log')
    message = str(message)
    if os.path.isfile(fail_log_path):
        with open(fail_log_path, 'a') as log_data:
            log_data.write("================= {} ================\n".format(fullpath))
            log_data.write(message)
            log_data.write("\n")
            log_data.close()
    else:
        with open(fail_log_path, 'x') as log_data:
            log_data.close()
        with open(fail_log_path, 'a') as log_data:
            log_data.write("================= {} ================\n".format(fullpath))
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
    if len(sys.argv) < 2:
        logger.warning("SCRIPT EXITING: Error with shell script input:\n %s", sys.argv)
        sys.exit()
    else:
        fullpath = sys.argv[1]
        path_split = os.path.split(fullpath)
        file = path_split[1]
        if file.startswith("N_") and '/mkv/' not in fullpath:
            # Build and execute FFmpeg subprocess call
            logger.info("******** <%s> being processed ********", fullpath)
            ffmpeg_data = []
            # Extract MKV metadata to list and pass to subprocess blocks
            setfield = get_interl(fullpath)
            colour_data = get_colour(fullpath)
            color_primaries = colour_data[0]
            color_trc = 'bt709'
            colormatrix = colour_data[1]
            codec = 'v210'
            codec_desc = 'Uncompressed 10-bit 4:2:2'
            ffmpeg_data = [codec, codec_desc, colormatrix, color_trc, color_primaries, setfield]

            ffmpeg_call = create_ffmpeg_command(fullpath, ffmpeg_data)
            ffmpeg_call_neat = (" ".join(ffmpeg_call), "\n")
            logger.info("FFmpeg call: %s", ffmpeg_call_neat)
            print(ffmpeg_call_neat)

            tic = time.perf_counter()
            try:
                subprocess.call(ffmpeg_call)
            except Exception:
                logger.critical("FFmpeg command failed: %s", ffmpeg_call)
            toc = time.perf_counter()
            encode_time = (toc - tic) // 60
            logger.info(f"*** Encoding time for {file}: {encode_time} minutes")

            # Check framemd5's match for MKV and MOV
            tic2 = time.perf_counter()
            framemd5 = make_framemd5(fullpath)
            toc2 = time.perf_counter()
            md5_time = (toc2 - tic2) // 60
            logger.info(f"*** MD5 creation time for FFV1 and MOV: {md5_time} minutes")
            md5_mkv = framemd5[0]
            md5_mov = framemd5[1]
            result = diff_check(md5_mkv, md5_mov)
            if 'MATCH' in result:
                logger.info("Framemd5 check passed for %s and %s\nCopying to top level framemd5 folder (deleting local version)", md5_mkv, md5_mov)
                shutil.copy(md5_mov, FRAMEMD5_PATH)
                shutil.copy(md5_mkv, FRAMEMD5_PATH)
                os.remove(md5_mov)
                os.remove(md5_mkv)
                clean_up(fullpath)
            else:
                fail_path = change_path(fullpath, 'fail')
                new_file = change_path(fullpath, 'transcode')
                fail_log(fullpath, "{} being deleted due to Framemd5 mis-match. Failed framemd5 manifests moving to 'framemd5/' appended 'failed_' for review".format(fail_path))
                logger.warning("FRAMEMD5 FILES DO NOT MATCH. Cleaning up files to enable re-encoding attempt")
                md5_mkv_split = os.path.split(md5_mkv)
                rename_md5_mkv = os.path.join(FRAMEMD5_PATH, 'failed_{}'.format(md5_mkv_split[1]))
                md5_mov_split = os.path.split(md5_mov)
                rename_md5_mov = os.path.join(FRAMEMD5_PATH, 'failed_{}'.format(md5_mov_split[1]))
                try:
                    shutil.move(md5_mov, rename_md5_mov)
                    shutil.move(md5_mkv, rename_md5_mkv)
                    logger.info("Moving framemd5 manifest to framemd5/ folder renamed 'failed_'")
                except Exception:
                    logger.warning("Unable to move framemd5 files to failures/ folder")
                try:
                    shutil.move(new_file, fail_path)
                    logger.info("Moving %s to failures/ folder: %s before deletion", new_file, fail_path)
                except Exception:
                    logger.warning("Unable to move %s to failures/ folder: %s", new_file, fail_path)
                try:
                    logger.info("Deleting %s file", fail_path)
                    os.remove(fail_path)
                except Exception:
                    logger.warning("Unable to delete %s", fail_path)
        else:
            logger.info("SKIPPING: %s is an '/mkv/' path ** NOT FOR TRANSCODING **", fullpath)

    logger.info("================== END ffv1 to v210 transcode END ==================")


def clean_up(fullpath):
    '''
    Runs conformance check with MediaConch, and pass or fail
    removes the relevant file and appends logs
    '''
    new_file = change_path(fullpath, 'transcode')
    logger.info("Clean up begins for %s", new_file)
    if os.path.isfile(new_file):
        if new_file.endswith(".mov"):
            logger.info("Conformance check: comparing %s with policy", new_file)
            result = conformance_check(new_file)
            if "PASS!" in result:
                logger.info("%s passed the policy checker and it's Matroska can be deleted", new_file)
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
                logger.warning("FAIL: %s failed the policy checker. Leaving Matroska for second encoding attempt", new_file)
                fail_log(fullpath, result)
                fail_path = change_path(fullpath, 'fail')
                try:
                    # Delete MOV from failures/ path
                    shutil.move(new_file, fail_path)
                    logger.info("Moving %s to failures/ folder: %s", new_file, fail_path)
                except Exception:
                    logger.warning("Unable to move %s to failures/ folder: %s", new_file, fail_path)
                try:
                    logger.info("Deleting %s file as failed mediaconch policy")
                    os.remove(fail_path)
                except Exception:
                    logger.warning("Unable to delete %s", fail_path)
        else:
            logger.info("Skipping %s, as this file is not ended .mov", new_file)
    else:
        logger.warning("NOT A FILE: %s what is this?", new_file)


if __name__ == "__main__":
    main()
