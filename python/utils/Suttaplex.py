"""Utility functions for reading SuttaCentral's .json sutta index files.
Run this module as a standalone script to process the files in sutta/suttaplex/raw into sutta/suttaplex/reduced.
Then import the module to query the reduced .json files."""

from __future__ import annotations

import os, sys, json, re
from collections import Counter
from typing import TypedDict, Callable
from functools import lru_cache
import Alert

scriptDir,_ = os.path.split(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(scriptDir,'python/modules'))
sys.path.append(os.path.join(scriptDir,'python/utils'))
import Utils

def AllUids(directory = "sutta/suttaplex/raw") -> list[str]:
    """Return a list of all uids a given directory. """

    return [f.removesuffix(".json") for f in sorted(os.listdir(directory)) if 
                os.path.isfile(Utils.PosixJoin(directory,f)) and f.endswith(".json")]

def CacheJsonFile(cacheDir: str,indent:None|int = 2) -> Callable[...,dict]:
    """Implement a json disk cache for function returning a dict"""
    def InnerWrapper(dictGenerator: Callable[...,dict]):
        """The dictGenerator function takes a variable number of arguments which can be converted to strings."""
        def CachedDictGenerator(*args) -> dict:
            if args:
                cachedFileName = "_".join(str(arg) for arg in args) + ".json"
            else:
                cachedFileName= "_noArgs_.json"
            cachedFilePath = Utils.PosixJoin(cacheDir,cachedFileName)

            if os.path.isfile(cachedFilePath):
                try:
                    with open(cachedFilePath, 'r', encoding='utf-8') as file:
                        return json.load(file)
                except Exception as error:
                    Alert.error(error,"when opening",cachedFilePath,". Will try to regenerate the json file.")
            
            Alert.info("Generating json file:",cachedFilePath)
            os.makedirs(cacheDir,exist_ok=True)
            returnDict = dictGenerator(*args)
            with open(cachedFilePath, 'w', encoding='utf-8') as file:
                json.dump(returnDict,file,ensure_ascii=False,indent=indent)
            return returnDict
            
        return CachedDictGenerator
    return InnerWrapper

@CacheJsonFile("sutta/suttaplex/raw",indent=None)
def RawSuttaplex(uid:str) -> dict[str]:
    """Return and cache raw suttaplex files from SuttaCentral"""
    suttaplexURL = f"https://suttacentral.net/api/suttaplex/{uid}"
        
    with Utils.OpenUrlOrFile(suttaplexURL) as file:
        return json.load(file)

def ReducedSutaplex(uid:str) -> dict[str]:
    """Read the suttaplex json file uid.json in sutta/suttaplex/raw. Eliminate non-English translations and
    extraneous keys and return the output."""

    suttaplex = RawSuttaplex(uid)
    
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

@CacheJsonFile("sutta/suttaplex/segmented")
def SegmentedSuttaplex(uid: str) -> None:
    """For a given uid, merge the reduced suttaplex database with verseNo fields downloaded from SuttaCentral."""
    
    segmentedDir = "sutta/suttaplex/segmented"
    os.makedirs(segmentedDir,exist_ok=True)
    
    suttaplex = ReducedSutaplex(uid)
    for sutta in suttaplex:
        suttaURL = f"https://suttacentral.net/api/suttas/{sutta['uid']}"
        
        with Utils.OpenUrlOrFile(suttaURL) as file:
            suttaData = json.load(file)
        
        sutta["verseNo"] = suttaData["suttaplex"]["verseNo"]

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
    mark: str
    translator: str

def MakeSuttaIndex(uid:str,indexBy:str,bookmarkWith:str = "",indexByComesFirst = True,preferredTranslators:list[str] = ()) -> dict[str,SuttaIndexEntry]:
    """Returns an index of references to the suttas in a given text.
        uid: the SuttaCentral text uid.
        indexBy: create an index for all bookmarks that start with this string 
        bookmarkWith: bookmark the text using this bookmark
        indexByComesFirst: if True, equate each indexBy bookmark with the next bookmarkWith bookmark; if False equate with the previous.
        MakeSuttaIndex("snp","vnp","vns") returns a dict with keys "vnp1", "vnp2",...
        and values {"uid":"snp1","mark":"vns1","translator":"sujato"}, {"uid":"snp1","mark":"vns2","translator":"sujato"},...
        If bookmarkWith is not given, omit the bookmark key."""
    
    suttaplex = SegmentedSuttaplex(uid)
    index:dict[str,SuttaIndexEntry] = {}
    if not bookmarkWith:
        bookmarkWith = indexBy
    
    for sutta in suttaplex:
        bookmarks = sutta["verseNo"].split(",")
        bookmarks = [b.strip() for b in bookmarks]
        bookmarks = [b for b in bookmarks if b.startswith(indexBy) or (bookmarkWith and b.startswith(bookmarkWith))]

        translator = sutta["priority_author_uid"]
        if preferredTranslators:
            availableTranslations = set(t["author_uid"] for t in sutta["translations"])
            for trans in preferredTranslators:
                if trans in availableTranslations:
                    translator = trans
                    break

        prevBookmarkWith = None
        for n,b in enumerate(bookmarks):
            if b.startswith(indexBy):
                if bookmarkWith == indexBy:
                    index[b] = SuttaIndexEntry(uid=sutta["uid"],translator=translator)
                elif indexByComesFirst:
                    newBookmark = None
                    for lookaheadIndex in range(n,len(bookmarks)):
                        if bookmarks[lookaheadIndex].startswith(bookmarkWith):
                            newBookmark = bookmarks[lookaheadIndex]
                            continue
                    if not newBookmark:
                        newBookmark = prevBookmarkWith
                    index[b] = SuttaIndexEntry(uid=sutta["uid"],mark=newBookmark,translator=translator)
                else:
                    index[b] = SuttaIndexEntry(uid=sutta["uid"],mark=prevBookmarkWith,translator=translator)
            else:
                prevBookmarkWith = b
    
    return index

def MakeSnpIndex() -> None:
    indexDir = "sutta/suttaplex/index"
    os.makedirs(indexDir,exist_ok=True)
    destPath = Utils.PosixJoin(indexDir,"snp-vnp" + ".json")
    with open(destPath, 'w', encoding='utf-8') as file:
        json.dump(SuttaIndex("snp","vnp"),file,ensure_ascii=False,indent=2)

def MakeThigIndex() -> None:
    indexDir = "sutta/suttaplex/index"
    os.makedirs(indexDir,exist_ok=True)
    destPath = Utils.PosixJoin(indexDir,"thig-vnp" + ".json")
    with open(destPath, 'w', encoding='utf-8') as file:
        json.dump(SuttaIndex("thig","vnp"),file,ensure_ascii=False,indent=2)

@lru_cache(maxsize=None)
def SuttaIndex(textUid:str) -> dict[str,SuttaIndexEntry]:
    """Returns an index of this sutta. Returns None on failure"""
    if textUid in ("dhp","snp","thag","thig"):
        return MakeSuttaIndex(textUid,"vnp")
    elif textUid == "mil": # https://suttacentral.net/mil6.3.10/en/tw_rhysdavids?lang=en&reference=main/pts&highlight=false#pts-vp-pli320
        return MakeSuttaIndex(textUid,"pts-vp-pli",preferredTranslators=["kelly","tw_rhysdavids"])
    return None

@CacheJsonFile("sutta/suttaplex/translator")
@lru_cache(maxsize=None)
def TranslatorDict(textUid:str) -> dict[str,list[str]]:
    """Returns the dict {suttaUid:list[translatorUid]} for a given textUid."""

    suttaplex = ReducedSutaplex(textUid)
    returnDict = {}
    for sutta in suttaplex:
        returnDict[sutta["uid"]] = [trans["author_uid"] for trans in sutta["translations"]]
    
    return returnDict

def DotRef(numbers: list[int],printCount:int = None,filler:int = 1,separator:str = "."):
    """A utility function that returns strings of the form 'n0.n1.n2'.
    numbers: the list of numbers to print.
    printCount: print this many numbers; if omitted, set to len(numbers).
    filler: if printCount > len(numbers), add filler at the end.
    separator: the separator character between numbers."""

    if printCount is None:
        printCount = len(numbers)
    strings = [str(n) for n in numbers]
    if len(strings) < printCount:
        strings += (printCount - len(strings)) * [str(filler)]
    return separator.join(strings)

def PreferredTranslator(textUid:str,refNumbers:list[int],silentFail = False) -> str:
    """Return the preferred translator for the whole sutta specified by textUid and refNumbers."""

    textUid = textUid.lower()
    translatorDict = TranslatorDict(textUid)
    suttaUid = textUid + DotRef(refNumbers)
    availableTranslations = translatorDict.get(suttaUid,None)

    def ChooseTranslator(available:list[str]) -> str:
        "Pick the preferred translator from those available."
        priorityTranslator = ("bodhi","kelly","sujato")
        for t in priorityTranslator:
            if t in available:
                return t
        return available[0]

    if not availableTranslations:
        spanUid = InterpolatedSuttaDict(textUid).get(suttaUid)
        if spanUid:
            availableTranslations = translatorDict.get(spanUid,None)
        if availableTranslations:
            return ChooseTranslator(availableTranslations)
        else:
            if not silentFail:
                Alert.warning("Cannot find",suttaUid,"on SuttaCentral.")
            return ""
    else:
        return ChooseTranslator(availableTranslations)
    
def ExistsOnSC(textUid:str,refNumbers:list[int]) -> bool:
    """Returns whether this text exists on SuttaCentral."""
    return bool(PreferredTranslator(textUid,refNumbers))
class SuttaTitle(TypedDict):
    original_title: str
    translated_title: str

def ParseUid(uid: str) -> tuple[str,tuple[int,int]]:
    """Parse a uid into its text and number(s)."""

    match = re.match(r"([a-zA-Z]+)([0-9]+)?(?:[.:]([0-9]+))?",uid)
    if match:
        numbers = tuple(int(match[n]) for n in range(2,4) if match[n])
        return match[1],numbers
    else:
        return "",()

@CacheJsonFile("sutta/suttaplex/title")
@lru_cache(maxsize=None)
def TitleDict(textUid:str) -> dict[str,SuttaTitle]:
    """Return the dict {suttaUid:SuttaTitle} for a given textUid."""
    suttaplex = RawSuttaplex(textUid)
    returnDict:dict[str,SuttaTitle] = {}

    def ProcessTitle(title: str) -> str:
        title = title.strip()
        title = re.sub(r"^[0-9]+\.?","",title)
        return title.strip()

    for sutta in suttaplex:
        textUid,numbers = ParseUid(sutta["uid"])
        prefTrans = numbers and PreferredTranslator(textUid,numbers,silentFail=True)
        if prefTrans and prefTrans != "sujato":
            for translation in sutta.get("translations",()):
                if translation.get("author_uid") == prefTrans and "title" in translation:
                    returnDict[sutta["uid"]] = SuttaTitle(original_title=ProcessTitle(sutta["original_title"]),
                                                  translated_title=ProcessTitle(translation["title"]))
                    break
        if sutta["uid"] not in returnDict and sutta.get("original_title") and sutta.get("translated_title"):
            returnDict[sutta["uid"]] = SuttaTitle(original_title=ProcessTitle(sutta["original_title"]),
                                                  translated_title=ProcessTitle(sutta["translated_title"]))
    
    return returnDict

def Title(suttaUid:str,translated:bool = True) -> str:
    """Return the title of this sutta. Return '' if it cannot be found."""
    baseUid = re.match(r"[a-z-]*",suttaUid)[0]
    if not baseUid:
        return ""
    
    titles = TitleDict(baseUid).get(suttaUid)
    if titles:
        return titles['translated_title'] if translated else titles['original_title']
    else:
        return ""

@CacheJsonFile("sutta/suttaplex/interpolated")
@lru_cache(maxsize=None)
def InterpolatedSuttaDict(textUid:str) -> dict[str,list[str]]:
    """Create a dict containing interpolated sutta references:
    e.g. 'an1.1-10' becomes 'an1.1', 'an1.2', ... , 'an1.10'."""

    translatorDict = TranslatorDict(textUid)
    returnDict = {}
    for suttaUid in translatorDict:
        m = re.match("(.*?)([0-9]+)-([0-9]+)$",suttaUid)
        if m:
            for suttaNumber in range(int(m[2]),int(m[3]) + 1):
                returnDict[f"{m[1]}{suttaNumber}"] = suttaUid
    
    return returnDict

def PrintTranslatorCount():
    """For each text, print the number of suttas each translator has translated."""

    for uid in AllUids():
        translatorDict = TranslatorDict(uid)

        translationCount = Counter()
        for translatorList in translatorDict.values():
            for translator in translatorList:
                translationCount[translator] += 1

        mostCommon = sorted(translationCount.items(),key = lambda item:-item[1])
        print("Text:",uid,"Sutta count:",len(translatorDict),"Translations:",mostCommon)


if __name__ == "__main__":
    Alert.verbosity = 3
    PrintTranslatorCount()
    # print(len(SegmentedSuttaplex("dn")))

    # MakeSegmentedSuttaplex("dn")
    # ReduceRawSuttaplexFiles()