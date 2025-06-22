"""Maintain pages/assets/FeaturedDatabase.json, which contains rendered random featured excerpts to display on the homepage.
"""

from __future__ import annotations

import os, json, datetime, re
from datetime import timedelta
import random
from difflib import SequenceMatcher
from typing import Callable, TypedDict
import Utils, Alert, Build, Filter, Database
from copy import copy
import Filter
import Html2 as Html

# A submodule takes a string with its arguments and returns a bool indicating its status or None if the submodule doesn't run
SubmoduleType = Callable[[str],bool|None]
class ExcerptDict(TypedDict):
      text: str         # Text of the excerpt; used to identify this excerpt when its code changes
      fTags: list[str]  # The excerpt's fTags
      shortHtml: str    # Html code to render on the homepage
      html: str         # Html code to render on the daily featured excerpts page
    
class FeaturedDatabase(TypedDict):
    made: str                       # Date and time this database was first made in iso format
    updated: str                    # Date and time this database was last changed

    mirrors: dict[str,str]          # The dict of mirror names and URLs the last time this database was updated
    excerptSources: list[str]       # The list of mirrors used for excerpt mp3s
        # The above two items are important because the html must be re-rendered when the excerpt mirror changes
    
    excerpts: dict[str,ExcerptDict] # Details about the excerpts; keys are given by the excerpt codes

    startDate: str                  # The date to display the first exerpt in calendar in iso format
    calendar: list[str]             # The list of excerpt codes to display on each date

def ReadDatabase(backupNumber:int = 0) -> bool:
    """Read the featured excerpt database from disk.
    If backupNumber is given, read from the specified backup file or the lastest backup if -1."""
    global gFeaturedDatabase
    
    filename = gOptions.featuredDatabase
    try:
        with open(filename, 'r', encoding='utf-8') as file: # Otherwise read the database from disk
            gFeaturedDatabase = json.load(file)
        Alert.info(f"Read featured excerpt DB from {filename} with {len(gFeaturedDatabase['calendar'])} calendar entries.")
        return True
    except OSError as err:
        Alert.error(f"Could not read {gOptions.featuredDatabase} due to {err}")
        return False
    

def WriteDatabase(newDatabase: FeaturedDatabase) -> bool:
    """Write newDatabase to the random excerpt .json file"""
    filename = gOptions.featuredDatabase
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(newDatabase, file, ensure_ascii=False, indent=2)
        Alert.info(f"Wrote featured excerpt database to {filename}.")
        return True
    except OSError as err:
        Alert.error(f"Could not write {gOptions.featuredDatabase} due to {err}")
        return False
    

def PrintInfo(database: FeaturedDatabase) -> None:
    """Print information about this featured excerpt database."""
    Alert.info("Featured excerpt database contains",len(database["excerpts"]),"random excerpts.")

    calendarLength = len(database['calendar'])
    daysPast = (datetime.date.today() - datetime.date.fromisoformat(database["startDate"])).days

    Alert.info(f"Calendar length {calendarLength}; {daysPast} days of history; {calendarLength - daysPast - 1} excerpts remaining.")
    

def ParseNumericalParameter(parameter: str,defaultValue:int = 0) -> int:
    numberStr = re.search(r"[0-9]+",parameter)
    if numberStr:
        return int(numberStr[0])
    else:
        return defaultValue

def ExcerptEntry(excerpt:dict[str]) -> ExcerptDict:
    """Return a dictionary containing the information needed to display this excerpt on the front page."""
    
    formatter = Build.Formatter()
    formatter.SetHeaderlessFormat()
    formatter.excerptDefaultTeacher = {"AP"}
    formatter.excerptShowFragmentPlayers = False
    html = formatter.HtmlExcerptList([excerpt])

    simpleExcerpt = copy(excerpt)
    simpleExcerpt["annotations"] = ()
    simpleExcerpt["tags"] = ()
    shortHtml = formatter.FormatExcerpt(simpleExcerpt)
    keyTopicTags = Database.KeyTopicTags()
    topicTags = [tag for tag in excerpt["fTags"] if tag in keyTopicTags]

    if topicTags: # Since we select only featured excerpts from key topic tags, this should always be true
        tag = topicTags[0]
        subtopic = gDatabase["subtopic"][gDatabase["tag"][tag]["partOfSubtopics"][0]]
        isCluster = subtopic["subtags"] # A cluster has subtags; a regular tag doesn't
        if isCluster:
            tagDescription = f"tag cluster {Build.HtmlSubtopicLink(subtopic['tag'])}"
        else:
            tagDescription = f"tag {Build.HtmlTagLink(tag)}"

        html += f"<hr><p>Featured in {tagDescription}, part of key topic {Build.HtmlKeyTopicLink(subtopic['topicCode'])}.</p>"

    return {
        "text": excerpt["text"],
        "fTags": topicTags,
        "html": html,
        "shortHtml": shortHtml
    }

def FeaturedExcerptEntries() -> dict[str,ExcerptDict]:
    """Return a list of entries corresponding to featured excerpts in key topics."""

    keyTopicFilter = Filter.FTag(Database.KeyTopicTags().keys())
    teacherFilter = Filter.Teacher("AP")
    kindFilter = Filter.ExcerptMatch(Filter.Kind("Comment").Not())
    homepageFilter = Filter.And(keyTopicFilter,teacherFilter,Filter.HomepageExcerpts(),kindFilter)
    featuredExcerpts =  [x for x in homepageFilter(gDatabase["excerpts"])]

    return {Database.ItemCode(x):ExcerptEntry(x) for x in featuredExcerpts}

def Header() -> dict[str]:
    """Return a dict describing the conditions under which the random excerpts were built."""

    now = datetime.datetime.now().isoformat()
    return {
        "made": now,
        "updated": now,
        "mirrors": gOptions.mirrorUrl,
        "excerptSources": gOptions.excerptMp3
    }

def UpdateHeader(database: FeaturedDatabase) -> None:
    for key,value in Header().items():
        if key != "made":
            database[key] = value

def Remake(paramStr: str) -> bool:
    """Create a completely new random excerpt dictionary.
    paramStr (if given) specifies the number of excerpts to put in the past."""

    global gFeaturedDatabase

    entries = FeaturedExcerptEntries()
    calendar = list(entries)
    random.shuffle(calendar)

    historyDays = ParseNumericalParameter(paramStr)
    startDate = (datetime.date.today() - timedelta(days=historyDays)).isoformat()
    
    gFeaturedDatabase = dict(**Header(),startDate=startDate,excerpts=entries,calendar=calendar)

    Alert.info("Generated new featured excerpt database with",len(gFeaturedDatabase["excerpts"]),"entries")
    if historyDays:
        Alert.info(historyDays,"past days placed in calendar.")
    return True

def Read(paramStr: str) -> bool:
    """Reads the database from its usual location."""
    
    ReadDatabase()

def ExcerptMirrorList(database: FeaturedDatabase) -> list[str]:
    """Returns the list of excerpt mirrors for this database."""
    
    return [database["mirrors"][s] for s in database["excerptSources"]]

def DatabaseMismatches() -> tuple[list[ExcerptDict],list[ExcerptDict],list[ExcerptDict]]:
    """Returns the entries in gFeaturedDatabase that don't match the current excerpt database.
    Returns the tuple (textMatches,textMismatches,missingEntries):
    textMatches: The text matches but fTags or html doesn't
    textMismatches: The text doesn't match
    missingEntries: The item code cannot be found in the current database."""

    textMatches = []
    textMismatches = []
    missingEntries = []
    for excerptCode,databaseEntry in gFeaturedDatabase["excerpts"].items():
        currentExcerpt = Database.FindExcerpt(excerptCode)
        if currentExcerpt:
            currentEntry = ExcerptEntry(currentExcerpt)
            if currentEntry != databaseEntry:
                if currentEntry["text"] == databaseEntry["text"]:
                    textMatches.append(excerptCode)
                else:
                    textMismatches.append(excerptCode)
        else:
            missingEntries.append(excerptCode)
    
    return textMatches,textMismatches,missingEntries


def Check(paramStr: str) -> bool:
    """Checks gFeaturedDatabase to make sure that everything matches the current environment.
    Returns False if any of the checks fail."""
    
    databaseGood = True

    currentMirrors = ExcerptMirrorList(Header())
    databaseMirrors = ExcerptMirrorList(gFeaturedDatabase)
    if databaseMirrors != currentMirrors:
        Alert.error("The database specifies excerpt mirrors",databaseMirrors,"which do not match the command line mirrors",currentMirrors)
        databaseGood = False

    textMatches,textMismatches,missingEntries = DatabaseMismatches()
    databaseGood = databaseGood and not any((textMatches,textMismatches,missingEntries))

    if missingEntries:
        Alert.error(len(missingEntries),"""entries in the database read from disk cannot be found in the current database.
These may require the Fix module if excerpts have moved or the Remove module if they have been deleted.""")
        Alert.essential.ShowFirstItems(missingEntries,"missing excerpt")

    if textMatches or textMismatches:
        Alert.error(len(textMatches) + len(textMismatches),"entries do not match between the current database and the database read from disk.")
        if textMatches:
            Alert.essential(len(textMatches),"entries simply need to be updated with the Update module.")
        if textMismatches:
            Alert.essential(len(textMismatches),"entries texts do not match and might require the Fix module if excerpts have moved.")
            Alert.essential.ShowFirstItems(textMismatches,"text mismatched excerpt")
    
    missingCalendarItems = [code for code in gFeaturedDatabase["calendar"] if code not in gFeaturedDatabase["excerpts"]]
    if missingCalendarItems:
        Alert.error(len(missingCalendarItems),"calendar entries cannot be found in the excerpt list.")
        Alert.essential("Run the fix module to correct this problem.")
        Alert.essential.ShowFirstItems(missingCalendarItems,"missing entry")
        databaseGood = False

    if databaseGood:
        Alert.info("No errors found in database.")
    return databaseGood

def Update(paramStr: str) -> bool:
    """Set entries in gFeaturedDatabase equal to the current database if the text string matches closely enough.
    Return True if we modify gFeaturedDatabase."""

    databaseChanged = False
    textMatches,textMismatches,missingEntries = DatabaseMismatches()

    for code in textMatches:
        gFeaturedDatabase["excerpts"][code] = ExcerptEntry(Database.FindExcerpt(code))
        databaseChanged = True
    if textMatches:
        Alert.info("Updated",len(textMatches),"excerpts with identical text strings.")
    
    for code in textMismatches:
        currentEntry = ExcerptEntry(Database.FindExcerpt(code))
        entryOnDisk = gFeaturedDatabase["excerpts"][code]
        ratio = SequenceMatcher(a=entryOnDisk["text"],b=currentEntry["text"]).ratio()
        updated = "does not match; not updated"
        if ratio >= gOptions.updateThreshold:
            gFeaturedDatabase["excerpts"][code] = currentEntry
            updated = "matches; updated"
            databaseChanged = True
        Alert.extra("")
        Alert.info(f"Excerpt: {code}; ratio:{ratio:.3f}; {updated}.")
        Alert.extra("Old:",entryOnDisk["text"],indent=6)
        Alert.extra("New:",currentEntry["text"],indent=6)

    if not databaseChanged:
        Alert.info("No changes made to database.")
    return databaseChanged


def Write(paramStr: str,goodDatabase:bool = True) -> bool:
    """Write the database to disk if it is good or paramStr contains 'always'."""
    paramStr = paramStr.lower()
    if goodDatabase or "always" in paramStr:
        if not goodDatabase:
            Alert.warning("The database contains errors, but is being written to disk anyway.")
        if "never" in paramStr:
            Alert.info("Database not written to disk.")
        else:
            WriteDatabase(gFeaturedDatabase)
    else:
        Alert.info("The database contains unidentified or improperly linked excerpts and cannot be written.")

def AnnounceSubmodule(submodule: SubmoduleType|None) -> None:
    """Print the name and parameter of this submodule."""
    if submodule:
        submoduleName = submodule.__name__.lower()
        parameter = gOptions.featured.get(submoduleName,"")
        parameterStr = f" with parameter {repr(parameter)}" if parameter else ""
        Alert.structure(f"------- Running SetupFeatured.{submoduleName.capitalize()}(){parameterStr}")
    else:
        Alert.structure(f"------- All submodules finished.")

def RunSubmodule(submodule: SubmoduleType,alwaysRun:bool = False,**kwargs) -> bool|None:
    """Runs the named submodule if it was specified by --featured and returns the result.
    Returns None if the submodule doesn't run."""

    submoduleName = submodule.__name__.lower()
    if submoduleName in gOptions.featured or alwaysRun:
        AnnounceSubmodule(submodule)
        return submodule(gOptions.featured.get(submoduleName,""),**kwargs)
    else:
        return None

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--featured',type=str,default="update",help="Comma-separated list of operations to run on the featured database.")
    parser.add_argument('--featuredDatabase',type=str,default="pages/assets/FeaturedDatabase.json",help="Featured database filename.")
    parser.add_argument('--randomExcerptCount',type=int,default=0,help="Include only this many random excerpts in the calendar.")
    parser.add_argument('--updateThreshold',type=float,default=0.8,help="SetupFeatured.Update replaces old text with new if ratio is at least this.")

def ParseArguments() -> None:
    # --featured is a comma-separated list of operations from gOperations optionally followed by non-alphabetic parameters
    gOptions.featured = [re.match(r"([a-z]*)(.*)",op.strip(),re.IGNORECASE) for op in gOptions.featured.split(',')]
    gOptions.featured = {m[1].lower():m[2] for m in gOptions.featured}

    unrecognized = [op for op in gOptions.featured if op not in gSubmodules]
    if unrecognized:
        Alert.warning("--featured specifies unknown operation(s)",unrecognized,". Available operations are",gSubmodules)

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

gFeaturedDatabase:FeaturedDatabase = {}
gRepairModules:list[SubmoduleType] = [Update]
gSubmodules:dict[str,SubmoduleType] = {op.__name__.lower():op for op in [Remake,Read,Check,Write] + gRepairModules}

def main() -> None:
    global gFeaturedDatabase

    random.seed(42)

    databaseChanged = RunSubmodule(Remake)
    if not databaseChanged:
        RunSubmodule(Read,alwaysRun=True)
    if not gFeaturedDatabase:
        return
    
    PrintInfo(gFeaturedDatabase)
    goodDatabase = RunSubmodule(Check)

    databaseRepaired = any(RunSubmodule(m) for m in gRepairModules)
    if databaseRepaired:
        UpdateHeader(gFeaturedDatabase)

    databaseChanged = databaseRepaired or databaseChanged
    
    if not goodDatabase or databaseChanged:
        goodDatabase = RunSubmodule(Check,alwaysRun=True)

    if databaseChanged:
        RunSubmodule(Write,alwaysRun=True,goodDatabase=goodDatabase)
    else:
        AnnounceSubmodule(None)
        Alert.info("No changes need to be written to disk.")
    
