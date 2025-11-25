"""Check links in the documentation and events directories using BeautifulSoup.
"""

from __future__ import annotations

import os
import re
import Utils, Alert, Link
from typing import NamedTuple, Iterable
from bs4 import BeautifulSoup
import urllib.error, urllib.parse
from collections import defaultdict
import itertools

class UrlInfo(NamedTuple):
    """Information about a given URL."""
    good: bool              # Can we read the URL?

gCheckedUrl:dict[str,UrlInfo] = {}
"""Dictionary of urls we have checked already."""

def GetEventLinks() -> list[str]:
    """Return a list of urls for events."""
    return [Utils.PosixJoin(gOptions.mirrorUrl[gOptions.linkCheckMirror],gOptions.pagesDir,"events",eventCode + ".html") for eventCode in gDatabase["event"]]

def ScanPageForLinks(url: str) -> list[str]:
    """Scan the page url and return a list of all links."""
    if gOptions.uploadMirror != "local":
        uploadMirrorUrl = gOptions.mirrorUrl[gOptions.uploadMirror]
    else:
        uploadMirrorUrl = "@!None"
    urlsToCheck = set()
    with Utils.OpenUrlOrFile(url) as page:
        soup = BeautifulSoup(page,"html.parser")
        idsInPage = set(item.get("id") for item in soup.find_all(id=True))

        linkItems = soup.find_all("a")
        srcItems = soup.find_all(src=True)
        for link in itertools.chain(
            (linkItem.get("href") for linkItem in linkItems),
            (linkItem.get("data-alt-href") for linkItem in linkItems if "data-alt-href" in linkItem.attrs),
            (srcItem.get("src") for srcItem in srcItems)
        ):
            if link.startswith(uploadMirrorUrl):
                urlsToCheck.add(link.replace(uploadMirrorUrl,gOptions.mirrorUrl["local"]))
                continue
                    # Convert links to the upload mirror to equivalent local files
            parsed = urllib.parse.urlparse(link)
            if parsed.path:
                if parsed.scheme: # A remote hyperlink
                    if parsed.scheme.lower().startswith("http"): # Don't check mailto:, etc.
                        urlsToCheck.add(link)
                else: # Local file reference
                    parsed = parsed._replace(query="")
                    urlsToCheck.add(urllib.parse.urljoin(url,parsed.geturl()))
            else: # Link to a bookmark in this page
                if parsed.fragment:
                    if parsed.fragment not in idsInPage:
                        Alert.warning(f"Cannot resolve local bookmark link #{parsed.fragment} in {url}.")
    
    return urlsToCheck

def CheckFileCase(posixPath: str):
    """Check for case inconsistencies in posixPath relative to the (potentially case-insensiteve) local file system."""

    posixParts = posixPath.split("/")
    realParts = re.split(r"[\\/]",os.path.realpath(posixPath))

    for p,r in zip(reversed(posixParts),reversed(realParts)):
        if p != r and p != "." and r != ".":
            Alert.warning("Case mismatch between URL",posixPath,"and file on disk",os.path.realpath(posixPath))
            print("path:",p)
            print("disk:",r)
            return

def CheckUrl(linkTo:str,linkFrom: list[str],bookmarksToPage: list[str]) -> UrlInfo:
    """Check a URL if we haven't already done so."""
    if linkTo in gCheckedUrl:
        return gCheckedUrl[linkTo]
    
    parsed = urllib.parse.urlparse(linkTo)
    htmlFile = parsed.path.lower().endswith(".html")

    try:
        if not Utils.RemoteURL(linkTo):
            CheckFileCase(linkTo)
        with Utils.OpenUrlOrFile(linkTo) as page:
            if htmlFile and bookmarksToPage:
                soup = BeautifulSoup(page,"html.parser")
                idItems = soup.find_all(id=True)
                bookmarks = set(item.get("id") for item in idItems)
                for bookmarkToCheck in bookmarksToPage:
                    if bookmarkToCheck not in bookmarks:
                        Alert.warning("Cannot find bookmark","#" + bookmarkToCheck,"in",linkTo,"; linked from",linkFrom)
                result = UrlInfo(good=True)
            else:
                result = UrlInfo(good=True)
            Alert.debug("Successfully opended",linkTo)
    except (OSError,urllib.error.HTTPError) as error:
        Alert.warning("Error",error,"when trying to access",linkTo,"; linked from",linkFrom)
        result = UrlInfo(good=False)
    
    gCheckedUrl[linkTo] = result
    return result

class LinkInfo:
    linkFrom: list[str]
    bookmarks: list[str]

    def __init__(self):
        self.linkFrom = []
        self.bookmarks = []

    def Append(self,linkFrom: str,bookmark: str) -> None:
        Utils.ExtendUnique(self.linkFrom,linkFrom)
        if bookmark and bookmark not in self.bookmarks:
            self.bookmarks.append(bookmark)

def CheckUrls(urls: dict[str,list[str]]) -> None:
    """Check a list of urls to see if they are valid."""
    urlsWithBookmarks = defaultdict(LinkInfo)
    for linkTo,linkFrom in urls.items():
        parsed = urllib.parse.urlparse(linkTo)
        bookmark = parsed.fragment
        if bookmark == "_keep_scroll":
            bookmark = ""
        linkTo = urllib.parse.urlunparse(parsed._replace(fragment=""))
        urlsWithBookmarks[linkTo].Append(linkFrom,bookmark)

    with Utils.ConditionalThreader() as pool:
        for linkTo,linkInfo in urlsWithBookmarks.items():
            pool.submit(CheckUrl,linkTo,linkInfo.linkFrom,linkInfo.bookmarks)

def CheckLinksInPages(pages: Iterable[str]) -> None:
    urlsToCheck = defaultdict(list)
    for page in pages:
        for link in ScanPageForLinks(page):
            urlsToCheck[link].append(page)
    
    Alert.info(len(urlsToCheck),"urls to check.")
    CheckUrls(urlsToCheck)

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument("--linkCheckMirror",type=str,default="local",help="Check links in this mirror; default: local")

def ParseArguments() -> None:
    gOptions.linkCheckMirror = Link.CheckMirrorName(Link.ItemType.EXCERPT,gOptions.linkCheckMirror)
    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main() -> None:
    Alert.info("Checking about pages...")
    aboutUrls = [filename for filename in os.listdir(Utils.PosixJoin(gOptions.pagesDir,"about")) if filename.lower().endswith(".html")]
    aboutUrls = [Utils.PosixJoin(gOptions.pagesDir,"homepage.html")] + \
        [Utils.PosixJoin(gOptions.pagesDir,"about",filename) for filename in aboutUrls]
    CheckLinksInPages(aboutUrls)

    Alert.info("Checking dispatch pages...")
    dispatchUrls = [filename for filename in os.listdir(Utils.PosixJoin(gOptions.pagesDir,"dispatch")) if filename.lower().endswith(".html")]
    dispatchUrls = [Utils.PosixJoin(gOptions.pagesDir,"dispatch",filename) for filename in dispatchUrls]
    CheckLinksInPages(dispatchUrls)

    Alert.info("Checking extra book links...")
    bookUrls = defaultdict(list)
    for book in gDatabase["reference"].values():
        if book["otherUrl"]:
            bookUrls[book["otherUrl"]].append(book["abbreviation"])
    Alert.info(len(bookUrls),"urls to check.")
    CheckUrls(bookUrls)

    Alert.info("Checking event pages...")
    CheckLinksInPages(GetEventLinks())
    
