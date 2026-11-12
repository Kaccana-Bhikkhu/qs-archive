#!/usr/bin/env python3
"""List properties of all mp3 files in a given directory."""

from __future__ import annotations

import os,sys,argparse
from datetime import timedelta
import mutagen
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
import json
class CLIP(mutagen.id3.TextFrame):
    "List of clips"

mutagen.id3.Frames["CLIP"] = CLIP
EasyID3.RegisterTextKey("clips","CLIP")

class SPLT(mutagen.id3.TextFrame):
    "Dict describing how this clip was split"

mutagen.id3.Frames["SPLT"] = SPLT
EasyID3.RegisterTextKey("splitmethod","SPLT")

def TimeDeltaToStr(time: timedelta,digits:int = None) -> str:
    """Convert a timedelta object to the form [HH:]MM:SS or [HH:]MM:SS[.sss] if digits is given."""

    seconds = time.total_seconds()
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)

    seconds = abs(seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60

    if digits:
        secondStr = f"{seconds:02.{digits}f}"
    else:
        secondStr = f"{seconds:02d}"

    if hours:
        return f"{sign}{hours}:{minutes:02d}:{secondStr}"
    else:
        return f"{sign}{minutes}:{secondStr}"


def ToTimeDelta(time: timedelta|float|str) -> timedelta|None:
    "Convert various types to a timedelta object."

    if type(time) == timedelta:
        return time
    
    try:
        floatVal = float(time)
        return timedelta(seconds=floatVal)
    except (ValueError,TypeError):
        pass

    if not time:
        return None

    try:
        numbers = str.split(time,":")
        if len(numbers) == 2:
            return timedelta(minutes = int(numbers[0]),seconds = float(numbers[1]))
        elif len(numbers) == 3:
            return timedelta(hours = int(numbers[0]),minutes = int(numbers[1]),seconds = float(numbers[2]))
    except (ValueError,TypeError):
        pass
    
    raise ValueError(f"{repr(time)} cannot be converted to a time.")


def CheckDuration(filename: str,clips:str,duration:float|int) -> None:
    "Check whether the duration of clips matches duration"
    clips = json.loads(clips)
    clipDuration = timedelta()
    for clip in clips:
        if clip[2]:
            clipDuration += ToTimeDelta(clip[2]) - ToTimeDelta(clip[1])
        else:
            # print("Clips reaching then end of a file have an indeterminate duration.")
            return

    difference = duration - clipDuration
    if abs(difference) > timedelta(seconds=0.2):
        print(difference.total_seconds())
        print(f"   ### {filename}: mismatched duration: mp3 file duration: {TimeDeltaToStr(duration,1)}; clip duration: {TimeDeltaToStr(clipDuration,1)}; difference: {TimeDeltaToStr(difference,1)};")
    


parser = argparse.ArgumentParser(description="List the properties of mp3 files in a given directory.")
parser.add_argument('directory',type=str,help="Directory to list mp3 files")
parser.add_argument('--recursive','-R',action='store_true',help="Traverse directory recursively")
parser.add_argument('--verbose','-v',default=0,action='count',help='Increase verbosity')

options = parser.parse_args(sys.argv[1:])

treeIterator = os.walk(options.directory)
if not options.recursive:
    treeIterator = (next(treeIterator),)

for dirpath,dirnames,filenames in treeIterator:
    for filename in sorted(filenames):
        path = os.path.join(dirpath,filename)
        if filename.lower().endswith(".mp3"):
            # print(os.path.join(options.directory,fileName))
            mp3File = MP3(path)
            duration = timedelta(seconds=mp3File.info.length)
            bitRate = f"{mp3File.info.bitrate / 1000} kbps"

            try:
                id3Tags = EasyID3(path)
                clips = id3Tags.get("clips")
                splitMethod = id3Tags.get("splitmethod")
            except mutagen.id3.ID3NoHeaderError:
                clips = None
                splitMethod = None

            if options.verbose > 0:
                print('\t'.join((filename,TimeDeltaToStr(duration,1),bitRate,str(clips),str(splitMethod))))
            if clips:
                CheckDuration(filename,clips[0],duration)