"""A template for creating new modules.
"""

from __future__ import annotations

import os,json
import Utils, Alert, Database
from typing import TypedDict, Iterable

class AutoCompleteDatabase(TypedDict):
    entries: list[dict[str,str]]    # The list of auto complete entries;
                                    # Each item is a single-entry dict of the form
                                    # kind:entry, e.g. "teacher":"Ajahn Pasanno"
    pageLinks: dict[str,str]        # Keys concatenate entries with _
                                    # Values are the page to link to
                                    # e.g. "teacher_Ajahn Pasanno":"teachers/ajahn-pasanno.html"

    


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
    newDatabase:AutoCompleteDatabase = {
        "entries": [],
        "pageLinks": {}
    }

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

    filename = gOptions.autoCompleteDatabase
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(newDatabase, file, ensure_ascii=False, indent=2)
        Alert.info(f"Wrote auto complete database to {filename}.")
        return True
    except OSError as err:
        Alert.error(f"Could not write {filename} due to {err}")
        return False
