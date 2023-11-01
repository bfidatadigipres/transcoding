#!/usr/bin/env /usr/local/bin/python3

'''
** MODULE FOR ALL SCRIPTS, RECEIVES FILE PATH RETURNS CHECKSUM **
Actions of the script:
1. Checks the path input is legitimate, then stores sys.argv[1] as variable 'filepath'.
2. Passes the filepath to the md5_65536() function.
    md5(file) chunk size 65536 (found to be fastest):
    i. Opens the input file in read only bytes.
    ii. Splits the file into chunks, iterates through 4096 bytes at a time.
    iii. Returns the MD5 checksum, formatted hexdigest / Returns None if exception raised
4. The MD5 checksum is passed back to the calling script

Joanna White 2023
Python 3
'''

import os
import sys
import hashlib
import tenacity


def md5_65536(file):
    '''
    Hashlib md5 generation, return as 32 character hexdigest
    '''
    try:
        hash_md5 = hashlib.md5()
        with open(file, "rb") as fname:
            for chunk in iter(lambda: fname.read(65536), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    except Exception:
        return None


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def make_output_md5(filepath):
    '''
    Runs checksum generation/output to file as separate function allowing for easier retries
    '''
    try:
        md5_checksum = md5_65536(filepath)
        return md5_checksum
    except Exception as err:
        print(err)
        return None


def make_checksum(filepath):
    '''
    Argument passed from calling script
    Decorator for function ensures retries if Exceptions raised
    '''
    if not filepath:
        print("No argument passed")
        return None

    if not os.path.isfile(filepath):
        print("Supplied file path is not a file.")
        return None

    checksum = make_output_md5(filepath)
    return checksum


if __name__ == "__main__":
    make_checksum(sys.argv[1])
