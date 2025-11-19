"""A template for creating new modules.
"""

from __future__ import annotations

import os,json,itertools,re
import Utils, Alert, Database
from typing import TypedDict, Iterable
from Build import FA_STAR, RemoveLanguageTag, HtmlIcon
from ParseCSV import TagFlag
import BuildReferences, Suttaplex
from bs4 import BeautifulSoup


class AutoCompleteEntry(TypedDict):
    long: str           # The long (or only) entry, e.g. Ajahn Chah Subadho
    short: str          # The shorter tag or name, e.g. Ajahn Chah
    number: str         # Digit(s) associated with this entry; e.g. Four Noble Truths
    link: str           # Link to page, e.g. teachers/ajahn-chah.html
    icon: str           # Icon to display to the left of the auto complete entry
    suffix: str         # Text to display after the entry
    excerptCount: int   # The number of excerpts on this page

numberNames = {3:"three", 4:"four", 5:"five", 6:"six", 7:"seven", 8:"eight",
               9:"nine", 10:"ten", 12: "twelve"}
numberRegex:dict[int,re.Pattern] = {n:re.compile(r"\b"+string,re.IGNORECASE) for n,string in numberNames.items()}

def NumberFromText(text:str) -> int|None:
    "Scan text to see if it contains a number. Only look for numbers which are used"
    for n,regex in numberRegex.items():
        if regex.search(text):
            return n
    return None

def Entry(short: str,link: str,long: str = "", number: int = None,icon: str = "",suffix:str = "",excerptCount:int = 0) -> AutoCompleteEntry:
    "Return an AutoCompleteEntry corresponding to these parameters."
    number = "" if number is None else str(number)
    return dict(short=short,link=link,long=long,number=number,icon=HtmlIcon(icon,directoryDepth=0),suffix=suffix,excerptCount=excerptCount)

def KeyTopicEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries for the key topics"
    for topic in gDatabase["keyTopic"].values():
        yield Entry(topic["topic"],Utils.PosixJoin("topics",topic["listFile"]),
                    icon="Key.png",suffix = f"({topic['fTagCount']}{FA_STAR})",
                    number=NumberFromText(topic["topic"]))

def SutopicEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries for subtopics"
    for subtopic in gDatabase["subtopic"].values():
        if subtopic["autoComplete"] == "Display":
            text = subtopic["displayAs"]
            pali = subtopic["pali"]
        else:
            text = subtopic["tag"]
            pali = gDatabase["tag"][subtopic["tag"]]["pali"]
        isCluster = bool(subtopic["subtags"])

        if pali:
            text += f" ({pali})"

        yield Entry(text,subtopic["htmlPath"],
                    icon = "Cluster.png" if isCluster else "tag",
                    excerptCount = subtopic['excerptCount'],
                    number=NumberFromText(text))

def TagEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries for tags"

    tagIcon = '<i class="inline-icon" data-lucide="tag"></i>'
    tags = [t for t in gDatabase["tag"].values()
                 if t["htmlFile"] and t.get("excerptCount",0) and not TagFlag.HIDE in t["flags"]]
    tags = sorted(tags,key = lambda t: t["listIndex"])

    def TagEntry(tag:dict) -> AutoCompleteEntry:
        "Returns an entry for this tag."
        short = RemoveLanguageTag(tag["tag"])
        shortPali = RemoveLanguageTag(tag["pali"])
        if tag["pali"] and shortPali != short:
            short += f" ({shortPali})"
        elif TagFlag.DISPLAY_GLOSS in tag["flags"]:
            short += f" ({tag['glosses'][0]})"
        
        long = ""
        if tag["fullTag"] != tag["tag"]:
            long = RemoveLanguageTag(tag["fullTag"])
            longPali = RemoveLanguageTag(tag["fullPali"])
            if tag["fullPali"] and longPali != long:
                long += f" ({longPali})"
            elif TagFlag.DISPLAY_GLOSS in tag["flags"]:
                long += f" ({tag['glosses'][0]})"

        return Entry(short = short,
                    long = long,
                    link = Utils.PosixJoin("tags",tag.get("htmlFile","")),
                    icon="tag",excerptCount=tag.get('excerptCount',0),
                    number=tag["number"])
        
    # First yield basic tag information
    for tag in tags:
        yield TagEntry(tag)

    # Yield glosses and alternate translations
    for tag in tags:
        for gloss in tag["glosses"] + tag["alternateTranslations"]:
            yield Entry(RemoveLanguageTag(gloss),Utils.PosixJoin("tags",tag["htmlFile"]),
                suffix=f" – see {tagIcon} {RemoveLanguageTag(tag['tag'])} ({tag['excerptCount']})")

    # Yield subsumed tags
    for subsumedTag in gDatabase["tagSubsumed"].values():
        if TagFlag.HIDE in subsumedTag["flags"]:
            continue
        
        subsumedUnder = gDatabase["tag"][subsumedTag["subsumedUnder"]]

        subsumedEntry = TagEntry(subsumedTag)
        subsumedEntry["icon"] = ""
        subsumedEntry["link"] = Utils.PosixJoin("tags",subsumedUnder["htmlFile"])
        subsumedEntry["suffix"] = f" – see {tagIcon} {RemoveLanguageTag(subsumedUnder['tag'])}"
        subsumedEntry["excerptCount"] = subsumedUnder['excerptCount']
        yield subsumedEntry

def EventEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries each event"
    for event in gDatabase["event"].values():
        yield Entry(Utils.RemoveHtmlTags(Database.ItemCitation(event)),
                    Database.EventLink(event["code"]).replace("../",""), # Eliminate the leading ../ in the path returned by EventLink
                    icon="calendar",
                    excerptCount=event["excerpts"])

def TeacherEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries for each teacher"
    for teacher in gDatabase["teacher"].values():
        if teacher["htmlFile"]:
            long = teacher["fullName"] if teacher["fullName"] != teacher["attributionName"] else ""
            yield Entry(teacher["attributionName"],
                        Utils.PosixJoin("teachers",teacher["htmlFile"]),
                        long = long,
                        icon="user",
                        excerptCount=teacher["excerptCount"])

def CategoryEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries for All Excerpts, All Stories, etc. pages"
    sitemap = Utils.ReadFile(Utils.PosixJoin(gOptions.pagesDir,"sitemap.html"))
    soup = BeautifulSoup(sitemap,"html.parser")
    links = soup.find_all("a")

    for link in links:
        href = link.get("href")
        text = link.get_text().strip()
        if "AllExcerpts" not in href:
            continue

        splitText = re.match(r"(.*) \(([0-9]+)\)$",text) # Split category and number
        text = splitText[1]

        if not text.startswith("All"):
            if text == "Featured":
                text = "All featured excerpts"
            else:
                text = "All " + text.lower()

        yield Entry(text,href,
                    excerptCount = int(splitText[2]),
                    icon="All.png")

def AboutEntries() -> Iterable[AutoCompleteEntry]:
    "Yield an entry for each about page by scanning Search-instructions.html for menu options"
    technicalAboutPage = Utils.ReadFile(Utils.PosixJoin(gOptions.pagesDir,"about","Search-instructions.html"))
    soup = BeautifulSoup(technicalAboutPage,"html.parser")
    menuOptions = soup.find_all("option")

    for option in menuOptions:
        filePath = option.get("value")
        text = option.get_text().strip()
        if text != "Technical":
            yield Entry("About: " + text,filePath,icon="text")

def TextEntries() -> Iterable[AutoCompleteEntry]:
    "Yield an entry for each about text (Sutta or Vinaya) referenced."
    
    BuildReferences.ReadReferenceDatabase()
    for text,textData in BuildReferences.gSavedReferences["text"].items():
        if re.search(r"[0-9]$",text): # Remove root text links
            uid = BuildReferences.TextReference.FromString(text).Uid()
            paliTitle = Suttaplex.Title(uid,translated=False)
            title = Suttaplex.Title(uid)
            combinedTitle = f"{paliTitle}: {title}" if (paliTitle and title) else paliTitle or title or ""
            yield Entry(text,textData["link"],icon="DhammaWheel.png",excerptCount=textData["count"],suffix=combinedTitle)

def BookEntries() -> Iterable[AutoCompleteEntry]:
    "Yield an entry for each about book referenced."
    
    BuildReferences.ReadReferenceDatabase()
    for book,bookData in BuildReferences.gSavedReferences["book"].items():
        reference = BuildReferences.BookReference.FromString(gDatabase["reference"][book]["abbreviation"])
        title = re.sub(r'["“”]',"",reference.TextTitle())
        yield Entry(title,bookData["link"],icon="book-open",excerptCount=bookData["count"])
    
def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--autoCompleteDatabase',type=str,default="pages/assets/AutoCompleteDatabase.json",help="AutoComplete database filename.")


def ParseArguments() -> None:
    pass    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main() -> None:
    entrySources = [KeyTopicEntries(),SutopicEntries(),TagEntries(),
                    EventEntries(),TeacherEntries(),CategoryEntries(),AboutEntries(),TextEntries(),BookEntries()]
    newDatabase:list[AutoCompleteEntry] = list(itertools.chain.from_iterable(entrySources))

    characters = set()
    for entry in newDatabase:
        characters.update(entry["long"])
        characters.update(entry["short"])
        characters.update(entry["number"])
    Alert.debug("Search string characters:","".join(sorted(characters)))

    filename = gOptions.autoCompleteDatabase
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(newDatabase, file, ensure_ascii=False, indent=2)
        Alert.info(f"Wrote {len(newDatabase)} auto complete entries to {filename}.")
        return True
    except OSError as err:
        Alert.error(f"Could not write {filename} due to {err}")
        return False
    