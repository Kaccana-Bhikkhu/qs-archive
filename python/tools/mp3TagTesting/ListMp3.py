"""List properties of all mp3 files in a given directory."""

from __future__ import annotations

import os,sys,argparse
from datetime import timedelta
from mutagen.mp3 import MP3

def TimeDeltaToStr(time: timedelta,decimal:bool = False) -> str:
    """Convert a timedelta object to the form [HH:]MM:SS or [HH:]MM:SS[.sss] if decimal is True."""

    seconds = int(time.total_seconds())

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    decimalPart = f"{0.000001* time.microseconds:f}".strip("0").rstrip(".") if decimal else ""

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}{decimalPart}"
    else:
        return f"{minutes}:{seconds:02d}{decimalPart}"

parser = argparse.ArgumentParser(description="List the properties of mp3 files in a given directory.")
parser.add_argument('directory',type=str,help="Directory to list mp3 files")

options = parser.parse_args(sys.argv[1:])

for fileName in sorted(os.listdir(options.directory)):
    path = os.path.join(options.directory,fileName)
    if fileName.endswith(".mp3"):
        file = MP3(os.path.join(options.directory,fileName))
        duration = timedelta(seconds=file.info.length)
        bitRate = f"{file.info.bitrate / 1000} kbps"
        print('\t'.join((fileName,TimeDeltaToStr(duration),bitRate)))