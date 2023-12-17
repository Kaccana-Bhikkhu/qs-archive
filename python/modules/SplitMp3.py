"""Use Mp3DirectCut.exe to split the session audio files into individual excerpts based on start and end times from Database.json"""

from __future__ import annotations

import os, json, platform
import Utils, Alert, Link, TagMp3, PrepareUpload
import Mp3DirectCut
from Mp3DirectCut import Clip, ClipTD
from typing import List, Union, NamedTuple
from datetime import timedelta

Mp3DirectCut.SetExecutable(Utils.PosixToWindows(Utils.PosixJoin('tools','Mp3DirectCut')))


def IncludeRedactedExcerpts() -> List[dict]:
    "Merge the redacted excerpts back into the main list in order to split mp3 files"
    
    allExcerpts = gDatabase["excerpts"] + gDatabase["excerptsRedacted"]
    allExcerpts = [x for x in allExcerpts if x["fileNumber"]] # Session excerpts don't need split mp3 files
    orderedEvents = list(gDatabase["event"].keys()) # Look up the event in this list to sort excerpts by event order in gDatabase
    
    allExcerpts.sort(key = lambda x: (orderedEvents.index(x["event"]),x["sessionNumber"],x["fileNumber"]))
        # Sort by event, then by session, then by file number
    
    return allExcerpts

def AddArguments(parser):
    "Add command-line arguments used by this module"
    parser.add_argument('--overwriteMp3',**Utils.STORE_TRUE,help="Overwrite existing mp3 files; otherwise leave existing files untouched")

def ParseArguments() -> None:
    pass

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main():
    """ Split the Q&A session mp3 files into individual excerpts.
    Read the beginning and end points from Database.json."""
    
    if platform.system() != "Windows":
        Alert.error(f"SplitMp3 requires Windows to run mp3DirectCut.exe. mp3 files cannot be split on {platform.system()}.")
        return

    eventSplitCount = 0
    errorCount = 0
    alreadySplit = 0
    for event,eventExcerpts in Utils.GroupByEvent(gDatabase["excerpts"]):        
        eventName = event["code"]
        if gOptions.events != "All" and eventName not in gOptions.events:
            continue

        excerptClipsDict:dict[str,list[Mp3DirectCut.Clip]] = {}
        sources = set()

        if gOptions.overwriteMp3:
            excerptsNeedingSplit = eventExcerpts
        else:
            excerptsNeedingSplit = [x for x in eventExcerpts if Link.LocalItemNeeded(x)]
        if not excerptsNeedingSplit:
            alreadySplit += 1
            continue # If no local excerpts are needed in this session, then no need to split mp3 files
        
        session = dict(sessionNumber=None)
        for excerpt in excerptsNeedingSplit:
            if session["sessionNumber"] != excerpt["sessionNumber"]:
                session = Utils.FindSession(gDatabase["sessions"],eventName,excerpt["sessionNumber"])

            filename = f"{Utils.ItemCode(excerpt)}.mp3"
            clips = list(excerpt["clips"])
            defaultSource = session["filename"]
            for index in range(len(clips)):
                source = clips[index].file
                if source == "$":
                    source = defaultSource
                elif index == 0:
                    defaultSource = clips[0].file
                clips[index] = clips[index]._replace(file=source)
                sources.add(source)

            excerptClipsDict[filename] = clips
        
        inputDir = Utils.PosixJoin(gOptions.sessionMp3Dir,eventName)
        outputDir = Utils.PosixJoin(gOptions.excerptMp3Dir,eventName)
        os.makedirs(outputDir,exist_ok=True)
        
        for source in sources:
            PrepareUpload.MoveItemToRegularLocation(gDatabase["audioSource"][source])

        # We use inputDir as scratch space for newly generated mp3 files.
        # So first clean up any files left over from previous runs.
        for filename in excerptClipsDict:
            scratchFilePath = Utils.PosixToWindows(Utils.PosixJoin(inputDir,filename))
            if os.path.exists(scratchFilePath):
                os.remove(scratchFilePath)
        
        # Next invoke Mp3DirectCut:
        try:
            Mp3DirectCut.MultiFileSplitJoin(excerptClipsDict,Utils.PosixToWindows(inputDir),Utils.PosixToWindows(outputDir))
        except Mp3DirectCut.ExecutableNotFound as err:
            Alert.error(err)
            Alert.status("Continuing to next module.")
            return
        except Mp3DirectCut.Mp3CutError as err:
            Alert.error(err)
            errorCount += 1
            Alert.status("Continuing to next event.")
            continue
        except (ValueError,OSError) as err:
            Alert.error(f"Error: {err} occured when processing session {session}")
            errorCount += 1
            Alert.status("Continuing to next event.")
            continue
        
        for excerpt in excerptsNeedingSplit:
            filename = f"{Utils.ItemCode(excerpt)}.mp3"
            filePath = Utils.PosixJoin(outputDir,filename)
            TagMp3.TagMp3WithClips(filePath,excerpt["clips"])
        
        eventSplitCount += 1
        Alert.info(f"{eventName}: Split {len(sources)} source files into {len(excerptClipsDict)} excerpt mp3 files.")
    
    Alert.status(f"   {eventSplitCount} events split; {errorCount} events had errors; all files already present for {alreadySplit} events.")