# Open source transcode scripts

The BFI National Archive have developed several workflows using excellent open source software FFmpeg, FFprobe, Mediainfo and Mediaconch to convert preservation files to lossless and lossy access files for distribution and editing in NLE software. The aim of these scripts are to batch convert collections of digitised files from within the BFI National Archive collection, or returned from external sources, for Heritage 2022 Video Tape and Film Digitisation projects.  

The transcoding scripts are written in Python3, and, excepting one instance, are launched from Bash Shell script using GNU Parallel which runs multiple versions of the Python script concurrently. These scripts are available under the MIT licence. If you wish to test these yourself please create a safe environment to use this code separate from preservation critical files. All comments and feedback welcome.  

## Overview and Dependencies

These scripts are run from Ubuntu 20.04LTS installed server and rely upon various Linux command line programmes. The scripts are not designed to be run from the command line, but via cron scheduling (see next section for more details). As a result there is no built in help command, so please refer to this README and the script comments for information about script functionality.  

Linux dependencies include: flock, rsync, grep, cat, echo, mmin, touch, find, and date. You can find out more about these by running the manual (man flock) or by calling the help page (flock --help).  

Open source softwares are used from Media Area and FFmpeg. Please follow the links below to find out more about installation and operation:  
MediaConch - https://mediaarea.net/mediaconch  
MediaInfo - https://mediaarea.net/mediainfo  
FFmpeg - http://ffmpeg.org/  
FFprobe - https://ffmpeg.org/ffprobe.html  

To run the concurrent processes the scripts use GNU Parallel which will require installation (with dependencies of it's own that may include the following):

    GNU parallel may also require: sysstat 12.2.0, libsensors 5-6.0, libsensors-config 3.6.0
    available here http://archive.ubuntu.com/ubuntu/pool/main/l/lm-sensors/libsensors-config_3.6.0-2ubuntu1_all.deb
    available here http://archive.ubuntu.com/ubuntu/pool/main/l/lm-sensors/libsensors5_3.6.0-2ubuntu1_amd64.deb
    available here http://archive.ubuntu.com/ubuntu/pool/main/s/sysstat/sysstat_12.2.0-2_amd64.deb
    available here http://archive.ubuntu.com/ubuntu/pool/universe/p/parallel/parallel_20161222-1.1_all.deb

## Supporting crontab actions

The transcoding scripts are launched via shell scripts, or the Python directly, from a server's /etc/crontab.  
Where a script is working on batches using multiple instances running concurrently it's possible to overburden the server and accidentally kill processes midway through. To prevent this the crontab calls the scripts via Linux Flock, /usr/bin/flock shown below. The lock files associated with each script are manually created and put in the /var/run folder. When one is active it blocks any other instances from launching, which allows for multiple crontab entries for a given script, see crontab example below. A script called flock_rebuild.sh (you can see an example of this in the dpx_encoding repository) regularly checks for missing lock files, and where absent recreates them. It is common for the lock files to disappear when a server is rebooted.  

The scripts for FFmpeg transcoding run frequently throughout the day:  
batch_transcode_ffv1_v210_start.sh  
A bash script creates file list from multiple paths, passes to GNU Parallel that launches multiple Python3 scripts  
batch_transcode_proresHD_mp4_start.sh  
A bash script creates file list and passes to GNU Parallel that launches multiple Python3 scripts  
f47_ffv1_v210_transcode.py  
Python 3 script that works through a folder of FFV1 mkv files, transcoding one a at a time until completed

Crontab example entries:

    0  9 * * * user /usr/bin/flock -w 0 --verbose /var/run/batch_transcode.lock /transcoding/batch_transcode_ffv1_v210_start.sh > /tmp/python_cron1.log 2&>1
    0 13 * * * user /usr/bin/flock -w 0 --verbose /var/run/batch_transcode.lock /transcoding/batch_transcode_ffv1_v210_start.sh > /tmp/python_cron1.log 2&>1
    0 11 * * * user /usr/bin/flock -w 0 --verbose /var/run/batch_prores.lock    /transcoding/batch_transcode_proresHD_mp4_start.sh > /tmp/python_cron2.log 2&>1
    0 15 * * * user /usr/bin/flock -w 0 --verbose /var/run/batch_prores.lock    /transcoding/batch_transcode_proresHD_mp4_start.sh > /tmp/python_cron2.log 2&>1
    0 18 * * * user                               /usr/bin/python3              /transcoding/f47_ffv1_v210_transcode.py > /tmp/python_cron3.log 2>&1
    
## Environmental variable storage

These scripts are being operated on each server under a specific user, who has environmental variables storing all path data for the script operations. These environmental variables are persistent so can be called indefinitely. When being called from crontab it's critical that the crontab user is set to the correct user with associated environmental variables.

--------------------
# Scripts

### batch_transcode_h22_ffv1_v210_start.sh
This bash shell script compiles a list of FFV1 matroska files, and launches concurrent Python scripts each with a different path name using GNU Parallel, four jobs at a time. It outputs the opening and closing statements to the same script log as the Python, so when reviewing the log it makes it clear that the Shell script ran to completion of the items on the list.

Script function:
1. Loads local variables from server environmental variables
2. Changes directory temporarily to launch Python script
3. Deletes and recreates the list of available Matroska files for processing
4. Runs a find search for all files named ending ".mkv" in transcode path 1 and 2, outputs to one list
5. Greps the list searching for '/mnt/' path opening, and passes the results one at a time to GNU Parallel
6. GNU parallel runs four concurrent jobs, passing a different FFV1 mkv path to Python script below

### batch_transcode_h22_ffv1_v210.py
This script convert FFV1 Matroska files to V210 mov files for Heritage 2022 partners who wish to have alternative preservation masters. This script uses open source softwares to automate the transcode and validate the finished V210 file. Transcoding software FFmpeg is used to convert the FFV1 mkv to V210 mov. The script retrieves FFV1 source metadata using open source software FFprobe and Mediainfo collecting colour primaries data, matrix coefficients and field order. This metadata is passed into the FFmpeg command to create the V210 mov. FFmpeg is further used to make framemd5 files testing that each frame is identical between the FFV1 and V210, and finally the V210 is checked against an open source MecdiaConch policy to ensure the file is valid.

Script function:
** THIS SCRIPT MUST BE LAUNCED BY SHELL SCRIPT TO POPULATE SYS.ARGV[1] **
1. Receives the FFV1 matroska path, and checks the path supplied conforms to file requirement, ie starts with 'N_' and is not from the 'mkv' folder path.
2. The script extracts the metadata of each file acquiring scan order and colour metadata
3. Populates FFmpeg subprocess command based on format decision from retrieved metadata
4. Transcodes new file into 'transcode/' folder named as {filename}.mov
5. Verifies V210 mov passes framemd5 manifest comparison and mediaconch policy
If passes both!
  - Moves V210 mov to success/ folder
  - Deletes FFV1 mkv that has successful MOV pass
If fails either!
  - Moves V210 mov to failures/ before deleting the mov asset
  - Leaves FFV1 mkv whose mov failed policy check for another transcode attempt next script run
  - Outputs fail reason to failure log (inc. mediaconch policy fail) kept in failed/ folder

### batch_transcode_proresHD_mp4_start.sh
This bash shell script compiles a list of HD ProRes mov files, and launches concurrent Python scripts each with a different path name using GNU Parallel, four jobs at a time. It outputs the opening and closing statements to the same script log as the Python, so when reviewing the log it makes it clear that the Shell script ran to completion of the items on the list.

Script function:
1. Loads local variables from server environmental variables
2. Deletes and recreates the list of available Matroska files for processing
3. Changes directory temporarily to launch Python script
4. Runs a find search (minimum modification time over 10 minutes) for all files named ending ".mov" in transcode path 1, 2 and 3, outputs to list
5. Greps the list searching for '/mnt/' path opening, and passes the results one at a time to GNU Parallel
6. GNU parallel runs three concurrent jobs, passing a different HD ProRes mov path to Python script below

### batch_transcode_proresHD_mp4.py
This script converts externally supplied HD ProRes mov files to H.264 MP4 files for distribution to partners via Frameio. This script uses open source software Mediaconch to validate the ProRes mov file before FFmpeg automates the transcode to an MP4 file. The ProRes mov is copied to a new preservation location using open source software rsync, and MD5 sums are generated for both ProRes mov files to check the copy is identical.

Script function:
** THIS SCRIPT MUST BE LAUNCED BY SHELL SCRIPT TO POPULATE SYS.ARGV[1] **
1. Receives the HD ProRes mov path, and checks the path supplied conforms to file requirement, ie ends ".mov"
2. Checks each ProRes mov file against MediaConch ProRes policy  
3. If it passes, initiates FFmpeg subprocess command and encodes with FFmpeg a mp4 file for frame.io viewing  
4. If it fails, writes mediaconch failure message to a failures log, moves ProRes to failures folder and the script exists to avoid the clean up stage for successful file transcodes only.
5. Transcode begins using FFmpeg subprocess call, creating H264 MP4 file  
6. MP4 compared to basic MP4 Mediaconch policy (is file whole)
7. If it passes, moves mp4 to mp4_completed/ folder. Copies ProRes from to new preservation location, before making md5sum checks of both files. If MD5 sums match the script deletes original ProRes mov. If MD5 sum does not match it repeats copy/MD5 sum validation. If fails again append failure log and exits script.
8. If it fails, deletes mp4 and leaves ProRes for repeat attempt

### f47_ffv1_v210_transcode.py
This script has been designed to help assist the Video and Audio Conservation Specialists at the BFI, by providing transcodes of preservation standard video files from FFV1 matroska to V210 mov, allowing editing in NLE software.  This script uses open source transcoding software FFmpeg to convert the FFV1 mkv to V210 mov, taking into account the need to trim certain files that have height dimensions of 608 (accommodating data streams embedded within the video during capture). The file’s metadata is assessed using Media Area’s MediaInfo and the finished V210 file is checked against a MediaConch conformance policy to ensure the file is valid before the original FFV1 mkv is deleted from the automation folder, leaving just the V210 version. As this script is infrequently needed it is run once a day and works through each file one at a time.

Script function:
1. Searches in specified path for files that end in “.mkv”
2. Checks metadata of each file against DAR and height. The script has been developed to handle SD 4:3, SD with 608 height, SD 16:9, 720 height 16:9 and 1080 height 16:9.
3. With DAR/height metadata, selects correct FFmpeg subprocess command combination
4. If a file has 608 height it is cropped and outputted to 576
5. Encodes with FFmpeg creating a V210 mov in same location as FFV1 mkv, appended {}_v210.mov
6. Verifies V210 mov passes basic Mediaconch policy
7. Moves V210 mov to success/ folder om FFV1_Matroska_conversion/ signalling the file is safe to remove and edit with
8. Deletes FFV1 mkv that has successful V210 mov
9. If the V210 mov fails the Mediaconch policy check the FFV1 mkv is left in place for a repeat transcoding attempt the next time the script runs.
