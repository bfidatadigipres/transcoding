#!/bin/bash

# Script to modify Pixel Aspect Ratio atom of MOV files.
#
# It operates on a watch folder, any MOV files that are placed in a folder are processed but only when the 'start file' is manually deleted.
# The design is such that because a large video file might take a while to be copied onto the QNAP it is best a user decides when this is
# ready & does so by deleting the 'start file'.
# Processed files are then moved into a subdirectory.
#
# movmetaedit needs to be installed and can be obtained from https://mediaarea.net/MOVMetaEdit e.g.:
#  wget https://mediaarea.net/download/binary/movmetaedit/17.10.1/movmetaedit_17.10.1-1_amd64.Debian_8.0.deb
#  dpkg -i movmetaedit_17.10.1-1_amd64.Debian_8.0.deb
#
# The appropriate mount point for the QNAP can be added into /etc/fstab, e.g.:
# QNAP Video Operations share NFS export
#
# Brian Fattorini - January 2019


# Pixel Aspect Ratio to apply
par='12:11'

# Standard location of 'movmetaedit'
mmeLocation='/usr/bin/movmetaedit'

# Where the Isilon PAR folder is mounted on this system (no trailing slash)
mountPoint="$QNAP_08"
echo "mountpoint is $mountPoint"

# Folder containing files to process (no trailing slash)
processFolder='TVOps/PAR-Corrections/convert-to_12-11'
processFolderLocation="${mountPoint}/${processFolder}"

# Folder name for completed conversions (no trailing slash)
completedFolder='COMPLETED'
destinationFolderLocation="${processFolderLocation}/${completedFolder}"

# The start file is what needs to be deleted before converstion can start
startFile='DELETE-THIS-FILE-TO-START.txt'
startFileLocation="${processFolderLocation}/${startFile}"

# Our short hostname
hostName=$(eval $(which hostname) -s)

# Name of this script
scriptName=$(eval $(which basename ) $0)
# Script name without extension (deletes shortest match of . from back of string)
scriptNameWithoutExtension=${scriptName%.*}
echo "$scriptNameWithoutExtension"
# PID directory e.g. '/run/'
pidDirectory='/usr'
pidFile='${pidDirectory}${scriptNameWithoutExtension}.pid'

# Log file for user. Always overwritten on new run.
userLog='conversion-details-log.txt'
userLogFileLocation='${destinationFolderLocation}/${userLog}'

# System log file, always overwritten on new run (no trailing slash on directory).
sysLog="${scriptNameWithoutExtension}.log"
echo "syslog: $sysLog"
sysLogLocation="/var/log/pixel-aspect-ratio-conversion/"
sysLogFileLocation="${sysLogLocation}/${sysLog}"
echo "$sysLogFileLocation"

message="\r\nPlace MOV video files to be converted to '${par}' pixel aspect ratio into this folder then delete this file to start. Conversion will commence within 5 minutes.\r\n\r\nQ. Do I really delete this file to start the PAR conversion process?\r\nA. Yes.\r\n\r\nQ. How does it work?\r\nA. A script located on '${hostName}' constantly monitors this folder, once you delete this file (${startFile}) the process can begin.\r\n\r\nQ. Why do it this way?\r\nA. Files can take time to arrive in this folder and we do not want to start processing a partially transferred file. The simplest way to ensure files are ready to process is by having the operator decide so.\r\n\r\nQ. If I delete this text file will it come back when I've finished?\r\nA. Yes, this file is automatically regenerated when a conversion process finishes. To protect against accidental deletion it is also automatically generated when this folder is empty & there are no files in it.\r\n\r\n"

################### - Program starts here - ###################

# Check all locations are correct before doing anything
errorFlag=0
if ! $(which mountpoint) -q "$mountPoint" ; then
  echo "ERROR: '${mountPoint}' is not a mountpoint, has the QNAP been correctly mounted on '${hostName}'?"
  errorFlag=1
fi
if [ ! -d $processFolderLocation ] ; then
  echo "ERROR: The folder '${processFolder}' does not exist on the QNAP in the location expected."
  errorFlag=1
fi
if [ ! -d $destinationFolderLocation ] ; then
  $(which mkdir) $destinationFolderLocation > /dev/null 2>&1
  if [ $? -ne 0 ] ; then
    echo "ERROR: The completed folder '${completedFolder}' does not exist in '${processFolderLocation}/' and in addition cannot be created."
    errorFlag=1
  fi
fi
if [ ! -d $sysLogLocation ] ; then
  $(which mkdir) $sysLogLocation > /dev/null 2>&1
  if [ $? -ne 0 ] ; then
    echo "ERROR: The logging folder '${sysLogLocation}/' does not exist and in addition cannot be created."
    errorFlag=1
  fi
fi
if [ ! -x $mmeLocation ] ; then
  echo "ERROR: 'movemetaedit' either cannot be found or is not executable on '${hostName}'. Perhaps it has not been installed or installed in the standard location '${mmeLocation}'."
  echo "       How to Install:"
  echo '       - go to https://mediaarea.net/MOVMetaEditr to determine the latest version'
  echo '       - download the Pixel Aspect Ratio editor tool, e.g. wget https://mediaarea.net/download/binary/movmetaedit/17.10.1/movmetaedit_17.10.1-1_amd64.Debian_8.0.deb'
  echo '       - install, e.g. dpkg -i movmetaedit_17.10.1-1_amd64.Debian_8.0.deb'
  errorFlag=1
fi
if [ "$errorFlag" -gt 0 ] ; then
  echo
  echo "Exiting with errors!"
  echo
  exit 1
fi


Main () {
  #numOfSourceMovies=$( $(which ls ) -1 $processFolderLocation | $(which grep ) -i '.mov$\|.mxf$' | $(which wc ) -l )
  numOfSourceMovies=$( $(which ls ) -1 $processFolderLocation | $(which grep ) -i '.mov$' | $(which wc ) -l )
  if [ "$numOfSourceMovies" -gt 0 ] ; then
    nowU="$(date --rfc-3339=seconds)"
    nowURefined=${nowU%+*}
    echo -e "$nowURefined  Script started.\r" > $userLogFileLocation
    moviesToConvert=($( $(which ls ) -1 $processFolderLocation | $(which grep ) -i '.mov$'))
    for movie in "${moviesToConvert[@]}"
    do
      movieFullLocation="${processFolderLocation}/${movie}"
      movieFullLocationDestination="${destinationFolderLocation}/${movie}"
      $mmeLocation --par $par $movieFullLocation > /dev/null 2>&1
      $(which mv ) -f $movieFullLocation $movieFullLocationDestination
      #$(which mv ) -f $movieFullLocation -t $destinationFolderLocation
      if [ ! -e $movieFullLocationDestination ] ; then
        sysLog "  ERROR: Unable to move video file to completed location (tried to move '${movieFullLocation}' to '${movieFullLocationDestination}' but failed)."
        sysLog "Script exiting with unrecoverable error!"
        userLog "  ERROR: Unable to move video file to completed location (tried to move '${movieFullLocation}' to '${movieFullLocationDestination}' but failed)."
        userLog "Script exiting with unrecoverable error!"
        exit 100
      fi
      sysLog "  '${movie}' processed."
      userLog "  '${movie}' processed."
    done
    sysLog "Script completed."
    userLog "Script completed."
  else
    sysLog "Script finished (no start file but there were also no movies to process)."
  fi

}


WriteStartFile () {
  # Rewrite start file if not there
  if [ ! -e $startFileLocation ] ; then
    echo -e $message > $startFileLocation
  fi
}


sysLog () {
  nowSys="$(date --rfc-3339=seconds)"
  nowSysRefined=${nowSys%+*}
  echo "$nowSysRefined  $1" >> $sysLogFileLocation
}

userLog () {
  nowUser="$(date --rfc-3339=seconds)"
  nowUserRefined=${nowUser%+*}
  echo -e "$nowUserRefined  $1\r" >> $userLogFileLocation
}


# Create a lockfile (pidFile) and output the PID to it. Set a trap to auto-delete the pidFile if the script terminates abnormally
if [ ! -e $pidFile ]; then
  trap "rm -f $pidFile; exit" INT TERM EXIT
  echo $$ > $pidFile
  nowS="$(date --rfc-3339=seconds)"
  nowSRefined=${nowS%+*}
  echo "$nowSRefined  Script '${scriptName}' started work in '${processFolderLocation}'." > $sysLogFileLocation
  # Only commence when the file 'startFile' is absent
  if [ ! -e $startFileLocation ] ; then
    Main
    WriteStartFile
  else
    sysLog "Script finished (start file is there so not ready to process)."
  fi
  rm $pidFile
  trap - INT TERM EXIT
else
  sysLog "Script is already running, see pid file located at '${pidFile}'"
  echo "Script is already running, see pid file located at '${pidFile}'"
fi

exit 0
