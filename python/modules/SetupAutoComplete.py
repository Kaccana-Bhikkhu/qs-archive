"""A template for creating new modules.
"""

from __future__ import annotations

import os,json,itertools,re
import Utils, Alert, Database
from typing import TypedDict, Iterable
from Build import FA_STAR

class AutoCompleteEntry(TypedDict):
    long: str           # The long (or only) entry, e.g. Ajahn Chah Subadho
    short: str          # The shorter tag or name, e.g. Ajahn Chah
    number: str         # Digit(s) associated with this entry; e.g. Four Noble Truths
    link: str           # Link to page, e.g. teachers/ajahn-chah.html
    icon: str           # Icon to display to the left of the auto complete entry
    suffix: str         # Text to display after the entry

numberNames = {3:"three", 4:"four", 5:"five", 6:"six", 7:"seven", 8:"eight",
               9:"nine", 10:"ten", 12: "twelve"}
numberRegex:dict[int,re.Pattern] = {n:re.compile(r"\b"+string,re.IGNORECASE) for n,string in numberNames.items()}

def NumberFromText(text:str) -> int|None:
    "Scan text to see if it contains a number. Only look for numbers which are used"
    for n,regex in numberRegex.items():
        if regex.search(text):
            return n
    return None

def Entry(long: str,link: str,short: str = "", number: int = None,icon: str = "",suffix:str = "") -> AutoCompleteEntry:
    "Return an AutoCompleteEntry corresponding to these parameters."
    number = "" if number is None else str(number)
    return dict(long=long,link=link,short=short,number=number,icon=icon,suffix=suffix)

def KeyTopicEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries for the key topics"
    for topic in gDatabase["keyTopic"].values():
        yield Entry(topic["topic"],Utils.PosixJoin("topics",topic["listFile"]),
                    icon="book-open",suffix = f"({topic['fTagCount']}{FA_STAR})",
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

        suffix = f"({subtopic['excerptCount']})"
        if pali:
            suffix = f"({pali}) {suffix}"
        yield Entry(text,subtopic["htmlPath"],
                    icon = '<img src="images/icons/Cluster.png" class="list-icon">' if isCluster else "tag",
                    suffix = suffix,
                    number=NumberFromText(text))

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
    entrySources = [KeyTopicEntries(),SutopicEntries()]
    newDatabase:list[AutoCompleteEntry] = list(itertools.chain.from_iterable(entrySources))

    filename = gOptions.autoCompleteDatabase
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(newDatabase, file, ensure_ascii=False, indent=2)
        Alert.info(f"Wrote {len(newDatabase)} auto complete entries to {filename}.")
        return True
    except OSError as err:
        Alert.error(f"Could not write {filename} due to {err}")
        return False
    
    """

    blankEntry = dict.fromkeys(["topic","subtopic","tag","event","teacher"],"")

    def AddEntry(kind: str,entry: str,link: str) -> None:
        "Add an entry to the auto complete database"
        newDatabase["entries"].append(blankEntry | {kind:entry})
        newDatabase["pageLinks"][kind + "_" + entry] = link

    for topic in gDatabase["keyTopic"].values():
        AddEntry("topic",topic["topic"],Utils.PosixJoin("topics",topic["listFile"]))

    for subtopic in gDatabase["subtopic"].values():
        AddEntry("subtopic",subtopic["displayAs"],subtopic["htmlPath"])

    for tag in gDatabase["tag"].values():
        if tag["htmlFile"]:
            AddEntry("tag",tag["tag"],Utils.PosixJoin("tags",tag["htmlFile"]))
    
    for event in gDatabase["event"].values():
        AddEntry("event",event["title"],Database.EventLink(event["code"]).replace("../",""))
            # Eliminate the leading ../ in the path returned by EventLink

    for teacher in gDatabase["teacher"].values():
        if teacher["htmlFile"]:
            AddEntry("teacher",teacher["attributionName"],Utils.PosixJoin("teachers",teacher["htmlFile"]))
"""
