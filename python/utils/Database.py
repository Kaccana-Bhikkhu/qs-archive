"""Functions for reading and writing the json databases used in QSArchive."""

from collections.abc import Iterable
from collections import defaultdict
import json, re, itertools
import Html2 as Html
import Link
from Build import gDatabase
import SplitMp3
import Utils
import Alert
import Filter
import ParseCSV
from functools import lru_cache


gOptions = None
gDatabase:dict[str] = {} # These will be set later by QSarchive.py

def LoadDatabase(filename: str) -> dict:
    """Read the database indicated by filename"""

    with open(filename, 'r', encoding='utf-8') as file: # Otherwise read the database from disk
        newDB = json.load(file)
    
    for x in newDB["excerpts"]:
        if "clips" in x:
            x["clips"] = [SplitMp3.Clip(*c) for c in x["clips"]]
    
    return newDB

def RemoveFragments(excerpts: Iterable[dict[str]]) -> Iterable[dict[str]]:
    """Yield these excerpts but skip fragments if their source excerpt is present."""

    lastNonFragment = ()
    for x in excerpts:
        if ParseCSV.ExcerptFlag.FRAGMENT in x["flags"]:
            if (x["event"],x["sessionNumber"],int(x["excerptNumber"])) != lastNonFragment:
                yield x
        else:
            yield x
            lastNonFragment = (x["event"],x["sessionNumber"],x["excerptNumber"])

def CountExcerpts(excerpts: Iterable[dict[str]],countSessionExcerpts:bool = False) -> int:
    """Count excerpts excluding fragments if the list includes their source excerpt."""

    return sum(1 for x in RemoveFragments(excerpts) if x["fileNumber"] or countSessionExcerpts)

def GroupFragments(excerpts: Iterable[dict[str]]) -> Iterable[list[dict[str]]]:
    """Yield lists containing non-fragment excerpts followed by their fragments."""
    
    # Fragments share the integral part of their excerpt number with their source.
    for key,group in itertools.groupby(excerpts,lambda x: (x["event"],x["sessionNumber"],int(x["excerptNumber"]))):
        yield list(group)

def FragmentSource(excerpt: dict[str]) -> dict[str]:
    """If this excerpt is a fragment, return its source. If not, return the excerpt itself."""

    excerptDict = ExcerptDict()
    while (excerpt["excerptNumber"] != int(excerpt["excerptNumber"])):
        excerpt = excerptDict[excerpt["event"]][excerpt["sessionNumber"]][excerpt["fileNumber"] - 1]
    
    return excerpt

def FindSession(sessions:list, event:str ,sessionNum: int) -> dict:
    "Return the session specified by event and sessionNum."

    for session in sessions:
        if session["event"] == event and session["sessionNumber"] == sessionNum:
            return session

    raise ValueError(f"Can't locate session {sessionNum} of event {event}")


def Mp3Link(item: dict,directoryDepth: int = 2) -> str:
    """Return a link to the mp3 file associated with a given excerpt or session.
    item: a dict representing an excerpt or session.
    directoryDepth: depth of the html file we are writing relative to the home directory"""

    if "fileNumber" in item and item["fileNumber"]: # Is this is a regular (non-session) excerpt?
        return Link.URL(item,directoryDepth=directoryDepth)

    session = FindSession(gDatabase["sessions"],item["event"],item["sessionNumber"])
    audioSource = gDatabase["audioSource"][session["filename"]]
    return Link.URL(audioSource,directoryDepth=directoryDepth)


def EventLink(event:str, session: int|None = None, fileNumber:int|None = None) -> str:
    "Return a link to a given event, session, and fileNumber. If session == None, link to the top of the event page"

    directory = "../events/"
    if session or fileNumber:
        return f"{directory}{event}.html#{ItemCode(event=event,session=session,fileNumber=fileNumber)}"
    else:
        return f"{directory}{event}.html"


def ItemCitation(item: dict) -> str:
    """Return html code with the name of the event, session number, and file number.
    item can be an event, session or excerpt"""

    event = item.get("event",item.get("code",None))
    session = item.get("sessionNumber",None)

    eventName = gDatabase["event"][event]["title"]
    if not re.search(r"[0-9]{4}",eventName):
        eventYear = re.search(r"[0-9]{4}",event)
        if eventYear:
            eventName += f" [{eventYear[0]}]"
    parts = [Html.Tag("a",{"href":EventLink(event)})(eventName)]
    if session:
        parts.append(Html.Tag("a",{"href":EventLink(event,session)})(f"Session {session}"))
    excerptNumber = item.get("excerptNumber",None)
    if excerptNumber:
        fileNumber = FragmentSource(item)["fileNumber"]
        parts.append(Html.Tag("a",{"href":EventLink(event,session,fileNumber)})(f"Excerpt {excerptNumber}"))
    return ", ".join(parts)


def TagLookup(tagRef:str,tagDictCache:dict = {}) -> str|None:
    "Search for a tag based on any of its various names. Return the base tag name."

    if not tagDictCache: # modify the value of a default argument to create a cache of potential tag references
        tagDB = gDatabase["tag"]
        tagDictCache.update((tag,tag) for tag in tagDB)
        tagDictCache.update((tagDB[tag]["fullTag"],tag) for tag in tagDB)
        tagDictCache.update((tagDB[tag]["pali"],tag) for tag in tagDB if tagDB[tag]["pali"])
        tagDictCache.update((tagDB[tag]["fullPali"],tag) for tag in tagDB if tagDB[tag]["fullPali"])

        subsumedDB = gDatabase["tagSubsumed"]
        tagDictCache.update((tag,subsumedDB[tag]["subsumedUnder"]) for tag in subsumedDB)
        tagDictCache.update((subsumedDB[tag]["fullTag"],subsumedDB[tag]["subsumedUnder"]) for tag in subsumedDB)
        tagDictCache.update((subsumedDB[tag]["pali"],subsumedDB[tag]["subsumedUnder"]) for tag in subsumedDB if subsumedDB[tag]["pali"])
        tagDictCache.update((subsumedDB[tag]["fullPali"],subsumedDB[tag]["subsumedUnder"]) for tag in subsumedDB if subsumedDB[tag]["fullPali"])

    return tagDictCache.get(tagRef,None)

def TagClusterLookup(clusterRef:str,tagClusterDictCache:dict = {}) -> str|None:
    "Search for a tag cluster based on any of its various names. Return the base tag name."

    if not tagClusterDictCache: # modify the value of a default argument to create a cache of potential tag references
        clusterDB = gDatabase["subtopic"]
        tagDB = gDatabase["tag"]
        tagClusterDictCache.update((cluster,cluster) for cluster in clusterDB)
        tagClusterDictCache.update((clusterDB[cluster]["displayAs"],cluster) for cluster in clusterDB)
        tagClusterDictCache.update((tagDB[cluster]["fullTag"],cluster) for cluster in clusterDB)

    return tagClusterDictCache.get(clusterRef,None)

@lru_cache(maxsize=None)
def KeyTopicTags() -> dict[str,None]:
    "Return a dict of tag names which appear in key topics. The dict class simulates an ordered set."

    returnValue = {}
    for subtopic in gDatabase["subtopic"].values():
        returnValue[subtopic["tag"]] = None
        for tag in subtopic["subtags"]:
            returnValue[tag] = None
    return returnValue

@lru_cache(maxsize=None)
def SoloSubtopics() -> set[str]:
    "Return a set of tag names which are subtopics without subtags."

    returnValue = set()
    for subtopic in gDatabase["subtopic"].values():
        if not subtopic["subtags"]:
            returnValue.add(subtopic["tag"])
    return returnValue

@lru_cache(maxsize=None)
def SecondarySubtopics() -> set[str]:
    "Return a set of tag names which are subtopics of more than one key topic."

    returnValue = set()
    for subtopic in gDatabase["subtopic"].values():
        returnValue.update(subtopic.get("secondarySubtags",()))
    return returnValue

def SubtopicsAndTags() -> Iterable[str]:
    "Iterate over all subtopics and then over all tags not in subtopics"
    yield from gDatabase["subtopic"].values()
    keyTopicTags = KeyTopicTags()
    yield from (tag for tag in gDatabase["tag"].values() if tag["tag"] not in keyTopicTags and ParseCSV.TagFlag.VIRTUAL not in tag["flags"])

def ParentTagListEntry(listIndex: int) -> dict|None:
    "Return a the entry in gDatabase['tagDisplayList'] that corresponds to this tag's parent tag."

    tagHierarchy = gDatabase["tagDisplayList"]
    level = tagHierarchy[listIndex]["level"]
    
    if level < 2:
        return None
    while (listIndex >= 0):
        if tagHierarchy[listIndex]["level"] < level:
            return tagHierarchy[listIndex]
        listIndex -= 1

    return None


def TeacherLookup(teacherRef:str,teacherDictCache:dict = {}) -> str|None:
    "Search for a tag based on any of its various names. Return the base tag name."

    if not teacherDictCache: # modify the value of a default argument to create a cache of potential teacher references
        teacherDB = gDatabase["teacher"]
        teacherDictCache.update((t,t) for t in teacherDB)
        teacherDictCache.update((teacherDB[t]["attributionName"],t) for t in teacherDB)
        teacherDictCache.update((teacherDB[t]["fullName"],t) for t in teacherDB)

    return teacherDictCache.get(teacherRef,None)

@lru_cache(maxsize=None)
def ExcerptDict() -> dict[str,dict[int,dict[int,dict[str]]]]:
    """Return a dictionary of excerpts that can be referenced as:
    ExcerptDict()[eventCode][sessionNumber][fileNumber]"""
    excerptDict = defaultdict(lambda: defaultdict(defaultdict))
    for x in gDatabase["excerpts"]:
        excerptDict[x["event"]][x["sessionNumber"]][x["fileNumber"]] = x
    return excerptDict

@lru_cache(maxsize=None)
def SessionDict() -> dict[str,dict[int,dict[str]]]:
    """Returns a dictionary of sessions that can be referenced as:
    SessionDict()[eventCode][sessionNumber]"""
    sessionDict = defaultdict(defaultdict)
    for s in gDatabase["sessions"]:
        sessionDict[s["event"]][s["sessionNumber"]] = s
    return sessionDict

def FindExcerpt(eventOrCode: str, session: int|None = None, fileNumber: int|None = None) -> dict|None:
    """Return the excerpt that matches these parameters. Otherwise return None."""

    if not gDatabase:
        return None
    if fileNumber is None:
        if eventOrCode:
            eventOrCode,session,fileNumber = ParseItemCode(eventOrCode)
        if fileNumber is None:
            return None
    if session is None:
        session = 0
    try:
        return ExcerptDict()[eventOrCode][session][fileNumber]
    except KeyError:
        return None


def FindOwningExcerpt(annotation: dict) -> dict:
    """Search the global database of excerpts to find which one owns this annotation.
    This is a slow function and should be called infrequently."""
    if not gDatabase:
        return None
    for x in gDatabase["excerpts"]:
        for a in x["annotations"]:
            if annotation is a:
                return x
    return None


def SubtagDescription(tag: str) -> str:
    "Return a string describing this tag's subtags."
    primary = gDatabase["tag"][tag]["listIndex"]
    listEntry = gDatabase["tagDisplayList"][primary]
    return f'{listEntry["subtagCount"]} subtags, {listEntry["subtagExcerptCount"]} excerpts'


def GroupBySession(excerpts: list[dict],sessions: list[dict]|None = None) -> Iterable[tuple[dict,list[dict]]]:
    """Yield excerpts grouped by their session."""
    if not sessions:
        sessions = gDatabase["sessions"]
    sessionIterator = iter(sessions)
    curSession = next(sessionIterator)
    yieldList = []
    for excerpt in excerpts:
        while excerpt["event"] != curSession["event"] or excerpt["sessionNumber"] != curSession["sessionNumber"]:
            if yieldList:
                yield curSession,yieldList
                yieldList = []
            curSession = next(sessionIterator)
        yieldList.append(excerpt)

    if yieldList:
        yield curSession,yieldList


def GroupByEvent(excerpts: list[dict],events: dict[dict]|None = None) -> Iterable[tuple[dict,list[dict]]]:
    """Yield excerpts grouped by their event. NOT YET TESTED"""
    if not events:
        events = gDatabase["event"]
    yieldList = []
    curEvent = ""
    for excerpt in excerpts:
        while excerpt["event"] != curEvent:
            if yieldList:
                yield events[curEvent],yieldList
                yieldList = []
            curEvent = excerpt["event"]
        yieldList.append(excerpt)

    if yieldList:
        yield events[curEvent],yieldList


def PairWithSession(excerpts: list[dict],sessions: list[dict]|None = None) -> Iterable[tuple[dict,dict]]:
    """Yield tuples (session,excerpt) for all excerpts."""
    if not sessions:
        sessions = gDatabase["sessions"]

    for session,excerptList in GroupBySession(excerpts,sessions):
        yield from ((session,x) for x in excerptList)


def ItemCode(item:dict|None = None, event:str = "", session:int|None = None, fileNumber:int|None = None) -> str:
    "Return a code for this item. "

    if item:
        event = item.get("event",None)
        session = item.get("sessionNumber",None)
        fileNumber = item.get("fileNumber",None)

    outputStr = event
    if session is not None:
        outputStr += f"_S{session:02d}"
    if fileNumber is not None:
        outputStr += f"_F{fileNumber:02d}"
    return outputStr

def ExcerptNumberCode(excerpt:dict|None = None, event:str = "", session:int|None = None, excerptNumber:float|None = None) -> str:
    "Return a code for this item as above, but use the excerpt number instead of the file number."
    "event, session, and excerptNumber are required unless excerpt is specified."

    if excerpt:
        event = excerpt.get("event",None)
        session = excerpt.get("sessionNumber",None)
        excerptNumber = excerpt.get("excerptNumber",None)

    outputStr = event
    outputStr += f"_S{session:02d}"
    outputStr += f"_E{excerptNumber:02.1f}".replace(".0","")
    return outputStr

def ParseItemCode(itemCode:str) -> tuple[str,int|None,int|None]:
    "Parse an item code into (eventCode,session,fileNumber). If parsing fails, return ("",None,None)."

    m = re.match(r"([^_]*)(?:_S([0-9]+))?(?:_F([0-9]+))?",itemCode)
    session = None
    fileNumber = None
    if m:
        if m[2]:
            session = int(m[2])
        if m[3]:
            fileNumber = int(m[3])
        return m[1],session,fileNumber
    else:
        return "",None,None


def ItemRepr(item: dict) -> str:
    """Generate a repr-style string for various dict types in gDatabase. 
    Check the dict keys to guess what it is.
    If we can't identify it, return repr(item)."""

    if type(item) == dict:
        if "tag" in item:
            if "level" in item:
                kind = "tagDisplay"
            elif "topicCode" in item:
                kind = "subtopic"
            else:
                kind = "tag"
            return(f"{kind}({repr(item['tag'])})")

        event = session = fileNumber = None
        args = []
        if "code" in item and "subtitle" in item:
            kind = "event"
            event = item["code"]
        elif "sessionTitle" in item:
            kind = "session"
            event = item["event"]
            session = item["sessionNumber"]
        elif "kind" in item and "flags" in item:
            if "annotations" in item:
                kind = "excerpt"
                event = item["event"]
                session = item["sessionNumber"]
                fileNumber = item.get("fileNumber",None)
            else:
                kind = "annotation"
                x = FindOwningExcerpt(item)
                if x:
                    event = x["event"]
                    session = x["sessionNumber"]
                    fileNumber = x["fileNumber"]
            args = [item['kind'],Utils.EllideText(item['text'],maxLength=70)]
        elif "pdfPageOffset" in item:
            kind = "reference"
            args.append(item["abbreviation"])
        elif "url" in item:
            kind = "audioSource"
            args = [item["event"],item["filename"]]
        elif "subtopics" in item:
            kind = "keyTopic"
            args = [item["code"]]
        else:
            return(repr(item))

        if event:
            name = event
            if session is not None:
                name += f"_S{session:02d}"
            if fileNumber is not None:
                name += f"_F{fileNumber:02d}"
            args = [name] + args

        return f"{kind}({', '.join(repr(i) for i in args)})"
    else:
        return repr(item)


def ChildAnnotations(excerpt: dict,annotation: dict|None = None) -> list[dict]:
    """Return the annotations that are directly under this annotation or excerpt."""

    if annotation is excerpt:
        scanLevel = 1
        scanning = True
    else:
        scanLevel = annotation["indentLevel"] + 1
        scanning = False

    children = []
    for a in excerpt["annotations"]:
        if scanning:
            if a["indentLevel"] == scanLevel:
                children.append(a)
            elif a["indentLevel"] < scanLevel:
                scanning = False
                break
        elif a is annotation:
            scanning = True

    return children


def SubAnnotations(excerpt: dict,annotation: dict|None = None) -> list[dict]:
    """Return all annotations contained by this excerpt or annotation."""

    if annotation is excerpt:
        scanLevel = 1
        scanning = True
    else:
        scanLevel = annotation["indentLevel"] + 1
        scanning = False

    subs = []
    for a in excerpt["annotations"]:
        if scanning:
            if a["indentLevel"] >= scanLevel:
                subs.append(a)
            else:
                break
        elif a is annotation:
            scanning = True

    return subs


def ParentAnnotation(excerpt: dict,annotation: dict) -> dict|None:
    """Return this annotation's parent."""
    if not annotation or annotation is excerpt:
        return None
    if annotation["indentLevel"] == 1:
        return excerpt
    searchForLevel = 0
    found = False
    for searchAnnotation in reversed(excerpt["annotations"]):
        if searchAnnotation["indentLevel"] <= searchForLevel:
            if searchAnnotation["indentLevel"] < searchForLevel:
                Alert.error("Annotation",annotation,f"doesn't have a parent at level {searchForLevel}. Returning prior annotation at level {searchAnnotation['indentLevel']}.")
            return searchAnnotation
        if searchAnnotation is annotation:
            searchForLevel = annotation["indentLevel"] - 1
    if not found:
        Alert.error("Annotation",annotation,"doesn't have a proper parent.")
        return None


def SubsumesTags() -> dict:
    """Inverts gDatabase["tagSubsumed"] to create a dictionary of which tags a tag subsumes."""

    subsumesTags:dict[str,list[dict]] = {}

    for subsumedTag in gDatabase["tagSubsumed"].values():
        subsumesTags[subsumedTag["subsumedUnder"]] = subsumesTags.get(subsumedTag["subsumedUnder"],[]) + [subsumedTag]

    return subsumesTags

def SubtagIterator(tagOrSubtopic:dict[str]) -> Iterable[str]:
    "Yield the subtags of a subtopic or the tag of a tag."
    yield tagOrSubtopic["tag"]
    if "topicCode" in tagOrSubtopic:
        yield from tagOrSubtopic.get("subtags",())

def FTagAndOrder(excerpt: dict,fTags: Iterable[str]) -> tuple[str,int,str]:
    """Return the tuple (fTag,fTagOrder,fTagOrderFlag) for the first matching fTag in fTags."""
    
    for tag in fTags:
        try:
            fTagIndex = excerpt["fTags"].index(tag)
            return excerpt["fTags"][fTagIndex],excerpt["fTagOrder"][fTagIndex],excerpt["fTagOrderFlags"][fTagIndex]
        except (ValueError, IndexError):
            pass
    return "",999,""

def FTagOrder(excerpt: dict,fTags: Iterable[str]) -> int:
    """Return fTagOrder of the first matching fTag in fTags."""
    
    return FTagAndOrder(excerpt,fTags)[1]


    
