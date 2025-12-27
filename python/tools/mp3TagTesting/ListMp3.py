"""List properties of all mp3 files in a given directory."""

from __future__ import annotations

import os,sys,argparse
from datetime import timedelta
import mutagen
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

class CLIP(mutagen.id3.TextFrame):
    "List of clips"

mutagen.id3.Frames["CLIP"] = CLIP
EasyID3.RegisterTextKey("clips","CLIP")

class SPLT(mutagen.id3.TextFrame):
    "Dict describing how this clip was split"

mutagen.id3.Frames["SPLT"] = SPLT
EasyID3.RegisterTextKey("splitmethod","SPLT")

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
        print(os.path.join(options.directory,fileName))
        mp3File = MP3(os.path.join(options.directory,fileName))
        duration = timedelta(seconds=mp3File.info.length)
        bitRate = f"{mp3File.info.bitrate / 1000} kbps"

        id3Tags = EasyID3(os.path.join(options.directory,fileName))
        clips = str(id3Tags.get("clips"))
        splitMethod = str(id3Tags.get("splitmethod"))
        print('\t'.join((fileName,TimeDeltaToStr(duration),bitRate,clips,splitMethod)))