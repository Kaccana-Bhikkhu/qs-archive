"""A template for creating new modules.
"""

from __future__ import annotations

import os,json,itertools,re
import Utils, Alert, Database
from typing import TypedDict, Iterable
from Build import FA_STAR, RemoveLanguageTag
from ParseCSV import TagFlag

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

def Entry(short: str,link: str,long: str = "", number: int = None,icon: str = "",suffix:str = "") -> AutoCompleteEntry:
    "Return an AutoCompleteEntry corresponding to these parameters."
    number = "" if number is None else str(number)
    return dict(short=short,link=link,long=long,number=number,icon=icon,suffix=suffix)

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

        if pali:
            text += f" ({pali})"

        suffix = f"({subtopic['excerptCount']})"
        yield Entry(text,subtopic["htmlPath"],
                    icon = '<img src="images/icons/Cluster.png" class="list-icon">' if isCluster else "tag",
                    suffix = suffix,
                    number=NumberFromText(text))

def TagEntries() -> Iterable[AutoCompleteEntry]:
    "Yield auto complete entries for tags"

    tagIcon = '<i class="inline-icon" data-lucide="tag"></i>'
    tags = [t for t in gDatabase["tag"].values()
                 if t["htmlFile"] and t.get("excerptCount",0) and not TagFlag.HIDE in t["flags"]]
    tags = sorted(tags,key = lambda t: t["listIndex"])

    # First yield basic tag information
    for tag in tags:
        short = suffix = ""
        long = RemoveLanguageTag(tag["fullTag"])
        longPali = RemoveLanguageTag(tag["fullPali"])
        if tag["fullPali"] and longPali != long:
            long += f" ({longPali})"
        elif TagFlag.DISPLAY_GLOSS in tag["flags"]:
            long += f" ({tag['glosses'][0]})"
        
        if tag["fullTag"] != tag["tag"]:
            short = RemoveLanguageTag(tag["tag"])
            shortPali = RemoveLanguageTag(tag["pali"])
            if tag["pali"] and shortPali != short:
                short += f" ({shortPali})"
            elif TagFlag.DISPLAY_GLOSS in tag["flags"]:
                short += f" ({tag['glosses'][0]})"

        yield Entry(long = long,
                    short = short,
                    link = Utils.PosixJoin("tags",tag["htmlFile"]),
                    icon="tag",suffix = f"({tag['excerptCount']})",
                    number=tag["number"])
    
    # Yield alternate translations
    for tag in tags:
        for translation in tag["alternateTranslations"]:
            yield Entry(RemoveLanguageTag(translation),Utils.PosixJoin("tags",tag["htmlFile"]),
                suffix=f" – <i>alt. trans. of</i> <b>{RemoveLanguageTag(tag['pali'])}</b>")
    
    # Yield glosses
    for tag in tags:
        for gloss in tag["glosses"]:
            yield Entry(RemoveLanguageTag(gloss),Utils.PosixJoin("tags",tag["htmlFile"]),
                suffix=f' – see {tagIcon} {RemoveLanguageTag(tag['tag'])}')
    
            

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
    entrySources = [KeyTopicEntries(),SutopicEntries(),TagEntries()]
    #entrySources = [TagEntries()]
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
