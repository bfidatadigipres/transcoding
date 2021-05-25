# Open source transcode scripts

The BFI National Archive have developed several workflows using excellent open source software FFmpeg, FFprobe, Mediainfo and Mediaconch to convert preservation files to lossless and lossy access files for distribution and editing in NLE software. The aim of these scripts are to batch convert collections of digitised files from within the BFI National Archive collection, or returned from external sources, for Heritage 2022 Video Tape and Film Digitisation projects.  

The transcoding scripts are written in Python3, and, excepting one instance, are launched from Bash Shell script using GNU Parallel which runs multiple versions of the Python script concurrently. These scripts are available under the MIT licence. If you wish to test these yourself please create a safe environment to use this code separate from preservation critical files. All comments and feedback welcome.  

## Overview and Dependencies

These scripts are run from Ubuntu 20.04LTS installed server and rely upon various Linux command line programmes. The scripts are not designed to be run from the command line, but via cron scheduling (see next section for more details). As a result there is no built in help command, so please refer to this README and the script comments for information about script functionality.  

Linux dependencies include: flock, md5sum, grep, cat, echo, ls, rm, touch, basename, dirname, find, and date. You can find out more about these by running the manual (man flock) or by calling the help page (flock --help).  

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
Where a script is working on batches using multiple instances running concurrently it's possible to overburden the server and accidentally killing processes midway through. To prevent this the crontab calls the scripts via Linux Flock, /usr/bin/flock shown below. The lock files associated with each script are manually created and put in the /var/run folder. When one is active it blocks any other instances from launching, which allows for multiple crontab entries for a given script, see crontab example below. A script called flock_rebuild.sh (you can see an example of this in the dpx_encoding repository) regularly checks for missing lock files, and where absent recreates them. It is common for the lock files to disappear when a server is rebooted.  

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
