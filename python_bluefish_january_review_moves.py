'''
Move items from moves.log
Back to their original position
following MKV 'BlueFish' fix
'''

import os
import sys

TRANSCODE_PTH = os.path.join(os.environ['QNAP_VID'], '/bluefish_january_review/transcoded/')
MOVES = os.path.join(os.environ['QNAP_VID'], '/bluefish_january_review/moves.log')

with open(MOVES, 'r') as data:
    lines = data.readlines()
targets = [ x for x in lines if 'BlueFish MKV found in Ingest path:' in str(x) ]

for item in targets:
    move_path = item.split(': ')[1].rstrip('\n')
    filename = os.path.basename(move_path)
    if '.mov' in filename:
        continue
    print(f"{os.path.join(TRANSCODE_PTH, filename)} to be moved to {move_path}")

    try:
        os.rename(os.path.join(TRANSCODE_PTH, filename), move_path)
    except FileNotFoundError:
        pass
