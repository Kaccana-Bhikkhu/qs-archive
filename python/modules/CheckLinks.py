"""Check links in the documentation and events directories using BeautifulSoup.
"""

from __future__ import annotations

import os
import Utils, Alert, Link
from typing import NamedTuple, Iterable
from bs4 import BeautifulSoup
import urllib.error, urllib.parse

class UrlInfo(NamedTuple):
    """Information about a given URL."""
    good: bool              # Can we read the URL?
    bookmarks: list[str]    # A list of linkable items

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
        urls = [linkItem.get("href") for linkItem in linkItems] + [srcItem.get("src") for srcItem in srcItems]
        for link in urls:
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

def CheckUrl(url:str) -> UrlInfo:
    """Check a URL if we haven't already done so."""
    if url in gCheckedUrl:
        return gCheckedUrl[url]
    
    parsed = urllib.parse.urlparse(url)
    htmlFile = parsed.path.lower().endswith(".html")
    fragmentToCheck = parsed.fragment
    if fragmentToCheck == "_keep_scroll":
        fragmentToCheck = ""
    url = urllib.parse.urlunparse(parsed._replace(fragment=""))

    try:
        with Utils.OpenUrlOrFile(url) as page:
            if htmlFile and fragmentToCheck:
                soup = BeautifulSoup(page,"html.parser")
                idItems = soup.find_all(id=True)
                bookmarks = set(item.get("id") for item in idItems)
                if fragmentToCheck not in bookmarks:
                    Alert.warning("Cannot find bookmark","#" + fragmentToCheck,"in",url)
                result = UrlInfo(good=True,bookmarks=bookmarks)
            else:
                result = UrlInfo(good=True,bookmarks=[])
            # Alert.info("Successfully opended",url)
    except (OSError,urllib.error.HTTPError) as error:
        Alert.warning("Error",error,"when trying to access",url)
        result = UrlInfo(good=False,bookmarks=[])
    
    gCheckedUrl[url] = result
    return result

def CheckUrls(urls: Iterable[str]) -> None:
    """Check a list of urls to see if they are valid."""
    with Utils.ConditionalThreader() as pool:
        for url in urls:
            pool.submit(CheckUrl,url)

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
    urlsToCheck = set()
    for url in aboutUrls:
        urlsToCheck.update(ScanPageForLinks(url))
    
    Alert.info(len(urlsToCheck),"urls to check.")
    CheckUrls(urlsToCheck)

    Alert.info("Checking event pages...")
    eventUrls = GetEventLinks()
    urlsToCheck = set()
    for url in eventUrls:
        urlsToCheck.update(ScanPageForLinks(url))
    
    Alert.info(len(urlsToCheck),"urls to check.")
    CheckUrls(urlsToCheck)
    
