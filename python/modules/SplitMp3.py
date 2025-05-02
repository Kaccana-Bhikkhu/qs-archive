"""Use Mp3DirectCut.exe to split the session audio files into individual excerpts based on start and end times from Database.json"""

from __future__ import annotations

import os
import subprocess
import Database
import Utils, Alert, Link, TagMp3, PrepareUpload
import Mp3DirectCut
from Mp3DirectCut import Clip, ClipTD
from typing import List, Union, NamedTuple
from datetime import timedelta

Mp3DirectCut.SetExecutable(Utils.PosixToNative(Utils.PosixJoin('tools','Mp3DirectCut')))

def NativeFilePaths(clipsDict: dict[str,list[Clip]]) -> dict[str,list[Clip]]:
    """Convert the clip file names to native file paths."""

    returnValue:dict[str,list[Clip]] = {}
    for outputFile,clipList in clipsDict.items():
        newClipList = [c._replace(file=Utils.PosixToNative(c.file)) for c in clipList]
        returnValue[outputFile] = newClipList
    return returnValue

def AddArguments(parser):
    "Add command-line arguments used by this module"
    parser.add_argument('--overwriteMp3',**Utils.STORE_TRUE,help="Overwrite existing excerpt mp3 files; otherwise leave existing files untouched")
    parser.add_argument('--redoJoinMp3',**Utils.STORE_TRUE,help="Overwrite mp3 files for excerpts that join clips together")
    parser.add_argument('--joinUsingPydub',**Utils.STORE_TRUE,help="Use pydub to smoothly join audio clips (requires pydub and ffmpeg)")

def ParseArguments() -> None:
    pass

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main():
    """ Split the Q&A session mp3 files into individual excerpts.
    Read the beginning and end points from Database.json."""
    
    try:
        Mp3DirectCut.ConfigureMp3DirectCut()
    except Mp3DirectCut.ExecutableNotFound as error:
        processError = subprocess.call(f"{Mp3DirectCut.mp3spltCommand} -h",shell=True,stdout=subprocess.DEVNULL)
        if processError:
            Alert.error(f"Mp3DirectCut returns error {error}. Cannot find command {Mp3DirectCut.mp3spltCommand}. Mp3 files cannot be split.")
            return
        else:        
            Alert.notice(f"Cannot find Mp3DirectCut executable. Will use {Mp3DirectCut.mp3spltCommand}.")
    
    Mp3DirectCut.joinUsingPydub = gOptions.joinUsingPydub

    # Step 1: Determine which excerpt mp3 files need to be created
    eventExcerptClipsDict:dict[str,dict[str,list[Mp3DirectCut.Clip]]] = {}
        # eventExcerptClipsDict[eventName][filename] is the list of clips to join to create
        # excerpt file filename
    excerptsByFilename:dict[str,dict] = {}
        # Store each excerpt by filename for future reference
    for event,eventExcerpts in Database.GroupByEvent(gDatabase["excerpts"]):        
        eventName = event["code"]
        if gOptions.events != "All" and eventName not in gOptions.events:
            continue

        excerptClipsDict:dict[str,list[Mp3DirectCut.Clip]] = {}

        if gOptions.overwriteMp3:
            excerptsNeedingSplit = eventExcerpts
        else:
            excerptsNeedingSplit = [x for x in eventExcerpts if (gOptions.redoJoinMp3 and len(x.get("clips",())) > 1) or Link.LocalItemNeeded(x)]
        if not excerptsNeedingSplit:
            continue
        
        session = dict(sessionNumber=None)
        for excerpt in excerptsNeedingSplit:
            if session["sessionNumber"] != excerpt["sessionNumber"]:
                session = Database.FindSession(gDatabase["sessions"],eventName,excerpt["sessionNumber"])

            filename = f"{Database.ItemCode(excerpt)}.mp3"
            clips = list(excerpt["clips"])
            allFilesFound = True
            for index in range(len(clips)):
                sourceFile = clips[index].file
                if sourceFile == "$":
                    sourceFile = session["filename"]
                source = gDatabase["audioSource"].get(sourceFile,None)
                if source:
                    clips[index] = clips[index]._replace(file=Link.URL(source,"local"))
                else:
                    Alert.error(f"Cannot find source file '{sourceFile}' for",excerpt,". Will not split this excerpt.")
                    allFilesFound = False
            
            if allFilesFound:
                excerptClipsDict[filename] = clips
                excerptsByFilename[filename] = excerpt
    
        eventExcerptClipsDict[eventName] = excerptClipsDict
    
    if not eventExcerptClipsDict:
        Alert.status("No excerpt files need to be split.")
        return
    
    allSources = [gDatabase["audioSource"][os.path.split(source)[1]] for source in Mp3DirectCut.SourceFiles(eventExcerptClipsDict)]
    totalExcerpts = sum(len(xList) for xList in eventExcerptClipsDict.values())
    Alert.extra(totalExcerpts,"excerpt(s) in",len(eventExcerptClipsDict),"event(s) need to be split from",len(allSources),"source file(s).")
    
    # Step 2: Download any needed audio sources
    def DownloadItem(item: dict) -> None:
        Link.DownloadItem(item,scanRemoteMirrors=False)

    with Utils.ConditionalThreader() as pool:
        for sourceFile in allSources:
            pool.submit(DownloadItem,sourceFile)

    splitCount = 0
    errorCount = 0
    # Step 3: Loop over all events and split mp3 files
    for eventName,excerptClipsDict in eventExcerptClipsDict.items():
        outputDir = Utils.PosixJoin(gOptions.excerptMp3Dir,eventName)
        os.makedirs(outputDir,exist_ok=True)

        # Group clips by sources and call MultiFileSplitJoin multiple times.
        # If there is an error, this lets us continue to split the remaining files.
        for sources,clipsDict in Mp3DirectCut.GroupBySourceFiles(excerptClipsDict):
            # Invoke Mp3DirectCut on each group of clips:
            try:
                nativeClipsDict = NativeFilePaths(clipsDict)
                Mp3DirectCut.MultiFileSplitJoin(nativeClipsDict,outputDir=Utils.PosixToNative(outputDir))
            except Mp3DirectCut.ExecutableNotFound as err:
                Alert.error(err)
                Alert.status("Continuing to next module.")
                return
            except (Mp3DirectCut.Mp3CutError,ValueError,OSError) as err:
                Alert.error(f"{eventName}: {err} occured when splitting source files {sources}.")
                Alert.status("Continuing to next source file(s).")
                errorCount += 1
                continue
            
            for filename in clipsDict:
                filePath = Utils.PosixJoin(outputDir,filename)
                TagMp3.TagMp3WithClips(filePath,excerptsByFilename[filename]["clips"])
            
            splitCount += 1
            sources = set(os.path.split(source)[1] for source in sources)
            Alert.info(f"{eventName}: Split {sources} into {len(clipsDict)} files.")
    
    Alert.status(f"   {splitCount} source file groups split; {errorCount} source file groups had errors.")