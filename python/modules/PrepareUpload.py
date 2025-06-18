"""Move unlinked files into xxxNoUpload directories in preparation for uploading the website.
"""

from __future__ import annotations

import os, re
import Utils, Alert, Link
from typing import Iterable

def MoveItemsIfNeeded(items: Iterable[dict]) -> tuple[int,int,int]:
    """Move items to/from the xxxNoUpload directories as needed. 
    Return a tuple of counts: (moved to regular location,moved to NoUpload directory,other files moved to NoUpload directory)."""
    movedToDir = movedToNoUpload = otherFilesMoved = 0
    neededFiles = set()
    itemType = None
    for item in items:
        itemType = Link.AutoType(item)
        localPath = Link.URL(item,mirror="local")
        noUploadPath = Link.NoUploadPath(item)
        mirror = item.get("mirror","")
        if not localPath or not noUploadPath or not mirror:
            continue
        
        fileNeeded = mirror in ("local",gOptions.uploadMirror)
        if fileNeeded:
            neededFiles.add(localPath)
        if Utils.SwitchedMoveFile(noUploadPath,localPath,fileNeeded):
            if fileNeeded:
                movedToDir += 1
            else:
                movedToNoUpload += 1
    
    if not itemType: # In case items is empty
        return 0,0,0
    # Move files aren't in items into the NoUpload directory as well.
    itemDir = Link.URL(itemType,"local")
    noUploadDir = Link.NoUploadPath(itemType)
    for root,_,files in os.walk(itemDir):
        for file in files:
            path = Utils.PosixJoin(root,file)
            if path not in neededFiles:
                Utils.MoveFile(path,path.replace(itemDir,noUploadDir))
                otherFilesMoved += 1

    Utils.RemoveEmptyFolders(itemDir)
    Utils.RemoveEmptyFolders(noUploadDir)

    return movedToDir,movedToNoUpload,otherFilesMoved

def MoveItemsIn(items: list[dict]|dict[dict],name: str) -> None:
    
    movedToDir,movedToNoUpload,otherFilesMoved = MoveItemsIfNeeded(Utils.Contents(items))
    if movedToDir or movedToNoUpload or otherFilesMoved:
        Alert.extra(f"Moved {movedToDir} {name}(s) to usual directory; moved {movedToNoUpload} {name}(s) and {otherFilesMoved} other file(s) to NoUpload directory.")

def CheckJavascriptFiles() -> None:
    "Print cautions if debug flags are set in .js files."

    for fileName in sorted(os.listdir(Utils.PosixJoin(gOptions.pagesDir,"js"))):
        filePath = Utils.PosixJoin(gOptions.pagesDir,"js",fileName)
        fileContents = Utils.ReadFile(filePath)
        if re.search(r"DEBUG\s*=\s*true",fileContents):
            Alert.caution(filePath,"contains DEBUG = true; this should be changed to false before uploading.")


def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    pass

def ParseArguments() -> None:
    pass
    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main() -> None:
    MoveItemsIn(gDatabase["audioSource"],"session mp3")
    MoveItemsIn(gDatabase["excerpts"],"excerpt mp3")
    MoveItemsIn(gDatabase["reference"],"reference")

    if gOptions.uploadMirror != "preview":
        CheckJavascriptFiles()
    