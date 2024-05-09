#!/usr/bin/env python3

'''
*** THIS SCRIPT MUST RUN WITH SHELL SCRIPT LAUNCH TO PASS FILES TO SYS.ARGV[1] AND DRIVE PARALLEL ***

Script that takes BlueFish MKV tbc 1/1000 and encodes to MKV tbc 1/25:
1. Shell script searches in paths for files that end in '.mkv' and passes on one at a time to Python
2. Receives single path as sys.argv[1], checks metadata of file acquiring field order, colour data etc
   and updates DAR from 1.26 to 1.29.
3. Populates FFmpeg subprocess command based on format decision from retrieved data
4. Transcodes new file into QNAP_08 path with inherited source name
5. Runs framemd5 checks against the FFV1 matroska and duplicate, checks if they're identical
   If identical:
     i. verifies new MKV passes mediaconch policy
     ii. If yes, deletes source MKV file and updates log with success
         If no, deletes duplicate MKV file and updates log with mediaconch failure
   If not identical:
     i. Duplicate is deleted from new QNAP08 path and log is updated with framemd5 mismatch data
     ii. Source file moved to 'problem' subfolder for human intervention

Python 3.7+
Joanna White
2022
'''

import os
import sys
import json
import time
import shutil
import logging
import datetime
import subprocess

# Global paths from environment vars
SOURCE = os.environ['BLUEFISH_MKV']
MKV_POLICY = os.environ['MKV_POLICY']
TBC_LOG = os.environ['TBC_LOG']
LOG = os.environ['SCRIPT_LOG']
FRAMEMD5_PATH = os.environ['BLUEFISH_TEMP']
CONTROL_JSON = os.path.join(LOG, 'downtime_control.json')

# Setup logging
logger = logging.getLogger('QNAP_08_bluefish_ffv1_tbc_fix.py')
hdlr = logging.FileHandler(os.path.join(LOG, 'QNAP_08_bluefish_ffv1_tbc_fix_folders.log'))
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


def get_fps(fullpath):
    '''
    Retrieve fps for source file
    '''
    mediainfo_cmd = [
        'mediainfo',
        '--Language=raw',
        '--Output=Video;%FrameRate%',
        fullpath
    ]

    fps = subprocess.check_output(mediainfo_cmd)
    fps = fps.decode('utf-8')
    if '.' in fps:
        fps = fps.split('.')[0]

    return fps


def get_dar(fullpath):
    '''
    Retrieves metadata DAR info and returns as string
    '''
    cmd = [
        'mediainfo',
        '--Language=raw', '--Full',
        '--Inform="Video;%DisplayAspectRatio%"',
        fullpath
    ]

    cmd[3] = cmd[3].replace('"', '')
    dar_setting = subprocess.check_output(cmd)
    dar_setting = dar_setting.decode('utf-8')
    dar = str(dar_setting).rstrip('\n')
    return dar


def adjust_dar_metadata(filepath):
    '''
    Use MKVToolNix MKVPropEdit to
    adjust the metadata for PAR output
    check output correct
    '''
    dar = get_dar(filepath)

    cmd = [
        'mkvpropedit', filepath,
        '--edit', 'track:v1',
        '--set', 'display-width=295',
        '--set', 'display-height=228'
    ]

    confirmed = subprocess.run(cmd, shell=False, check=True, universal_newlines=True, stdout=subprocess.PIPE, text=True)
    confirmed = str(confirmed.stdout)
    print(confirmed)

    if 'The changes are written to the file.' not in str(confirmed):
        print(f"DAR conversion failed: {confirmed}")
        return False

    new_dar = get_dar(filepath)
    if '1.29' in new_dar:
        print(f"DAR converted from {dar} to {new_dar}")
        return True


def create_ffmpeg_command(fullpath, outpath, data=None):
    '''
    Subprocess command build, with variations
    added based on metadata extraction
    '''

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
        "-map", "0"
    ]

    video_settings = [
        "-c:v", "ffv1",
        "-level", "3",
        "-g", "1",
        "-slicecrc", "1",
        "-slices", "24"
    ]

    colour_build = [
        "-color_primaries", f"{data[4]}",
        "-color_trc", f"{data[3]}",
        "-colorspace", f"{data[2]}"
    ]

    interlace = [
        "-vf", f"setfield={data[5]},fps=fps={data[1]}"
    ]

    audio_settings = [
        "-c:a", "copy"
    ]

    out_settings = [
        "-n", outpath
    ]

    return ffmpeg_program_call + input_video_file + map_command + video_settings + colour_build + \
           interlace + audio_settings + out_settings


def conformance_check(filepath):
    '''
    Checks mediaconch policy against new MKV file
    '''

    mediaconch_cmd = [
        'mediaconch', '--force',
        '-p', MKV_POLICY,
        filepath
    ]

    try:
        success = subprocess.check_output(mediaconch_cmd)
        success = success.decode('utf-8')
    except Exception:
        success = ""
        print(f"Mediaconch policy retrieval failure for {filepath}")

    if success.startswith('N/A'):
        return f"FAIL! {success}"
    elif success.startswith('pass!'):
        return "PASS!"
    elif success.startswith('fail!'):
        return f"FAIL! {success}"
    else:
        return f"FAIL! {success}"


def make_framemd5(mkv_path1, mkv_path2):
    '''
    Creates MKV and MOV framemd5 and returns path locations for generated files
    Uses lutyuv trim due to non-compliant yuv data capture at source (fault of capture cards)
    This losslessly passed to matroska, but in transcoding back to V210 mov yuv regions
    0-4 and 1019-1023 become lossy failing framemd5 comparison. lutyuv command courtesy Dave Rice.
    UPDATE FOR BLUEFISH MKV (WITH AUDIO COMPARISONS, MAY NEED UPDATING)
    '''
    filename = os.path.split(mkv_path1)[1]
    output_mkv1 = os.path.join(FRAMEMD5_PATH, f"{filename}.bluefish.mkv.framemd5")
    output_mkv2 = os.path.join(FRAMEMD5_PATH, f"{filename}.corrected.mkv.framemd5")

    framemd5_mkv = [
        "ffmpeg", "-nostdin", "-y",
        "-i", mkv_path1, "-an",
        "-vf", "lutyuv=y=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):u=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):v=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val))",
        "-f", "framemd5",
        output_mkv1
    ]

    try:
        subprocess.call(framemd5_mkv)
    except Exception:
        logger.exception("Framemd5 command failure: %s", mkv_path1)

    framemd5_mkv2 = [
        "ffmpeg", "-nostdin", "-y",
        "-i", mkv_path2, "-an",
        "-vf", "lutyuv=y=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):u=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val)):v=if(gt(val\,1019)\,1019\,if(lt(val\,4)\,4\,val))",
        "-f", "framemd5",
        output_mkv2
    ]

    try:
        subprocess.call(framemd5_mkv2)
    except Exception:
        logger.exception("Framemd5 command failure: %s", mkv_path2)

    return (output_mkv1, output_mkv2)


def diff_check(md5_mkv1, md5_mkv2):
    '''
    Opens and compares two MD4 paths with trim applied to
    prevent differing TBN data upsetting results
    '''

    mkv1_manifest = []
    mkv2_manifest = []

    with open(md5_mkv1, 'r') as file1:
        mkv1 = file1.read().splitlines()
    for line in mkv1[8:]:
        mkv1_manifest.append(line.split(',')[-1])

    with open(md5_mkv2, 'r') as file2:
        mkv2 = file2.read().splitlines()
    for line in mkv2[8:]:
        mkv2_manifest.append(line.split(',')[-1])

    print(mkv1_manifest)
    print(mkv2_manifest)

    if len(mkv1_manifest) == len(mkv2_manifest):
        length_check = len(mkv1_manifest) - 3
    else:
        if len(mkv1_manifest) < len(mkv2_manifest):
            length_check = len(mkv1_manifest) - 3
        else:
            length_check = len(mkv2_manifest) - 3

    if mkv1_manifest[:length_check] == mkv2_manifest[:length_check]:
        return 'MATCH'
    else:
        return 'FAIL'


def fail_log(fullpath, message):
    '''
    Creates fail log if not in existence
    Appends new message to log
    '''
    message = str(message)
    dt = datetime.datetime.now()
    dtime = dt.strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.isfile(TBC_LOG):
        with open(TBC_LOG, 'x') as log_data:
            log_data.close()

    with open(TBC_LOG, 'a+') as log_data:
        log_data.write(f"==== {fullpath}: {dtime} \n")
        log_data.write(message)
        log_data.write("\n")
        log_data.close()


def main():
    '''
    Receives sys.argv[1] path to FFV1 mkv from shell start script via GNU parallel
    Extracts metadata of file, passes to FFmpeg subprocess command, transcodes V210
    Makes framemd5 comparison, and passes V210 mov through mediaconch policy
    If all pass, cleans up files moving to success folder and deletes FFV1 mkv.
    '''
    logger_list = []
    if len(sys.argv) < 2:
        logger.warning("SCRIPT EXITING: Error with shell script input:\n %s", sys.argv)
        sys.exit(f'Error with shell script input {sys.argv}')
    else:
        logger.info("================== START BlueFish MKV TBC correction START ==================")
        check_control()
        fullpath = sys.argv[1]
        root, file = os.path.split(fullpath)
        outpath = os.path.join(root, 'transcoded', file)
        completed = os.path.join(root, 'completed', file)
        if os.path.exists(fullpath):
            # Build and execute FFmpeg subprocess call
            logger_list.append(f"******** {fullpath} being processed ********")
            ffmpeg_data = []

            # Update CID with DAR warning
            dar = get_dar(fullpath)
            print(f"************ {dar} ************")
            if '1.26' in dar:
                logger_list.append(f'{file}\tFile has 1.26 DAR. Converting to 1.29 DAR')
                logger_list.append(f'{file}\tFile found with 1.26 DAR. Converting to 1.29 DAR')
                confirmed = adjust_dar_metadata(fullpath)
                if not confirmed:
                    logger_list.append(f'WARNING: {file}\tCould not adjust DAR metadata.')
                else:
                    logger_list.append(f'{file}\tFile DAR header metadata changed to 1.29')

            # Extract MKV metadata to list and pass to subprocess blocks
            setfield = get_interl(fullpath)
            colour_data = get_colour(fullpath)
            color_primaries = colour_data[0]
            color_trc = 'bt709'
            colormatrix = colour_data[1]
            fps = get_fps(fullpath)
            codec = 'ffv1'
            ffmpeg_data = [codec, fps, colormatrix, color_trc, color_primaries, setfield]
            ffmpeg_call = create_ffmpeg_command(fullpath, outpath, ffmpeg_data)
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
            logger_list.append(f"*** Encoding time for {file} was {encode_time} minutes // or in seconds {seconds_time}")

            # Check framemd5's match for MKV and MOV
            tic2 = time.perf_counter()
            md5_mkv1, md5_mkv2 = make_framemd5(fullpath, outpath)
            toc2 = time.perf_counter()
            md5_time = (toc2 - tic2) // 60
            md5_seconds = (toc2 - tic2)
            logger_list.append(f"*** MD5 creation time for files: {md5_time} minutes or {md5_seconds} seconds")
            result = diff_check(md5_mkv1, md5_mkv2)
            if 'MATCH' in result:
                logger_list.append("Framemd5 check passed for source and copy MKV files")

                # Run conformance check
                result = conformance_check(outpath)
                if "PASS!" in result:
                    logger_list.append(f"PASS! {outpath} passed the policy checker and it's Matroska can be deleted")
                    try:
                        # Delete FFV1 mkv after successful transcode to MKV
                        shutil.move(fullpath, completed)
                        fname = os.path.split(fullpath)[-1]
                        completed_pth = os.path.join(completed, fname)
                        logger_list.append("*** FILE BEING MOVED TO COMPLETED PATH: %s", fname)
                    except Exception:
                        logger_list.append(f"WARNING: Deletion failure: {fullpath}")
                else:
                    logger_list.append(f"WARNING: {outpath} failed the policy checker. Leaving Matroska for second encoding attempt")
                    fail_log(fullpath, f"Failed Mediaconch policy check:\n{result}")

                    try:
                        logger_list.append(f"Deleting {outpath} file as failed mediaconch policy")
                        os.remove(outpath)
                    except Exception:
                        logger_list.append(f"WARNING: Unable to delete {outpath}")

                # Collate and output all logs at once for concurrent runs
                for line in logger_list:
                    if 'WARNING' in str(line):
                        logger.warning("%s", line)
                    else:
                        logger.info("%s", line)

            else:
                logger_list.append(f"--- {outpath} ---")
                fail_log(fullpath, "Failed FRAMEMD5 checks, appending 'failed_' for review.")
                fail_log(fullpath, f"Deleting: {outpath}")
                logger_list.append("FRAMEMD5 FILES DO NOT MATCH")

                md5_mkv1_split = os.path.split(md5_mkv1)
                rename_md5_mkv1 = os.path.join(FRAMEMD5_PATH, f'failed_{md5_mkv1_split[1]}')
                md5_mkv2_split = os.path.split(md5_mkv2)
                rename_md5_mkv2 = os.path.join(FRAMEMD5_PATH, f'failed_{md5_mkv2_split[1]}')

                # Move framemd5 files from qnap02 to qnap04 (new block)
                logger_list.append(f"MOVING: {md5_mkv2} TO {rename_md5_mkv2}")
                os.rename(md5_mkv2, rename_md5_mkv2)
                os.rename(md5_mkv1, rename_md5_mkv1)
                try:
                    logger_list.append(f"Deleting {outpath} file as failed mediaconch policy")
                    os.remove(outpath)
                except Exception:
                    logger_list.append(f"WARNING: Unable to delete {outpath}")

                # Collate and output all logs at once for concurrent runs
                for line in logger_list:
                    if 'WARNING' in str(line):
                        logger.warning("%s", line)
                    else:
                        logger.info("%s", line)
        else:
            logger.info("SKIPPING: Filename doesn't exist: %s", fullpath)

    logger.info("================== END BlueFish MKV TBC correction END =============\n")



if __name__ == "__main__":
    main()
