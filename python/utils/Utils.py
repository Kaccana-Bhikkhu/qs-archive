"""Utility files to support QAarchive.py modules"""

from __future__ import annotations

from datetime import timedelta, datetime
import copy
import re, os,argparse
from urllib.parse import urlparse
from typing import BinaryIO
import Alert
import pathlib, posixpath
from collections import Counter
from collections.abc import Iterable
from urllib.parse import urljoin,urlparse,quote,urlunparse
import urllib.request, urllib.error
from DjangoTextUtils import slugify, RemoveDiacritics
from concurrent.futures import ThreadPoolExecutor

gOptions = None

def Contents(container:list|dict) -> list:
    try:
        return container.values()
    except AttributeError:
        return container

def ExtendUnique(dest: list, source: Iterable) -> list:
    "Append all the items in source to dest, preserving order but eliminating duplicates."

    destSet = set(dest)
    for item in source:
        if item not in destSet:
            dest.append(item)
    return dest

def Duplicates(source: Iterable) -> list:
    "Return a list of the items which appear more than once in source."
    itemCount = Counter(source)
    return [item for item,count in itemCount.items() if count > 1]

def PosixToNative(path:str) -> str:
    return str(pathlib.PurePath(pathlib.PurePosixPath(path)))

PosixJoin = posixpath.join
PosixSplit = posixpath.split

def RemoveHtmlTags(html: str) -> str:
    return re.sub(r"\<[^>]*\>","",html)

def DirectoryURL(url:str) -> str:
    "Ensure that this url specifies a directory path."
    if url.endswith("/"):
        return url
    else:
        return url + "/"

def RemoteURL(url:str) -> bool:
    "Does this point to a remote file server?"
    return bool(urlparse(url).netloc)

def QuotePath(url:str) -> str:
    """If the path section of url contains any % characters, assume it's already been quoted.
    Otherwise quote it."""

    parsed = urlparse(url)
    if "%" in parsed.path:
        return url
    else:
        return urlunparse(parsed._replace(path=quote(parsed.path)))

def OpenUrlOrFile(url:str) -> BinaryIO:
    """Determine whether url represents a remote URL or local file, open it for reading, and return a handle."""
    
    if RemoteURL(url):
        url = QuotePath(url)
        return urllib.request.urlopen(url)
    else:
        return open(url,"rb")

def JavascriptLink(url:str) -> str:
    "Return Javascript code to jump to url."

    return f"location.hash = '#{url}'"

def ReadFile(filePath: str) -> str:
    "Return an entire file as a utf-8 encoded string."
    with open(filePath,encoding='utf8') as file:
        return file.read()

def SwitchedMoveFile(locationFalse: str,locationTrue: str,switch: bool) -> bool:
    """Move a file to either locationFalse or locationTrue depending on the value of switch.
    Raise FileExistsError if both locations are occupied.
    Return True if the file was moved."""
    if switch:
        moveTo,moveFrom = locationTrue,locationFalse
    else:
        moveTo,moveFrom = locationFalse,locationTrue
    
    if os.path.isfile(moveFrom):
        if os.path.isfile(moveTo):
            raise FileExistsError(f"Cannot move {moveFrom} to overwrite {moveTo}.")
        os.makedirs(PosixSplit(moveTo)[0],exist_ok=True)
        os.rename(moveFrom,moveTo)
        return True
    return False

def MoveFile(fromPath: str,toPath: str) -> bool:
    return SwitchedMoveFile(fromPath,toPath,True)

def RemoveEmptyFolders(root: str) -> set[str]:
    # From https://stackoverflow.com/questions/47093561/remove-empty-folders-python
    deleted = set()
    for current_dir, subdirs, files in os.walk(root, topdown=False):

        still_has_subdirs = False
        for subdir in subdirs:
            if os.path.join(current_dir, subdir) not in deleted:
                still_has_subdirs = True
                break
    
        if not any(files) and not still_has_subdirs:
            try:
                os.rmdir(current_dir)
                deleted.add(current_dir)
            except OSError:
                pass

    return deleted

def ReplaceExtension(filename:str, newExt: str) -> str:
    "Replace the extension of filename before the file extension"
    name,_ = os.path.splitext(filename)
    return name + newExt

def AppendToFilename(filename:str, appendStr: str) -> str:
    "Append to fileName before the file extension"
    name,ext = os.path.splitext(filename)
    return name + appendStr + ext

def AboutPageLookup(pageName:str,aboutPageCache:dict = {}) -> str|None:
    "Search for an about page based on its name. Return the path to the page relative to prototypeDir."

    if not aboutPageCache: # modify the value of a default argument to create a cache of potential tag references
        dirs = ["about"]
        for dir in dirs:
            fileList = os.listdir(PosixJoin(gOptions.prototypeDir,dir))
            for file in fileList:
                m = re.match(r"[0-9]*_?(.*)\.html",file)
                if m:
                    aboutPageCache[m[1].lower()] = PosixJoin(dir,m[0])

    return aboutPageCache.get(pageName.lower().replace(" ","-"),None)

def Singular(noun: str) -> str:
    "Use simple rules to guess the singular form or a noun."
    if noun.endswith("ies"):
        return noun[:-3] + "y"
    else:
        return noun.rstrip("s")

def EllideText(s: str,maxLength = 50) -> str:
    "Truncate a string to keep the number of characters under maxLength."
    if len(s) <= maxLength:
        return s
    else:
        return s[:maxLength - 3] + "..."

def SmartQuotes(s: str):
    """Takes a string and returns it with dumb quotes, single and double,
    replaced by smart quotes. Accounts for the possibility of HTML tags
    within the string.
    Based on https://gist.github.com/davidtheclark/5521432"""

    # Find dumb double quotes coming directly after letters or punctuation,
    # and replace them with right double quotes.
    s = re.sub(r'([a-zA-Z0-9.,?!;:)>%/\'\"])"', r'\1”', s)
    # Find any remaining dumb double quotes and replace them with
    # left double quotes.
    s = s.replace('"', '“')
    # Reverse: Find any SMART quotes that have been (mistakenly) placed around HTML
    # attributes (following =) and replace them with dumb quotes.
    s = re.sub(r'=“(.*?)”', r'="\1"', s)
    # Follow the same process with dumb/smart single quotes
    s = re.sub(r"([a-zA-Z0-9.,?!;:)>%/\"\'])'", r'\1’', s)
    s = s.replace("'", '‘')
    s = re.sub(r'=‘(.*?)’', r"='\1'", s)
    return s

def ParseDate(dateStr:str) -> datetime.date:
    "Read a date formated as DD/MM/YYYY and return datetime.date."
    
    return datetime.strptime(dateStr,"%d/%m/%Y").date()

def ReformatDate(dateStr:str,fullMonth:bool = False) -> str:
    "Take a date formated as DD/MM/YYYY and reformat it as mmm d YYYY."
    
    date = ParseDate(dateStr)
    
    return f'{date.strftime("%B" if fullMonth else "%b.")} {int(date.day)}, {int(date.year)}'

def ModificationDate(file:str) -> datetime:
    info = os.stat(file)
    return datetime.fromtimestamp(info.st_mtime)

def DependenciesModified(file:str,dependencies:Iterable[str]) -> bool:
    """Returns true if any of the file paths specified in dependencies has a later modification date than file."""

    try:
        fileDate = ModificationDate(file)
        for d in dependencies:
            if ModificationDate(d) >= fileDate:
                return True
        return False
    except FileNotFoundError:
        return True

def SessionIndex(sessions:list, event:str ,sessionNum: int) -> int:
    "Return the session specified by event and sessionNum."
    
    for n,session in enumerate(sessions):
        if session["event"] == event and session["sessionNumber"] == sessionNum:
            return n
    
    raise ValueError(f"Can't locate session {sessionNum} of event {event}")

def RegexMatchAny(strings: Iterable[str],capturingGroup = True,literal = False):
    """Return a regular expression that matches any item in strings.
    Optionally make it a capturing group."""

    if literal:
        strings = [re.escape(s) for s in strings]
    else:
        strings = list(strings)
    if strings:
        if capturingGroup:
            return r"(" + r"|".join(strings) + r")"
        else:
            return r"(?:" + r"|".join(strings) + r")"
    else:
        return r'^a\bc' # Looking for a word boundary between text characters always fails: https://stackoverflow.com/questions/1723182/a-regex-that-will-never-be-matched-by-anything


def ReorderKeys(ioDict: dict,firstKeys = [],lastKeys = []) -> None:
    "Reorder the keys in ioDict"

    spareDict = copy.copy(ioDict) # Make a shallow copy
    ioDict.clear()

    for key in firstKeys:
        ioDict[key] = spareDict.pop(key)

    for key in spareDict:
        if key not in lastKeys:
            ioDict[key] = spareDict[key]

    for key in lastKeys:
        ioDict[key] = spareDict[key]

def SummarizeDict(d: dict,printer: Alert.AlertClass) -> None:
    "Print a summary of dict d, one line per key."
    for key,value in d.items():
        desc = f"{key}: {value.__class__.__name__}"
        try:
            desc += f"[{len(value)}]"
        except TypeError:
            pass
        printer(desc)

class MockFuture():
    def __init__(self, result) -> None:
        self.result = result
    def result(self, timeout=None):
        return self.result
    def cancel(self):
        pass

class MockThreadPoolExecutor():
    """Don't execute any threads for testing purposes.
    https://stackoverflow.com/questions/10434593/dummyexecutor-for-pythons-futures"""
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def submit(self, fn, *args, **kwargs):
        # execute functions in series without creating threads
        # for easier unit testing
        result = fn(*args, **kwargs)
        return MockFuture(result)

    def shutdown(self, wait=True):
        pass

def ConditionalThreader() -> ThreadPoolExecutor|MockThreadPoolExecutor:
    return ThreadPoolExecutor() if gOptions.multithread else MockThreadPoolExecutor()

try:
    STORE_TRUE = dict(action=argparse.BooleanOptionalAction,default=False)
except AttributeError:
    STORE_TRUE = dict(action="store_true")