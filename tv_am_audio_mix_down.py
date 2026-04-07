"""
TV AM audio correction script
to separate stereo audio/clock
into two separate stereo pairs
with replicated L R from source L
and source R.

2026    
"""

import os
import sys
import shutil
import logging
import subprocess

STORAGE = os.environ.get("BP_NAS_VID")
TARGET = os.path.join(STORAGE, "automation/tvam_audio_fix")
LOG_PATH = os.environ.get("LOG_PATH")

# Setup logging
logger = logging.getLogger('tvam_audio_mix_down')
hdlr = logging.FileHandler(os.path.join(LOG_PATH, 'tvam_audio_mix_down.log'))
formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)


def command(input, output):
    """
    Create FFmpeg command
    to fix audio mapping
    """
    cmd = [
        "ffmpeg", "-i",
        input,
        "-filter_complex",
        "[0:a]pan=stereo|c0=c0|c1=c0[left];[0:a]pan=stereo|c0=c1|c1=c1[right]",
        "-map", "0:v", "-c:v", "copy",
        "-map", "[left]", "-c:a:0", "pcm_s24le",
        "-map", "[right]", "-c:a:1", "pcm_s24le",
        output
    ]
    
    try:
        logger.info("FFmpeg command: %s", " ".join(cmd))
        subprocess.run(cmd, shell=False, check=True)
        return True
    except subprocess.CalledProcessError as err:
        logger.warning(err)
        return False


def main():
    """
    Find files in target folder and process
    one after another. Do not delete source
    but add new version into subfolder.
    """

    files = [ x for x in os.listdir(TARGET) if os.path.isfile(os.path.join(TARGET, x)) ]
    if not files:
        sys.exit("No files found for transcoding.")
    
    logger.info("-------------- TV AM audio mix down START --------------")
    logger.info("Files identified for FFmpeg conversion: %s", ", ".join(files))
    
    for file in files:
        logger.info("** File being processed: %s", file)
        input = os.path.join(TARGET, file)
        output = os.path.join(TARGET, f"fixed_audio/{file}")
        logger.info("Calling FFmpeg with paths:\n%s\n%s", input, output)
        success = command(input, output)
        if success:
            logger.info("FFmpeg completed successfully. Moving source to completed/ path")
            shutil.move(input, os.path.join(TARGET, f"completed/{file}"))
        else:
            logger.warning("Manual help needed: Failed to complete FFmpeg command for file %s", file)


if __name__ == "__main__":
    main()