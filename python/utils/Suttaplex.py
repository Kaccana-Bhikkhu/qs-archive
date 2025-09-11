"""Utility functions for reading SuttaCentral's .json sutta index files.
Run this module as a standalone script to process the files in sutta/suttaplex/raw into sutta/suttaplex/reduced.
Then import the module to query the reduced .json files."""

from __future__ import annotations

import os, sys, json, re
from collections import Counter
from typing import TypedDict, NotRequired

scriptDir,_ = os.path.split(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(scriptDir,'python/modules'))
sys.path.append(os.path.join(scriptDir,'python/utils'))
import Utils

def AllUids(directory = "sutta/suttaplex/raw") -> list[str]:
    """Return a list of all uids a given directory. """

    return [f.removesuffix(".json") for f in sorted(os.listdir(directory)) if 
                os.path.isfile(Utils.PosixJoin(directory,f)) and f.endswith(".json")]


def ReducedSutaplex(uid:str) -> dict[str]:
    """Read the suttaplex json file uid.json in sutta/suttaplex/raw. Eliminate non-English translations and
    extraneous keys and return the output."""

    rawDir = "sutta/suttaplex/raw"
    sourcePath = Utils.PosixJoin(rawDir,uid + ".json")
    if not os.path.isfile(sourcePath) or not sourcePath.endswith(".json"):
        return None

    with open(sourcePath, 'r', encoding='utf-8') as file:
        suttaplex = json.load(file)
    
    reduced = [s for s in suttaplex if s.get("translations")]

    keepKeys = {"acronym","uid","original_title","translated_title","translations","priority_author_uid","verseNo"}
    keepTranslationKeys = {"author","author_short","author_uid","id","title"}
    for sutta in reduced:
        for key in list(sutta):
            if key not in keepKeys:
                del sutta[key]

        sutta["translations"] = [s for s in sutta["translations"] if s["lang"] == "en"]
        for translation in sutta["translations"]:
            for key in list(translation):
                if key not in keepTranslationKeys:
                    del translation[key]

    return reduced

def ReduceRawSuttaplexFiles():
    """Read the suttaplex json files in sutta/suttaplex/raw. Eliminate non-English translations and
    write the output into sutta/suttaplex/reduced."""

    reducedDir = "sutta/suttaplex/reduced"
    os.makedirs(reducedDir,exist_ok=True)
    for uid in AllUids():
        reduced = ReducedSutaplex(uid)

        translationCount = Counter()
        for sutta in reduced:
            for translation in sutta["translations"]:
                translationCount[translation["author_uid"]] += 1

        mostCommon = sorted(translationCount.items(),key = lambda item:-item[1])
        print("Text:",uid,"Sutta count:",len(reduced),"Translations:",mostCommon)

        hasVerses = reduced[0]["verseNo"]
        if hasVerses:
            print("   This text has verse numbers.")

        destPath = Utils.PosixJoin(reducedDir,uid + ".json")
        with open(destPath, 'w', encoding='utf-8') as file:
            json.dump(reduced,file,ensure_ascii=False,indent=2)

def MakeSegmentedSuttaplex(uid: str) -> None:
    """For a given uid, merge the reduced suttaplex database with verseNo fields downloaded from SuttaCentral."""
    
    segmentedDir = "sutta/suttaplex/segmented"
    os.makedirs(segmentedDir,exist_ok=True)
    
    suttaplex = ReducedSutaplex(uid)
    for sutta in suttaplex:
        suttaURL = f"https://suttacentral.net/api/suttas/{sutta['uid']}"
        
        with Utils.OpenUrlOrFile(suttaURL) as file:
            suttaData = json.load(file)
        
        sutta["verseNo"] = suttaData["suttaplex"]["verseNo"]

    destPath = Utils.PosixJoin(segmentedDir,uid + ".json")
    with open(destPath, 'w', encoding='utf-8') as file:
        json.dump(suttaplex,file,ensure_ascii=False,indent=2)
        
def SegmentedSuttaplex(uid:str) -> dict[str]:
    """Return a segmented suttaplex dict for a given uid. Download and cache if necessary."""

    segmentedDir = "sutta/suttaplex/segmented"
    filepath = Utils.PosixJoin(segmentedDir,uid + ".json")
    if not os.path.isfile(filepath):
        MakeSegmentedSuttaplex(uid)
    
    with open(filepath, 'r', encoding='utf-8') as file:
        suttaplex = json.load(file)
    return suttaplex

def DoubleReferenceDNSuttas() -> None:
    """Print the DN sutta numbers for which PTS citations have two numbers."""
    doubleCitations = []
    for sutta in SegmentedSuttaplex("dn"):
        if re.search(r"pts-cs[0-9]+\.[0-9]+",sutta["verseNo"]):
            doubleCitations.append(int(re.search(r"[0-9]+",sutta["uid"])[0]))
    print(doubleCitations)

class SuttaIndexEntry(TypedDict):
    uid: str
    mark: NotRequired[str]

def SuttaIndex(uid:str,indexBy:str,bookmarkWith:str = "",indexByComesFirst = True) -> dict[str,SuttaIndexEntry]:
    """Returns an index of references to the suttas in a given text.
        uid: the SuttaCentral text uid.
        indexBy: create an index for all bookmarks that start with this string 
        bookmarkWith: bookmark the text using this bookmark
        indexByComesFirst: if True, equate each indexBy bookmark with the next bookmarkWith bookmark; if False equate with the previous.
        MakeSuttaIndex("snp","vnp","vns") returns a dict with keys "vnp1", "vnp2",...
        and values {"suttaUid":"snp1","bookmark":"vns1"}, {"suttaUid":"snp1","bookmark":"vns2"},...
        If bookmarkWith is not given, omit the bookmark key."""
    
    suttaplex = SegmentedSuttaplex(uid)
    index:dict[str,SuttaIndexEntry] = {}
    if not bookmarkWith:
        bookmarkWith = indexBy
    
    for sutta in suttaplex:
        bookmarks = sutta["verseNo"].split(",")
        bookmarks = [b.strip() for b in bookmarks]
        bookmarks = [b for b in bookmarks if b.startswith(indexBy) or (bookmarkWith and b.startswith(bookmarkWith))]

        prevBookmarkWith = None
        for n,b in enumerate(bookmarks):
            if b.startswith(indexBy):
                if bookmarkWith == indexBy:
                    index[b] = SuttaIndexEntry(uid=sutta["uid"])
                elif indexByComesFirst:
                    newBookmark = None
                    for lookaheadIndex in range(n,len(bookmarks)):
                        if bookmarks[lookaheadIndex].startswith(bookmarkWith):
                            newBookmark = bookmarks[lookaheadIndex]
                            continue
                    if not newBookmark:
                        newBookmark = prevBookmarkWith
                    index[b] = SuttaIndexEntry(uid=sutta["uid"],mark=newBookmark)
                else:
                    index[b] = SuttaIndexEntry(uid=sutta["uid"],mark=prevBookmarkWith)
            else:
                prevBookmarkWith = b
    
    return index

def MakeSnpIndex() -> None:
    indexDir = "sutta/suttaplex/index"
    os.makedirs(indexDir,exist_ok=True)
    destPath = Utils.PosixJoin(indexDir,"snp-vnp" + ".json")
    with open(destPath, 'w', encoding='utf-8') as file:
        json.dump(SuttaIndex("snp","vnp"),file,ensure_ascii=False,indent=2)

if __name__ == "__main__":
    
    MakeSnpIndex()

    # MakeSegmentedSuttaplex("dn")
    # ReduceRawSuttaplexFiles()