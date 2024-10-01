#!/usr/bin/env LANG=en_UK.UTF-8 /usr/local/bin/python3

'''
**** SCRIPT TO RUN WITH START.SH SCRIPT, TO POPULATE SYS.ARGV[1] ****
ProRes mov mediaconch policy check, and transcode to h.264 mp4:
1. Shell script populates list with .mov files passes one at
   a time to this Python script from GNU parallel
2. Checks each file against MediaConch prores policy
   If it passes:
     i. Initiates FFmpeg subprocess command
     ii. Encodes with FFmpeg a mp4 file for frame.io viewing
   If it faile:
     i. Writes mediaconch failure message to a failures log
     ii. Moves ProRes to failures folder
3. Successful mp4 compared to basic mediaconch policy (is file whole)
   If it passes:
     i. Moves mp4 to mp4_completed/ folder
     ii. Copies ProRes from Grack_h22 to Grack_f47, md5sum checks
         and if successful deletes original in Grack_h22. If not retries once.
   If it fails:
     i. Deletes mp4 and leaves ProRes for repeat attempt

NOTE:  Needs temporary step that skip rsync and moves to local 'copy'
       folder. I/O waits prevent script completion/progress

2021
'''

import os
import subprocess
import shutil
import logging
import sys
import datetime

# Global variables
DESTINATION = os.environ['FILM_H22_DEST']
MOV_POLICY = os.environ['POLICY_FILM_H22']
MP4_POLICY = os.environ['POLICY_MP4']
LOG = os.environ['SCRIPT_LOG']
TODAY = datetime.date.today()

# Setup logging
logger = logging.getLogger('batch_transcode_proresHD_mp4')
hdlr = logging.FileHandler(os.path.join(LOG, 'batch_transcode_proresHD_mp4.log'))
formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

logger.info("================== START ProRes mov to mp4 transcode START ==================")


def set_output_path(file_path, use):
    '''
    Function to generate multiple output path options .mov and .mp4 usage
    '''
    if 'transcode' in use:
        path_split = os.path.split(file_path)
        filename, extension = os.path.splitext(path_split[1])
        new_filename = 'transcode/' + filename + ".mp4"
        if '/dragon/' in file_path.lower():
            return os.path.join(DESTINATION + 'Dragon/' + new_filename)
        elif '/silversalt/' in file_path.lower():
            return os.path.join(DESTINATION + 'Silversalt/' + new_filename)
        elif '/r3store/' in file_path.lower():
            return os.path.join(DESTINATION + 'R3store/' + new_filename)

    elif 'mp4' in use:
        path_split = os.path.split(file_path)
        filename, extension = os.path.splitext(path_split[1])
        new_filename = 'mp4_complete/' + filename + ".mp4"
        if '/dragon/' in file_path.lower():
            return os.path.join(DESTINATION + 'Dragon/' + new_filename)
        elif '/silversalt/' in file_path.lower():
            return os.path.join(DESTINATION + 'Silversalt/' + new_filename)
        elif '/r3store/' in file_path.lower():
            return os.path.join(DESTINATION + 'R3store/' + new_filename)

    elif 'copy' in use:
        path_split = os.path.split(file_path)
        path_split_2 = os.path.split(path_split[0])
        filename, extension = os.path.splitext(path_split[1])
        new_filename = "copy/" + filename + extension
        return os.path.join(path_split_2[0], new_filename)

    elif 'success' in use:
        path_split = os.path.split(file_path)
        filename, extension = os.path.splitext(path_split[1])
        new_filename = "success/" + filename + ".mov"
        if '/dragon/' in file_path.lower():
            return os.path.join(DESTINATION + 'Dragon/' + new_filename)
        elif '/silversalt/' in file_path.lower():
            return os.path.join(DESTINATION + 'Silversalt/' + new_filename)
        elif '/r3store/' in file_path.lower():
            return os.path.join(DESTINATION + 'R3store/' + new_filename)

    elif 'fail' in use:
        path_split = os.path.split(file_path)
        path_split_2 = os.path.split(path_split[0])
        filename, extension = os.path.splitext(path_split[1])
        new_filename = "failures/" + filename + extension
        return os.path.join(path_split_2[0], new_filename)

    elif 'log' in use:
        path_split = os.path.split(file_path)
        new_filename = "failures/h22_film_digitisation_ProRes_failure.log"
        return os.path.join(path_split[0], new_filename)

    elif 'kill' in use:
        path_split = os.path.split(file_path)
        new_filename = "failures/h22_film_digitisation_MP4_failure.log"
        return os.path.join(path_split[0], new_filename)


def create_ffmpeg_command(file_path):
    '''
    Subprocess structure for FFmpeg command, by Michael Norman
    '''

    output_fullpath = set_output_path(file_path, 'transcode')

    ffmpeg_program_call = [
        "ffmpeg"
    ]

    input_video_file = [
        "-i", file_path,
        "-nostdin"
    ]

    map_command = [
        "-movflags", "+faststart"
    ]

    video_settings = [
        "-c:v", "libx264",
        "-preset",  "slow",
        "-pix_fmt", "yuv420p"
    ]

    crf_settings = [
        "-crf", "28"
    ]

    audio_settings = [
        "-c:a", "aac",
        output_fullpath
    ]

    logger.info("The new FFmpeg h.264 mp4 file will be written to: %s", output_fullpath)

    return ffmpeg_program_call + input_video_file + map_command + video_settings + crf_settings + audio_settings


def conformance_check(file_path, policy):
    '''
    Checks mediaconch policy against file
    '''

    mediaconch_cmd = [
        'mediaconch', '--force',
        '-p', policy,
        file_path
    ]

    result = subprocess.check_output(mediaconch_cmd)
    result = str(result)

    if 'N/A!' in result or 'pass!' not in result:
        return "FAIL!\n{}".format(result)
    else:
        return "PASS!"


def fail_log(fail_log_path, file_path, message):
    '''
    Append failure message to log, if not there yet, recreate and append
    '''
    message = str(message)
    if os.path.isfile(fail_log_path):
        with open(fail_log_path, 'a') as log_data:
            log_data.write("================= {} ================ {}\n".format(file_path, TODAY))
            log_data.write(message)
            log_data.write("\n")
            log_data.close()
    else:
        with open(fail_log_path, 'x') as log_data:
            log_data.close()
        with open(fail_log_path, 'a') as log_data:
            log_data.write("================= {} ================ {}\n".format(file_path, TODAY))
            log_data.write(message)
            log_data.write("\n")
            log_data.close()


def md5_check(file_path1, file_path2):
    '''
    Makes MD5s and checks if they are the same
    '''
    path1 = os.path.split(file_path1)
    filename1, ext = os.path.splitext(path1[1])
    path2 = os.path.split(file_path2)
    filename2, ext = os.path.splitext(path2[1])

    md5_file1 = [
        'md5sum', file_path1
    ]

    try:
        logger.info("Beginning MD5 generation for ProRes file %s", file_path1)
        check1 = subprocess.check_output(md5_file1)
        check1 = str(check1)
    except:
        logger.exception("MD5 command failure: %s", file_path1)

    md5_file2 = [
        'md5sum', file_path2
    ]

    try:
        logger.info("Beginning MD5 generation for ProRes file %s", file_path2)
        check2 = subprocess.check_output(md5_file2)
        check2 = str(check2)
    except:
        logger.exception("MD5 command failure: %s", file_path2)

    if check1[2:36] == check2[2:36]:
        logger.info("MD5 checksums match! ProRes1: %s ProRes2: %s", check1[2:36], check2[2:36])
        return 'MATCH'
    else:
        logger.warning("MD5 checksums DO NOT MATCH %s and %s", check1, check2)
        return 'FAIL'


def main():
    '''
    Script receives sys.argv from GNU parallel list grep and processes one ProRes from list
    '''
    if len(sys.argv) < 2:
        print("SCRIPT EXITING: Error with shell script input. Please input:\n \
               python3 batch_transcode_proresHD_mp4.py /path_to_file/file.mov")
        logger.warning("SCRIPT EXITING: Error with shell script input. Please input:\n \
                        python3 batch_transcode_proresHD_mp4.py /path_to_file/file.mov")
        sys.exit()
    else:
        file_path = sys.argv[1]
        if file_path.endswith(".mov"):
            result = conformance_check(file_path, MOV_POLICY)
            if 'PASS!' in result:
                logger.info("MediaConch policy pass: %s", file_path)
                logger.info("Beginning FFmpeg transcode to H.264 mp4")
                ffmpeg_call = []
                ffmpeg_call = create_ffmpeg_command(file_path)
                # FFmpeg encoding begins
                try:
                    subprocess.call(ffmpeg_call)
                except Exception:
                    logger.exception("FFmpeg command failed: %s", ffmpeg_call)
                    raise

            elif 'FAIL!' in result:
                fail_mov_path = set_output_path(file_path, 'fail')
                trim = os.path.split(file_path)
                fail_log_path = set_output_path(trim[0], 'log')
                fail_log(fail_log_path, fail_mov_path, result)
                logger.warning("%s - failed Mediaconch policy. Moving to failures/ folder.", file_path)
                # Move prores to failures/ path
                try:
                    shutil.move(file_path, fail_mov_path)
                    logger.info("ProRes moved to failed/ and log appended. Script exiting!")
                except Exception:
                    logger.exception("Unable to move %s to %s. Script exiting", file_path, fail_mov_path)
                sys.exit()
        else:
            logger.info("%s - Skipping as this is not a .mov file", file_path)

        # Clean up after encoding
        clean_up(file_path)

    logger.info("================== END ProRes <%s> to MP4 transcode END ==================", file_path)


def clean_up(file_path):
    '''
    Check MP4 against mediaconch policy then trigger ProRes/MP4 clean up
    '''
    new_file = set_output_path(file_path, 'transcode')
    logger.info("clean_up(): %s", new_file)
    if os.path.isfile(new_file) and new_file.endswith(".mp4"):
        logger.info("clean_up(): Conformance checking %s with MP4 policy", new_file)
        result = conformance_check(new_file, MP4_POLICY)

        if "PASS!" in result:
            # Successful, moving mp4 to mp4_completed folder
            logger.info("clean_up(): PASS! MP4 policy check")
            mp4_complete_path = set_output_path(file_path, 'mp4')
            try:
                shutil.move(new_file, mp4_complete_path)
                logger.info("clean_up(): Moving %s to mp4_completed folder: %s", new_file, mp4_complete_path)
            except Exception:
                logger.warning("clean_up(): Unable to move %s to mp4_completed/ folder: %s", new_file, mp4_complete_path)
            # Move ProRes move to success/ path on Grack_F47
#            logger.info("clean_up(): MP4 creation successful. Moving ProRes to Grack_F47")
#            new_mov_path = set_output_path(file_path, 'success')
#            rsync(file_path, new_mov_path)
#            test = md5_check(file_path, new_mov_path)
            move_to_copy = set_output_path(file_path, 'copy')
            logger.info("Moving MOV to copy folder: %s:", move_to_copy)
            try:
                shutil.move(file_path, move_to_copy)
            except Exception:
                logger.exception("Unable to move %s to %s", file_path, move_to_copy)

            '''
            if 'MATCH' in test:
                logger.info("ProRes file %s moved successfully and MD5 checksums match", new_mov_path)
                logger.info("Deleting original file: %s", file_path)
                os.remove(file_path)
            else:
                logger.warning("ProRes file copy failed Diff check of MD5 sum. Deleting copy and retrying")
                os.remove(new_mov_path)
                rsync(file_path, new_mov_path)
                test = md5_check(file_path, new_mov_path)
                if 'MATCH' in test:
                    logger.info("ProRes file %s moved successfully after second attempt and MD5 checksums match", new_mov_path)
                    logger.info("Deleting original file: %s", file_path)
                    os.remove(file_path)
                else:
                    fail_mov_path = set_output_path(file_path, 'fail')
                    logger.warning("Unable to move ProRes successfully after two attempts: %s", file_path)
                    logger.warning("Moving ProRes to failures folder, with warning appended to failure log")
                    message = "==============================================================\n \
                               Unable to copy ProRes to Grack_h22. MP4 creation successful.\n \
                               {}\n \
                               This item needs manually relocating in Grack_F47.\n \
                               ==============================================================".format(file_path)
                    trim = os.path.split(file_path)
                    fail_log_path = set_output_path(trim[0], 'log')
                    fail_log(fail_log_path, fail_mov_path, message)
                    try:
                        shutil.move(file_path, fail_mov_path)
                    except Exception:
                        logger.exception("Failed to move ProRes %s to %s", file_path, fail_mov_path)
            '''
        elif 'FAIL!' in result:
            # Failed. Delete MP4 and leave ProRes to try again
            fail_mp4_path = set_output_path(new_file, 'fail')
            trim = os.path.split(new_file)
            fail_log_path = set_output_path(trim[0], 'kill')
            fail_log(fail_log_path, fail_mp4_path, result)
            logger.warning("clean_up(): FAILED: %s failed the MP4 policy checker. Moving to failures.", new_file)
            try:
                shutil.move(new_file, fail_mp4_path)
            except Exception:
                logger.exception("Unable to move %s to %s", new_file, fail_mp4_path)
        else:
            logger.warning("clean_up(): Mediaconch policy comparison failed for file %s \t %s", new_file, result)

    else:
        logger.info("clean_up(): NOT AN MP4 FILE: %s SKIPPING", new_file)


def rsync(file_path1, file_path2):
    '''
    Move ProRes from Grack_h22 to Grack_f47 using rsync
    '''
    rsync_cmd = [
        'rsync', '-avh',
        file_path1, file_path2
    ]

    try:
        logger.info("rsync(): Beginning rsync move of file %s to %s", file_path1, file_path2)
        subprocess.call(rsync_cmd)
    except Exception:
        logger.exception("rsync(): Move command failure: %s to %s", file_path1, file_path2)


if __name__ == "__main__":
    main()
