"""Maintain pages/assets/FeaturedDatabase.json, which contains rendered random featured excerpts to display on the homepage.
"""

from __future__ import annotations

import os, json, datetime, re
from datetime import timedelta
import random
from difflib import SequenceMatcher
from typing import Callable, TypedDict, NotRequired
import Utils, Alert, Build, Filter, Database
from copy import copy
import Filter
import Html2 as Html
from collections import defaultdict

# A submodule takes a string with its arguments and returns a bool indicating its status or None if the submodule doesn't run
SubmoduleType = Callable[[str],bool|None]
class ExcerptDict(TypedDict):
      text: str             # Text of the excerpt; used to identify this excerpt when its code changes
      fTags: list[str]      # The excerpt's fTags
      oldFTags: NotRequired[list[str]]
                            # fTags that were applied to this excerpt in the past.
      shortHtml: str        # Html code to render on the homepage
      html: str             # Html code to render on the daily featured excerpts page
    
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
        Alert.error(f"Could not write {filename} due to {err}")
        return False
    
def SplitPastAndFuture(database: FeaturedDatabase,offset:int = 0) -> tuple[list[str],list[str]]:
    """Split database["calenar"] into two lists (past,future). If offset == 0, past includes today.
    if offset > 0, include this many days past today in past as well."""
    daysPast = (datetime.date.today() - datetime.date.fromisoformat(database["startDate"])).days

    cutPoint = daysPast + offset + 1
    cutPoint = max(min(cutPoint,len(database["calendar"]) - 1),0)

    return (database["calendar"][0:cutPoint],database["calendar"][cutPoint:])

def PrintInfo(database: FeaturedDatabase) -> None:
    """Print information about this featured excerpt database."""
    Alert.info("Featured excerpt database contains",len(database["excerpts"]),"excerpts.")

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
    formatter.excerptShowFragmentPlayers = False
    html = formatter.HtmlExcerptList([excerpt])

    simpleExcerpt = copy(excerpt)
    simpleExcerpt["annotations"] = ()
    simpleExcerpt["tags"] = ()
    formatter.excerptDefaultTeacher = {"AP"}
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

def FeaturedExcerptFilter() -> Filter.Filter:
    """Returns a filter that passes front-page excerpts."""
    keyTopicFilter = Filter.FTag(Database.KeyTopicTags().keys())
    teacherFilter = Filter.Or(Filter.ExcerptMatch(Filter.FirstTeacher("AP")),
                              Filter.SingleItemMatch(Filter.Teacher("AP"),Filter.Kind("Read by")))
        # Pass only excerpts where AP is the first teacher in the excerpt or he is reading the excerpt
    kindFilter = Filter.ExcerptMatch(Filter.Kind("Comment").Not())
    return Filter.And(Filter.HomepageFlags(),keyTopicFilter,teacherFilter,kindFilter)

def FeaturedExcerptEntries() -> dict[str,ExcerptDict]:
    """Return a list of entries corresponding to featured excerpts in key topics."""

    featuredExcerpts =  [x for x in FeaturedExcerptFilter()(gDatabase["excerpts"])]
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
            if "oldFTags" in databaseEntry:
                currentEntry["oldFTags"] = databaseEntry["oldFTags"]
                    # Ignore oldFTags in the comparison
            if currentEntry != databaseEntry:
                if currentEntry["text"] == databaseEntry["text"]:
                    textMatches.append(excerptCode)
                else:
                    textMismatches.append(excerptCode)
        else:
            missingEntries.append(excerptCode)
    
    return textMatches,textMismatches,missingEntries

def DemotedExcerpts() -> tuple[list[str],dict[list[str]]]:
    """Return a list of excerpts that are no longer featured on the homepage.
    Returns the tuple (demotedExcerpts,when):
    demotedExcerpts: a list of the demoted excerpt codes.
    when: a dictionary describing when these excerpts occur in the calendar."""

    demoted = []
    featuredfilter = FeaturedExcerptFilter()
    for excerptCode,databaseEntry in gFeaturedDatabase["excerpts"].items():
        currentExcerpt = Database.FindExcerpt(excerptCode)
        if not featuredfilter.Match(currentExcerpt):
            demoted.append(excerptCode)
    
    past,future = SplitPastAndFuture(gFeaturedDatabase)
    when = defaultdict(list)
    for excerptCode in demoted:
        if excerptCode in past:
            if excerptCode in future:
                when["both"].append(excerptCode)
            else:
                when["past"].append(excerptCode)
        elif excerptCode in future:
            when["future"].append(excerptCode)
        else:
            when["neither"].append(excerptCode)

    return demoted,when

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
    
    demotedExcerpts,demotedWhen = DemotedExcerpts()
    if demotedExcerpts:
        if len(demotedWhen) == 1 and "past" in demotedWhen:
            Alert.notice(len(demotedExcerpts),"excerpts appearing in the past have been demoted from homepage status.")
        else:
            Alert.caution(len(demotedExcerpts),"excerpts have been demoted from homepage status.")
            Alert.essential("Location of demoted excerpts in calendar:",dict(demotedWhen))
            if demotedWhen["future"] or demotedWhen["both"]:
                Alert.essential("Demoted excerpts to be featured in the future should be removed with RemakeFuture.")
            if demotedWhen["neither"]:
                Alert.essential("Demoted items not appearing in the calendar can be removed by running the Trim module")
            Alert.essential()
    
    excerptsInCalendar = set(gFeaturedDatabase["calendar"])
    excerptsInDatabase = set(gFeaturedDatabase["excerpts"])
    currentFeaturedExcerpts = set(Database.ItemCode(x) for x in FeaturedExcerptFilter()(gDatabase["excerpts"]))

    missingCalendarItems = excerptsInCalendar - excerptsInDatabase
    if missingCalendarItems:
        Alert.error(len(missingCalendarItems),"calendar entries cannot be found in the excerpt list.")
        Alert.essential("Run the fix module to correct this problem.")
        Alert.essential.ShowFirstItems(sorted(missingCalendarItems),"missing entry")
        databaseGood = False

    if databaseGood:
        Alert.info("No errors found in database.")
    
    newFeaturedExcerpts = currentFeaturedExcerpts - excerptsInDatabase
    if newFeaturedExcerpts:
        Alert.info(len(newFeaturedExcerpts),"new featured excerpts do not appear in the database.")
        Alert.info("Run the remakeFuture module to include them.")
        Alert.info.ShowFirstItems(sorted(newFeaturedExcerpts),"new excerpt")

    return databaseGood

def UpdateEntry(entry: ExcerptDict,newEntry: ExcerptDict,excerptCode: str) -> None:
    """Update entry so that it has the contents of newEntry.
    If newEntry removes fTags, store them in oldFTags."""

    for fTag in entry["fTags"]:
        if fTag not in newEntry["fTags"]:
            entry["oldFTags"] = entry.get("oldFTags",[]) + [fTag]
            Alert.notice("Removing fTag",repr(fTag),"from",excerptCode)
    entry.update(newEntry) # Note that newEntry should not have key oldFTags

def Update(paramStr: str) -> bool:
    """Set entries in gFeaturedDatabase equal to the current database if the text string matches closely enough.
    Return True if we modify gFeaturedDatabase."""

    databaseChanged = False
    textMatches,textMismatches,missingEntries = DatabaseMismatches()

    for code in textMatches:
        UpdateEntry(gFeaturedDatabase["excerpts"][code],ExcerptEntry(Database.FindExcerpt(code)),code)
        databaseChanged = True
    if textMatches:
        Alert.info("Updated",len(textMatches),"excerpts with identical text strings.")
    
    for code in textMismatches:
        currentEntry = ExcerptEntry(Database.FindExcerpt(code))
        oldText = gFeaturedDatabase["excerpts"][code]["text"]
        ratio = SequenceMatcher(a=oldText,b=currentEntry["text"]).ratio()
        updated = "does not match; not updated"
        if ratio >= gOptions.updateThreshold:
            UpdateEntry(gFeaturedDatabase["excerpts"][code],currentEntry,code)
            updated = "matches; updated"
            databaseChanged = True
        Alert.extra("")
        Alert.info(f"Excerpt: {code}; ratio:{ratio:.3f}; {updated}.")
        Alert.extra("Old:",oldText,indent=6)
        Alert.extra("New:",currentEntry["text"],indent=6)

    if not databaseChanged:
        Alert.info("No changes made to database.")
    return databaseChanged

def RemakeFuture(paramStr: str) -> bool:
    """Remove any future featured excerpts that are no longer featured, add any newly featured excerpts,
    and shuffle all future excerpts.
    paramStr (if given) specifies the number of future excerpts to preserve unchanged."""

    preserveDays = ParseNumericalParameter(paramStr)
    past,future = SplitPastAndFuture(gFeaturedDatabase,offset=preserveDays)

    demotedExcerpts,_ = DemotedExcerpts()
    oldLength = len(future)
    future = [code for code in future if code not in demotedExcerpts]
    removed = oldLength - len(future)

    excerptsInDatabase = set(gFeaturedDatabase["excerpts"])
    currentFeaturedExcerpts = set(Database.ItemCode(x) for x in FeaturedExcerptFilter()(gDatabase["excerpts"]))
    
    newFeaturedExcerpts = sorted(currentFeaturedExcerpts - excerptsInDatabase)
    databaseChanged = bool(removed or newFeaturedExcerpts)
    if databaseChanged:
        future += newFeaturedExcerpts
        random.shuffle(future)
        gFeaturedDatabase["calendar"] = past + future
        for newExcerpt in newFeaturedExcerpts:
            gFeaturedDatabase["excerpts"][newExcerpt] = ExcerptEntry(Database.FindExcerpt(newExcerpt))

        Alert.info("Remake and reshuffle the featured excerpt calendar starting",preserveDays,"days in the future.")
        Alert.info("Removed",removed,"demoted excerpts; added",len(newFeaturedExcerpts),"new excerpts.")

        Trim("quiet")
    else:
        Alert.info("No changes to database.")
    return databaseChanged

def Trim(paramStr: str) -> bool:
    """Remove excerpts from the database that appear nowhere in the calendar."""

    excerptsInCalendar = set(gFeaturedDatabase["calendar"])
    oldLength = len(gFeaturedDatabase["excerpts"])
    gFeaturedDatabase["excerpts"] = {code:excerpt for code,excerpt in gFeaturedDatabase["excerpts"].items()
                                     if code in excerptsInCalendar}
    removedEntries = oldLength - len(gFeaturedDatabase["excerpts"])
    if removedEntries:
        Alert.info(removedEntries,"excerpts trimmed from database.")
    elif paramStr != "quiet":
        Alert.info("No changes made to database.")
    return bool(removedEntries)
    

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
gRepairModules:list[SubmoduleType] = [Update,RemakeFuture,Trim]
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
    
