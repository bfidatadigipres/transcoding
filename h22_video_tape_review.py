#!/usr/bin/env LANG=en_UK.UTF-8 /usr/local/bin/python3

'''
H22 video tape review script

First step is to clean up reviewed items:
1. Look through all subfolders in review for review_completed.txt file.
   Where found move all contained MOV files to the originals folder for
   scheduled bash script deletion.
2. Remove empty folder after deleting the review_completed.txt file.
3. If a folder containing review_completed.txt isn’t completely empty
   after the MOV files have been moved out, then the folder is moved
   into a completed_to_delete folder for manual assessment.

Second step is to look for new files that need sorting:
1. Script looks in auto_review folder for all files ending .mov and and split
   the file name from the extension, using the filename to make CID queries.
2. Look in CID items database using the filename in a current_location.name search,
   retrieve first original video format type (eg 1-inch, Umatic, Digital Betacam).
3. Convert the video_format variable into a folder name
4. Look in CID packages database using the filename in a name search, and
   retrieve the fields called part_of, which contains the supplier name.
5. Match the supplier name to one of five supplier paths and return to the
   script to allow the correct path to be constructed.
6. If format type and supplier name present, create new directory and add
   'review_underway.txt' and move MOV in. If folder already exists then move MOV
   file straight in. Iteration continues until all MOV files are processed
7. If a file is found that has no CID returns, then it's moved into
   CID_item_not_found folder.
8. All processes outputted to human readable log file located in review/ folder.

Joanna White 2021
'''

# Global pacakages
import os
import sys
import shutil
import logging
import datetime

# Local packages
import adlib

# Global vars
TRANSCODE = os.environ['GRACKH22_TRANSCODE']
REVIEW_PATH = os.path.join(TRANSCODE, 'review')
AUTO_REVIEW = os.path.join(TRANSCODE, 'auto_review')
CID_NOT_FOUND = os.path.join(REVIEW_PATH, 'CID_item_not_found')
ORIGINALS_PATH = os.path.join(TRANSCODE, 'original')
COMPLETED_PATH = os.path.join(REVIEW_PATH, 'completed_to_delete')
LOG_PATH = os.environ['LOG_PATH']
PATHS = ['DC1', 'INN', 'LMH', 'MX1', 'VDM']
LOCAL_LOG = os.path.join(REVIEW_PATH, 'H22_video_tape_review.log')
TODAY = str(datetime.datetime.now())
TODAY_DATE = TODAY[:10]
TODAY_TIME = TODAY[11:19]

# Setup logging
LOGGER = logging.getLogger('H22_video_tape_review')
HDLR = logging.FileHandler(os.path.join(LOG_PATH, 'H22_video_tape_review.log'))
FORMATTER = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
HDLR.setFormatter(FORMATTER)
LOGGER.addHandler(HDLR)
LOGGER.setLevel(logging.INFO)

# CID URL details
CID = adlib.Database(os.environ['CID_API'])
CUR = adlib.Cursor(CID)


def cid_check():
    '''
    Check CID online or exit
    '''
    try:
        LOGGER.info('* Initialising CID session... Script will exit if CID off line')
        cur = adlib.Cursor(CID)
        LOGGER.info("* CID online, script will proceed")
    except Exception:
        print("* Cannot establish CID session, exiting script")
        LOGGER.exception('Cannot establish CID session, exiting script')
        sys.exit()


def remove_reviewed():
    '''
    Checks for 'review_completed.txt' files
    Where present deletes txt file and moves .mov files to
    Originals path, before deleting video_type folder
    '''
    local_logger(f"\n---------- Assessing review path for completed reviews ---------- {TODAY_DATE} {TODAY_TIME}")
    for path in PATHS:
        review_path = os.path.join(REVIEW_PATH, path)
        directories = os.listdir(review_path)
        # Iterate through video format folders
        for d in directories:
            item_path = os.path.join(review_path, d)
            items = os.listdir(item_path)
            LOGGER.info("%s items found in %s", len(items), item_path)
            local_logger(f"MOV files found: {len(items)} in {item_path}")
            if 'review_completed.txt' in str(items).lower():
                local_logger(f"FOUND: review_completed.txt at path {item_path}")
                LOGGER.info("Completed review folder found")
                for i in items:
                    filepath = os.path.join(item_path, i)
                    LOGGER.info("Moving all contents to %s", ORIGINALS_PATH)
                    if i.endswith('completed.txt'):
                        LOGGER.info("Deleting: %s", filepath)
                        try:
                            os.remove(filepath)
                        except OSError:
                            LOGGER.warning("Unable to delete %s", filepath)
                    if i.endswith('.mov'):
                        local_logger(f"Moving file to originals/ for deletion: {i}")
                        LOGGER.info("Move: %s to %s", filepath, ORIGINALS_PATH)
                        shutil.move(filepath, ORIGINALS_PATH)
            else:
                local_logger(f"Skipping, no completed reviews for path {item_path}")
                LOGGER.info("No completed review text file found in folder %s", item_path)
                continue

            # Check all items removed then delete video format folder
            items_check = os.listdir(item_path)
            if len(items_check) == 0:
                local_logger(f"Deleting format folder: All files moved from {item_path}\n")
                LOGGER.info("%s empty. Deleting folder", item_path)
                try:
                    os.rmdir(item_path)
                except OSError:
                    LOGGER.warning(f"Unable to delete folder {item_path} - NOT EMPTY!")
            else:
                # Other file still remains in folder, move to completed_to_delete folder
                LOGGER.info("NOT DELETING: %s Folder has content remaining after MOV and TXT files removed", item_path)
                local_logger(f"{item_path}: NOT EMPTY! Moving to completed_to_delete folder for manual clean up")
                shutil.move(item_path, COMPLETED_PATH)


def main():
    '''
    Identify and move completed folder, placing MOV files in originals path
    Iterate automated_review folder for .mov files that need review
    Checks in CID for format type and supplier data
    Creates folder (if not existing) and 'review_underway.txt' and
    moves text file and MOV into folder
    '''
    cid_check()
    LOGGER.info("============== H22 VIDEO TAPE REVIEW START =============")
    LOGGER.info("Checking for format folders that have been reviewed")
    remove_reviewed()

    files = os.listdir(AUTO_REVIEW)
    for file in files:
        filepath = os.path.join(AUTO_REVIEW, file)
        fname = os.path.splitext(file)
        local_logger(f"\n----------- New file found for review: {file} ----------- {TODAY_DATE} {TODAY_TIME}")

        # Launch CID query to retrieve video format type
        video_type = get_video_type(fname[0])
        if video_type:
            format_folder = convert_folder(video_type)
            local_logger(f"Video type retrieved from CID: {format_folder}")
        else:
            format_folder = False
            local_logger(f"WARNING: No Video format retrieved from CID for {file}")

        # Launch CID query to retrieve supplier name
        supplier = get_supplier(fname[0])
        if supplier:
            supplier_folder = match_supplier(supplier)
            local_logger(f"Supplier name retrieved from CID: {supplier_folder}")
        else:
            supplier_folder = False
            local_logger(f"WARNING: No supplier name retrieved from CID for {file}")

        # Check folder path with new components exists
        if (format_folder and supplier_folder):
            move_folder = os.path.join(REVIEW_PATH, supplier_folder, format_folder)
            if os.path.exists(move_folder):
                # Move file straight in no issues
                LOGGER.info("Format folder exists for supplier. Moving %s straight to %s", filepath, move_folder)
                shutil.move(filepath, move_folder)
                logger_local(f"Moving {file} from {filepath} to new review path {move_folder}")
            else:
                # Folder doesn't exist, mkdir, make txt file and move
                LOGGER.info("New folder being created: %s", move_folder)
                os.mkdir(move_folder)
                local_logger(f"New folder created for path {move_folder}")
                text_path = os.path.join(move_folder, 'review_underway.txt')
                LOGGER.info("Creating new text file for new folder creation: %s", text_path)
                make_text_file(text_path)
                local_logger(f"New text file created for new review path {text_path}")
                if os.path.exists(text_path):
                    LOGGER.info("Moving %s to new path: %s", filepath, move_folder)
                    shutil.move(filepath, move_folder)
                    local_logger(f"Moving {file} from {filepath} to new review path {move_folder}")
                else:
                    LOGGER.warning("%s: Creation of text file in new folder failed. Leaving to retry later.", file)
        else:
            local_logger(f"Format folder {format_folder} or Supplier folder {supplier_folder} unobtainable.")
            local_logger(f"Moving file {file} to folder CID_item_not_found/ in review path")
            shutil_move(filepath, CID_NOT_FOUND)

    LOGGER.info("============== H22 VIDEO TAPE REVIEW END =============")


def get_video_type(fname):
    '''
    Retrieve video type from CID
    '''
    search = f"parts_reference->current_location.name='{fname}'"

    query = {'database': 'items',
             'search': search,
             'limit': '1',
             'output': 'json',
             'fields': 'video_format'}
    try:
        query_result = CID.get(query)
        LOGGER.info("Making CID query request with:\n %s", query)
    except (KeyError, IndexError):
        LOGGER.exception("get_video_type(): Unable to retrieve data for %s", fname)
        query_result = None
    try:
        video_fmt = query_result.records[0]['video_format'][0]
        return video_fmt
    except (KeyError, IndexError):
        video_fmt = ""
        LOGGER.warning("get_video_type(): Unable to access video_format")
        return False


def convert_folder(name_str):
    '''
    Make video_fmt into safe folder name
    '''
    name_str = str(name_str).lower()
    name_str_split = name_str.split(',')
    format = str(name_str_split[2])
    print(format)
    format = format.rstrip("]}'")
    format = format.lstrip(" '")
    path_str = format.replace(" ", "_")
    path_str = path_str.replace(".", "_")
    path_str = path_str.replace("-", "_")
    return path_str


def get_supplier(fname):
    '''
    CID query to retrieve current_location.name data
    Currently unavailable to the CID API
    '''
    search = f"name='{fname}'"

    query = {'database': 'packages',
             'search': search,
             'limit': '1',
             'output': 'json',
             'fields': 'part_of'}
    try:
        query_result = CID.get(query)
        LOGGER.info("Making CID query request with:\n %s", query)
    except (KeyError, IndexError):
        LOGGER.exception("get_supplier(): Unable to retrieve data for %s", fname)
        query_result = None
    try:
        supplier = query_result.records[0]['Currentlocation'][0]['part_of'][0]
        return supplier
    except (KeyError, IndexError):
        supplier = ""
        LOGGER.warning("get_supplier(): Unable to access supplier")
        return False


def match_supplier(supplier):
    '''
    Take supplier name and return correct path
    VDMS, INN-ARCHIVE, DC1, MX1, LMH
    '''
    if 'VDMS' in str(supplier).upper():
        return 'VDM'
    elif 'INN' in str(supplier).upper():
        return 'INN'
    elif 'DC1' in str(supplier).upper():
        return 'DC1'
    elif 'LMH' in str(supplier).upper():
        return 'LMH'
    elif 'MX1' in str(supplier).upper():
        return 'MX1'
    else:
        return 'UNKNOWN_SUPPLIER'


def make_text_file(path):
    '''
    Create text file 'review_underway.txt'
    '''
    message = '''
Automated file creation for H22 video tape review.\n
When the video files in this folder have been reviewed
please update this text file's name from:\n
'review_underway.txt' to 'review_completed.txt'\n\nThank you.
              '''

    with open(path, 'w') as file:
        file.write(message)


def local_logger(data):
    '''
    Pretty printed log for human readable data
    Output local log data for H22 video tape teams to monitor review movements
    '''
    if len(data) > 0:
        with open(LOCAL_LOG, 'a+') as log:
            log.write(f"{data} \n")
            log.close()


if __name__ == '__main__':
    main()
