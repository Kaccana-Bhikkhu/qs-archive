"""An optional module to export selected excerpt audio files with tsv catalogs.
"""

from __future__ import annotations

import os, shutil
from typing import TextIO, NamedTuple, Iterable
import Utils, Alert
import ReviewDatabase, Database, Filter, Link

def CopyExcerptAudio(excerpt: dict[str],path: str) -> None:
    "Copy the audio file associated with excerpt to a given path."

    if gOptions.exportCatalogOnly:
        return
    os.makedirs(path,exist_ok=True)
    audioFile = Link.LocalFile(excerpt)
    if audioFile:
        shutil.copy2(audioFile,Utils.PosixJoin(path,Utils.PosixSplit(audioFile)[1]))
    else:
        Alert.warning("Could not copy audio file for",excerpt)

def ExportFeaturedExcerptsBySubtopic(catalog: TextIO) -> int:
    """Copy the audio files for featured excerpts into a directory structure organized by subtopic.
    The --exportFTagFilter options specify with subtopics and tags to export.
    Returns the number of excerpts exported."""

    firstCluster = True
    exportCount = 0
    for subtopicOrTag in Database.SubtopicsAndTags():
        summary = ReviewDatabase.FeaturedExcerptSummary(subtopicOrTag["tag"],header=firstCluster,printFTag=True)
        if summary:
            print(summary,file=catalog)
            print(file=catalog)
        firstCluster = False

        isSubtopic = "topicCode" in subtopicOrTag
        if isSubtopic:
            tags = [subtopicOrTag["tag"]] + list(subtopicOrTag["subtags"])
        else:
            tags = [subtopicOrTag["tag"]]
        
        featuredExcerpts = Filter.FTag(tags)(gDatabase["excerpts"])
        if not featuredExcerpts:
            continue
        featuredExcerpts = sorted(featuredExcerpts,key=lambda x: Database.FTagOrder(x,tags))
        exportCount += len(featuredExcerpts)

        path = Utils.PosixJoin(gOptions.exportPath,"subtopics" if isSubtopic else "tags",Utils.slugify(subtopicOrTag["tag"]))
        for excerpt in featuredExcerpts:
            CopyExcerptAudio(excerpt,path)
    return exportCount

def CatalogLine(excerpt: dict[str], header:bool=False) -> str:
    """Return one line of a .tsv catalog file corresponding to excerpt.
    Print a header line if specified."""
    lines = []
    if header:
        columns = ["code","flags","duration","kind","text"]
        lines.append("\t".join(columns))
    lines.append("\t".join((
        Database.ItemCode(excerpt),
        excerpt["flags"],
        excerpt["duration"],
        excerpt["kind"],
        Utils.EllideText(excerpt["text"],70)
    )))
    
    return "\n".join(lines)

def ExportExcerpts(catalog: TextIO) -> int:
    """Export excerpts specified by the various --exportFilter options.
    Returns the number of excerpts exported"""

    filters = []
    if gOptions.exportFilterFlags:
        filters.append(Filter.Flags(gOptions.exportFilterFlags))
    
    firstLine = True
    exportCount = 0
    for excerpt in Filter.And(*filters).Apply(gDatabase["excerpts"]):
        print(CatalogLine(excerpt,header=firstLine),file=catalog)
        firstLine = False

        CopyExcerptAudio(excerpt,gOptions.exportPath)
        exportCount += 1
    return exportCount

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--exportPath',type=str,default="../exportedAudio",help="Directory to export audio to.")
    parser.add_argument('--exportCatalogOnly',**Utils.STORE_TRUE,help='Write Catalog.tsv without copying any files.')
    parser.add_argument('--exportFilterFlags',type=str,default="",help="Export excerpts with one or more of these flags.")

def ParseArguments() -> None:
    pass    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main() -> None:
    os.makedirs(gOptions.exportPath,exist_ok=True)
    with open(Utils.PosixJoin(gOptions.exportPath,"Catalog.tsv"),mode="w",encoding="utf-8") as catalog:
        exportMode = "subtopic"
        for option in ["exportFilterFlags"]:
            if getattr(gOptions,option):
                exportMode = "flat"

        if exportMode == "subtopic":
            count = ExportFeaturedExcerptsBySubtopic(catalog)
        else:
            count = ExportExcerpts(catalog)
    
    if gOptions.exportCatalogOnly:
        Alert.info("Created catalog file listing",count,"excerpts.")
    else:
        Alert.info("Exported",count,"excerpts to",gOptions.exportPath,".")
