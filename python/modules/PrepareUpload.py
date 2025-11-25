"""Move unlinked files into xxxNoUpload directories in preparation for uploading the website.
"""

from __future__ import annotations

import os, re, argparse, json
import Utils, Alert, Link, FileRegister
from typing import Iterable
import BuildReferences

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

def MinifyDatabases(minify: bool) -> None:
    """Remove spacing from databases read by Javascript. minify = False restores default spacing."""
    for databaseFile in ["SearchDatabase.json","AutoCompleteDatabase.json","FeaturedDatabase.json"]:
        databaseFile = Utils.PosixJoin("pages/assets",databaseFile)

        with open(databaseFile, 'r', encoding='utf-8') as file:
            database = json.load(file)
        with open(databaseFile, 'w', encoding='utf-8') as file:
            json.dump(database,file,ensure_ascii=False,indent = None if minify else 2)

def CheckJavascriptFiles() -> None:
    "Print cautions if debug flags are set in .js files."

    for fileName in sorted(os.listdir(Utils.PosixJoin(gOptions.pagesDir,"js"))):
        filePath = Utils.PosixJoin(gOptions.pagesDir,"js",fileName)
        fileContents = Utils.ReadFile(filePath)
        if re.search(r"DEBUG\s*=\s*true",fileContents):
            Alert.caution(filePath,"contains DEBUG = true; this should be changed to false before uploading.")

def CheckPreviousVersionFiles() -> None:
    """Read documentation/prevVersion/HashCache.json and compare it to the current HashCache.
    Print the files that have been added and removed."""

    prevCache = Utils.PosixJoin(gOptions.documentationDir,"prevVersion/HashCache.json")
    baseDir = gOptions.pagesDir
    if not os.path.isfile(prevCache):
        Alert.caution(prevCache,"is not present. Copy pages/assets/HashCache.json from the previous version to this path to display which files have been added and removed.")
        return
    
    with FileRegister.FileRegister(Utils.PosixSplit(prevCache)[0],"HashCache.json") as oldFileRegister:
        with FileRegister.FileRegister(baseDir,"assets/HashCache.json") as newFileRegister:
            oldFiles = set(oldFileRegister.record)
            newFiles = set(newFileRegister.record)
            added = newFiles - oldFiles
            removed = oldFiles - newFiles
            if removed:
                Alert.caution(len(removed),"file(s) were removed since the previous release. Consider redirecting them:",lineSpacing=0)
                Alert.structure("\n".join(sorted(removed)),indent=0,lineSpacing=1)
            if added:
                Alert.info(len(added),"file(s) were added since the previous release:")
                Alert.structure("\n".join(sorted(added)),indent=0,lineSpacing=1)

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--minifyDatabases',action=argparse.BooleanOptionalAction,help="Remove spaces from database files.")
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

    if gOptions.minifyDatabases is not None:
        MinifyDatabases(gOptions.minifyDatabases)

    if gOptions.uploadMirror != "preview":
        CheckJavascriptFiles()
        CheckPreviousVersionFiles()
    
    if BuildReferences.gReferencesChanged:
        Alert.warning("References have changed. Run Render again before uploading.")
    