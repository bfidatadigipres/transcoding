#!/usr/bin/env python3

'''
Memnon workflow for Video Ops D3 FFV1 MKV returns

1. Retrieve FFV1 MKVs from watch folder along with name matched XML
2. Run checks, if fail move to failure folder with human log:
    a. Create Hashlib MD5 and compare to MD5 in XML file
    b. Run FFmpeg check against FFV1 for flipped bits / CRC difference
    c. Validate file against MediaConch policy
    d. Possibly update PAR if needed (as per Bluefish metadata updating)
3. MKV files are moved into new Splitting script workflow in QNAP-08
   XML files are moved into ARRIVALS/xml_files/ folder

All files should be PAL 608 height, though a 608 mediaconch failure is
handled with a second MediaConch check for 576 height.

2025
'''

# Global packages
import os
import sys
import shutil
import logging
import subprocess
from datetime import datetime
import xmltodict

# Local packages
sys.path.append(os.environ['CODE'])
import utils

# Vars
LOG_PATH = os.environ['LOG_PATH']
ARRIVALS = os.path.join(os.environ['QNAP_08'], 'memnon_validation')
DEPARTURES = os.path.join(os.environ['QNAP_08'], 'memnon_processing/source/')
FAILURES = os.path.join(ARRIVALS, 'failures')
XML_FILES = os.path.join(ARRIVALS, 'xml_files')
VALIDATE608 = os.path.join(os.environ['QNAP08_POLICIES'], 'videoops_mediaconch_policy_mkv_608.xml')
VALIDATE576 = os.path.join(os.environ['QNAP08_POLICIES'], 'videoops_mediaconch_policy_mkv_576.xml')

# Logging
LOGGER = logging.getLogger('d3_memnon_validation')
HDLR = logging.FileHandler(os.path.join(LOG_PATH, 'd3_memnon_validation.log'))
FORMATTER = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
HDLR.setFormatter(FORMATTER)
LOGGER.addHandler(HDLR)
LOGGER.setLevel(logging.INFO)


def main():
    '''
    Iterate through files running checks against MKV files
    and moving to failure/processing folders as needed
    '''

    if not utils.check_control('power_off_all'):
        LOGGER.info('Script run prevented by downtime_control.json. Script exiting.')
        sys.exit('Script run prevented by downtime_control.json. Script exiting.')

    mkv_list = [ x for x in os.listdir(ARRIVALS) if x.endswith(('.mkv', '.MKV'))]
    if len(mkv_list) > 0:
        LOGGER.info("---------- D3 MEMNON VALIDATION START ------------------------------")
    for mkv in mkv_list:
        if not utils.check_control('power_off_all'):
            LOGGER.info('Script run prevented by downtime_control.json. Script exiting.')
            sys.exit('Script run prevented by downtime_control.json. Script exiting.')

        can_id = mkv.split('.')[0]
        xpath = os.path.join(ARRIVALS, f"{can_id}.xml")
        fpath = os.path.join(ARRIVALS, mkv)
        LOGGER.info("New file to process: %s", fpath)

        # Get file MD5
        LOGGER.info("Generating local MD5 and comparing to XML supplied checksum")
        local_hash = utils.create_md5_65536(fpath)
        LOGGER.info("Local MD5 created: %s", local_hash)
        xml_hash, duration = get_xml_hash(ARRIVALS, can_id)
        if duration:
            capture_duration_log(f"{can_id}.xml", duration)
        if xml_hash is None:
            LOGGER.warning("Failed to retrieve MD5 has from XML file for %s", mkv)
            shutil.move(fpath, FAILURES)
            shutil.move(xpath, FAILURES)
            error_log(mkv, f"{mkv} file had no supplier XML.")
            error_log(mkv, f"File MD5: {local_hash.lower()}")
            error_log(mkv, "XML supplied MD5: Not found")
            continue
        if local_hash.lower() != xml_hash.lower():
            LOGGER.warning("Moving MKV %s to failures path. Checksums do not match:\n%s\n%s", mkv, hash, xml_hash)
            shutil.move(fpath, FAILURES)
            shutil.move(xpath, FAILURES)
            error_log(mkv, f"{mkv} file failed MD5 Checksum tests:")
            error_log(mkv, f"File MD5: {local_hash.lower()}")
            error_log(mkv, f"XML supplied MD5: {xml_hash.lower()}")
            continue
        LOGGER.info("MKV %s passed MD5 checksum comparison:\n%s\n%s", mkv, local_hash.lower(), xml_hash.lower())

        # Run FFV1 report and see if CRC match
        LOGGER.info("Start FFmpeg report for FFV1 CRC checksum health")
        ffmpeg_report = scan_ffv1_codec(fpath)
        if 'slice CRC mismatch' in str(ffmpeg_report):
            LOGGER.warning("Moving MKV %s to failures path. CRC checksum mismatch in MKV file. See local error log for timestamps", mkv)
            error_log(mkv, f"FFV1 report revealed Slice CRC checksum mismatches for file {mkv}:")
            mismatches = get_crc_mismatch(ffmpeg_report)
            for mis in mismatches:
                error_log(mkv, f"CRC mismatch: {mis}")
            # Move to failures
            shutil.move(fpath, FAILURES)
            shutil.move(xpath, FAILURES)
            continue
        LOGGER.info("MKV %s passed Slice CRC checks", mkv)

        # Mediaconch checking
        LOGGER.info("Comparing file to 608 OFCOM MediaConch Policy")
        confirm608 = utils.get_mediaconch(fpath, VALIDATE608)
        if not confirm608:
            LOGGER.warning("MKV %s failed 608 policy: \n%s", mkv, confirm608)
            LOGGER.info("Comparing file to 576 OFCOM MediaConch Policy")
            confirm576 = utils.get_mediaconch(fpath, VALIDATE576)
            if not confirm576:
                LOGGER.warning("MKV %s failed 576 policy:\n%s", mkv, confirm576)
                LOGGER.warning("Moving MKV %s to failures path.", mkv)
                shutil.move(fpath, FAILURES)
                shutil.move(xpath, FAILURES)
                error_log(mkv, f"Mediaconch failure for 608 policy:\n{confirm608}")
                error_log(mkv, f"Mediaconch failure for 608 policy:\n{confirm576}")
                continue
        LOGGER.info("MKV %s passed Mediaconch checks", mkv)

        LOGGER.info("Moving MKV %s into Memnon splitting path: %s", mkv, DEPARTURES)
        shutil.move(fpath, os.path.join(DEPARTURES, mkv))
        shutil.move(xpath, os.path.join(XML_FILES, f"{can_id}.xml"))

    LOGGER.info("---------- D3 MEMNON VALIDATION END --------------------------------")


def get_xml_hash(fpath, fname):
    '''
    Split filepath, and retrieve XML hash
    data from file
    '''
    checksum = check_type = duration = ''

    xml_path = os.path.join(fpath, f"{fname}.xml")
    if not os.path.exists(xml_path):
        return None, None
    with open(xml_path, 'r', encoding='utf-8') as data:
        _data = data.read()
    if not _data:
        return None, None

    xml_data = xmltodict.parse(_data)
    print(xml_data)
    try:
        get_files = xml_data['Root']['Carrier']['Parts']['Part']['Files']['File']
        print(get_files)
    except (KeyError, IndexError, TypeError) as err:
        print(err)
        return None, None

    if isinstance(get_files, list):
        for file_dict in get_files:
            if f"{fname}.mkv" in file_dict.get('FileName'):
                checksum = file_dict.get('CheckSum').get('#text')
                check_type = file_dict.get('CheckSum').get('@Type')
                duration = file_dict.get('Duration')
                if len(checksum) != 32:
                    return None, None
    else:
        if f"{fname}.mkv" in str(get_files):
            try:
                checksum = get_files.get('CheckSum').get('#text')
                check_type = get_files.get('CheckSum').get('@Type')
                duration = get_files.get('Duration')
            except Exception as err:
                print(err)
    if str(check_type) == 'MD5':
        return checksum, duration


def scan_ffv1_codec(fpath):
    '''
    Run FFmpeg report on fpath
    Return any responses for errors
    (turned off -report, to avoid generating log)
    '''
    cmd = [
        'ffmpeg',
        '-i', fpath,
        '-f', 'null', '-'
    ]
    try:
        ffmpeg_report = subprocess.run(cmd, shell=False, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as err:
        print(err)
        return None

    return ffmpeg_report


def get_crc_mismatch(ffmpeg_report):
    '''
    Extract timings for CRC mismatches
    '''
    if not isinstance(ffmpeg_report, list):
        ffmpeg_report = ffmpeg_report.splitlines()

    time_mismatches = []
    for line in ffmpeg_report:
        if 'slice CRC mismatch' in line:
            split_line = line.split("!at ")[-1]
            mismatch = split_line.split(' sec')[0]
            time_mismatches.append(mismatch)
    return time_mismatches


def capture_duration_log(fname, duration):
    '''
    Write XML filename and duration to log
    '''
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fpath = os.path.join(XML_FILES, f"XML_durations.log")

    with open(fpath, 'a') as log:
        log.write(f"{ts} - {fname} - {duration}\n")


def error_log(fname, message):
    '''
    If needed, write error log
    where validation failure occurs
    '''
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fpath = os.path.join(FAILURES, f"{fname}_error.log")

    with open(fpath, 'w+') as log:
        log.write(f"Error {ts}: {message}.\n\n")


if __name__ == '__main__':
    main()
