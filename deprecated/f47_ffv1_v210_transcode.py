#!/usr/bin/env LANG=en_UK.UTF-8 /usr/local/bin/python3

'''
Script that daily checks watch folder for FFV1 Matroska files
that need encoding to v210 mov:
1. Searches in path for files that end in MKV
2. Checks metadata of each file against DAR and height
3. Selects FFmpeg subprocess command based on DAR/height
4. Encodes with FFmpeg a v210 MOV back to MKV path as {}_v210.mov
5. Verifies MOV passes mediaconch policy (therefore successful)
6. Moves MOV to success folder, signalling safe to edit with
7. Deletes MKV that has successful MOV pass of file with same name

Joanna White 2020
'''

import os
import time
import shutil
import logging
import subprocess

# Global paths from environment vars
PATH = os.environ['VID_IS']
MOV_POLICY = os.environ['MOV_POLICY']
DELIVERY_PATH = os.environ['VID_SUCCESS']
LOG = os.environ['SCRIPT_LOG']

# Setup logging
logger = logging.getLogger('f47_ffv1_v210_transcode')
hdlr = logging.FileHandler(os.path.join(LOG, 'f47_ffv1_v210_transcode.log'))
formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

logger.info("================== START F47 ffv1 to v210 transcode START ==================")


def get_dar(fullpath):
    '''
    Retrieves metadata size and DAR info and returns
    '''
    mediainfo_cmd = [
        'mediainfo',
        '-f',
        '--Language=raw',
        '--Output=Video;%DisplayAspectRatio/String%',
        fullpath
    ]

    dar_setting = subprocess.check_output(mediainfo_cmd)
    dar_setting = dar_setting.decode('utf-8')

    if '4:3' in dar_setting:
        return '4:3'
    elif '16:9' in dar_setting:
        return '16:9'
    elif '5:4' in dar_setting:
        return '5:4'
    else:
        return 'No DAR'


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


def get_height(fullpath):
    '''
    Retrieves height information via mediainfo
    '''
    mediainfo_cmd = [
        'mediainfo',
        '--Output=Video;%Height%',
        fullpath
    ]

    height = subprocess.check_output(mediainfo_cmd)
    height = height.decode('utf-8')
    height = height.strip('\n')

    if '576' == str(height):
        return '576'
    elif '608' == height:
        return '608'
    elif '720' == height:
        return '720'
    elif '1 080' == height or '1080' == height:
        return '1080'
    else:
        return "There is no height data for this item"


def set_output_path(fullpath):
    f = os.path.basename(fullpath)
    filename, extension = os.path.splitext(f)
    return os.path.join(PATH, "{}_v210.mov".format(filename))


def set_move_path(fullpath):
    f = os.path.basename(fullpath)
    filename, extension = os.path.splitext(f)
    return os.path.join(DELIVERY_PATH, "{}_v210.mov".format(filename))


def create_ffmpeg_command(fullpath, height, dar, framerate):

    output_fullpath = set_output_path(fullpath)

    ffmpeg_program_call = [
        "ffmpeg"
    ]

    input_video_file = [
        "-i", fullpath
    ]

    map_command = [
        "-map", "0",
        "-movflags", "write_colr"
    ]

    colour_sd_pal = [
        "-color_primaries", "bt470bg",
        "-color_trc", "bt709",
        "-colorspace", "bt470bg",
        "-color_range", "1"
    ]

    colour_hd = [
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-color_range", "1"
    ]

    video_settings = [
        "-c:v", "v210",
        "-framerate", framerate,
        "-metadata:s:v:0", "'encoder=Uncompressed 10-bit 4:2:2'"
    ]

    audio_settings = [
        "-c:a", "copy"
    ]

    interlace_crop = [
        "-vf", "setfield=tff,crop=720:576:0:32,setdar=4/3"
    ]

    interlace_nocrop = [
        "-vf", "setfield=tff"
    ]

    interlace_setdar_4x3 = [
        "-vf", "setfield=tff,setdar=4/3"
    ]

    interlace_setdar_16x9 = [
        "-vf", "setfield=tff,setdar=16/9"
    ]

    mov_settings = [
        "-f", "mov",
        output_fullpath
    ]

    print("The output path will be: {}".format(output_fullpath))
    logger.info("The new FFmpeg mov file will be written to: %s", output_fullpath)

    if height == '576' and dar == '4:3':
        logger.info("%s file will be encoded using SD 4:3 settings", fullpath)
        return ffmpeg_program_call + input_video_file + map_command + colour_sd_pal + \
               video_settings + interlace_setdar_4x3 + audio_settings + mov_settings
    elif height == '608':
        logger.info("%s file will be encoded with interlacing only. Crop requested to be removed", fullpath)
        return ffmpeg_program_call + input_video_file + map_command + colour_sd_pal + \
               video_settings + interlace_nocrop + audio_settings + mov_settings
    elif height == '576' and dar == '16:9':
        logger.info("%s file will be encoded using SD 16:9 settings", fullpath)
        return ffmpeg_program_call + input_video_file + map_command + colour_sd_pal + \
               video_settings + interlace_setdar_16x9 + audio_settings + mov_settings
    elif height == '720' and dar == '16:9':
        logger.info("%s file will be encoded using HD 16:9 settings", fullpath)
        return ffmpeg_program_call + input_video_file + map_command + colour_hd + \
               video_settings + interlace_setdar_16x9 + audio_settings + mov_settings
    elif height == '1080' and dar == '16:9':
        logger.info("%s file will be encoded using HD 16:9 settings", fullpath)
        return ffmpeg_program_call + input_video_file + map_command + colour_hd + video_settings + \
               interlace_setdar_16x9 + audio_settings + mov_settings
    else:
        logger.warning("There is a problem with your height and dar data:\n%s %s", height, dar)
        return None


def conformance_check(file):
    '''
    Checks mediaconch policy against new MOV creation
    '''

    mediaconch_cmd = [
        'mediaconch', '--force',
        '-p', MOV_POLICY,
        file
    ]

    try:
        success = subprocess.check_output(mediaconch_cmd)
        success = success.decode('utf-8')
    except:
        success = ""
        logger.warning("Mediaconch policy retrieval failure for %s", file)

    if success.startswith('pass!'):
        logger.info("PASS: %s has passed the mediaconch policy", file)
        return "PASS!"
    elif success.startswith('fail!'):
        return "FAIL! This policy has failed {}".format(success)
        logger.warning("FAIL! The policy has failed for %s:\n %s", file, success)
    else:
        return "FAIL!"
        logger.warning("FAIL! The policy has failed for %s:\n%s", file, success)


def main():

    file_list = [x for x in os.listdir(PATH) if os.path.isfile(os.path.join(PATH, x))]
    for file in file_list:
        fullpath = os.path.join(PATH, file)
        print(fullpath)
        if fullpath.endswith(".mkv"):
            ffmpeg_call = []
            dar = get_dar(fullpath)
            print(f"** DAR: {dar}")
            height = get_height(fullpath)
            print(f"** Height: {height}")
            framerate = get_framerate(fullpath)
            print(f"** FPS: {framerate}")
            logger.info("Sending FFmpeg_call with %s, %s, %s and %s", fullpath, height, dar, framerate)
            ffmpeg_call = create_ffmpeg_command(fullpath, height, dar, framerate)
            ffmpeg_call_neat = (" ".join(ffmpeg_call), "\n")
            print("Transcoding with:", " ".join(ffmpeg_call), "\n")
            logger.info("FFmpeg call created: %s", ffmpeg_call_neat)
            try:
                subprocess.call(ffmpeg_call)
            except Exception:
                logger.critical("FFmpeg command failed: %s", ffmpeg_call)
                print("FFmpeg command failed")
            time.sleep(15)
            clean_up(fullpath)

        else:
            print("{} is not a Matroska file, skipping".format(fullpath))

    logger.info("================== END F47 ffv1 to v210 transcode END ==================")


def clean_up(fullpath):
    new_file = set_output_path(fullpath)
    logger.info("Clean up begins for %s", new_file)
    print("Clean up for {} begins now".format(new_file))
    if os.path.isfile(new_file):
        if new_file.endswith("_v210.mov"):
            print("Comparing {} to conformance policy:".format(new_file))
            logger.info("Conformance check: comparing %s with policy", new_file)
            result = conformance_check(new_file)
            if "PASS!" in result:
                print("{} passed the policy checker and it's Matroska can be deleted".format(new_file))
                try:
                    print("** Moving {} file to success/ folder".format(new_file))
                    new_file_path = set_move_path(fullpath)
                    shutil.move(new_file, new_file_path)
                    logger.info("Moving %s to success folder: %s", new_file, new_file_path)
                except Exception:
                    print("Unable to move {} to success folder".format(new_file))
                    logger.warning("Unable to move %s to success folder: %s", new_file, new_file_path)
                try:
                    print("** Attempting deletion of file {}".format(fullpath))
                    logger.info("*** DELETION: %s", fullpath)
                    os.remove(fullpath)
                except Exception:
                    print("Deletion of {} failed".format(fullpath))
                    logger.warning("Deletion failure: %s", fullpath)
            else:
                print("FAIL: {} failed the policy checker. Leaving Matroska for second encoding attempt".format(new_file))
        else:
            print("Skipping: {} the wrong file has been passed to clean_up()".format(new_file))
            logger.info("Skipping %s, as this file is not ended _v210.mov", new_file)
    else:
        print("{} is not a file... What is it?".format(new_file))
        logger.warning("NOT A FILE: %s what is this?", new_file)


if __name__ == "__main__":
    main()
