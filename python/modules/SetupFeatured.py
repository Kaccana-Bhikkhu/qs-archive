"""Maintain pages/assets/FeaturedDatabase.json, which contains rendered random featured excerpts to display on the homepage.
"""

from __future__ import annotations

import os, json, datetime, re
from datetime import timedelta
import random
from typing import NamedTuple, Iterable, TypedDict
import Utils, Alert, Build, Filter, Database
from copy import copy
import Filter
import Html2 as Html

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

def ReadDatabase(filename:str) -> FeaturedDatabase:
    """Read a FeaturedDatabase.json file specified by filename"""
    with open(filename, 'r', encoding='utf-8') as file: # Otherwise read the database from disk
        newDB = json.load(file)
    return newDB

def WriteDatabase(newDatabase: FeaturedDatabase) -> None:
    """Write newDatabase to the random excerpt .json file"""
    with open(gOptions.featuredDatabase, 'w', encoding='utf-8') as file:
        json.dump(newDatabase, file, ensure_ascii=False, indent=2)

def PrintInfo(database: FeaturedDatabase) -> None:
    """Print information about this featured excerpt database."""
    Alert.info("Featured excerpt database contains",len(database["excerpts"]),"random excerpts.")

    calendarLength = len(database['calendar'])
    daysPast = (datetime.date.today() - datetime.date.fromisoformat(database["startDate"])).days

    Alert.info(f"Calendar length {calendarLength}; {calendarLength - daysPast - 1} excerpts remaining.")
    

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

    removeFragments = Filter.Kind(Filter.InverseSet(["Fragment"]))
    featuredExcerpts = [removeFragments.FilterAnnotations(x) for x in featuredExcerpts]
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

def Check(paramStr: str) -> bool:
    """Checks gFeaturedDatabase to make sure that everything is okay.
    Returns False if any of the checks fail."""
    
    return True

def AnnounceSubmodule(submoduleName: str) -> None:
    """Print the name and parameter of this submodule."""
    if submoduleName:
        parameter = gOptions.featured[submoduleName]
        parameterStr = f" with parameter {repr(parameter)}" if parameter else ""
        Alert.structure(f"------- Running SetupFeatured.{submoduleName.capitalize()}(){parameterStr}")
    else:
        Alert.structure(f"------- All submodules finished.")

def RunSubmodule(submoduleName: str) -> bool:
    """Runs the named submodule if it was specified by --featured.
    Returns False if the submodule doesn't run or returns False."""

    if submoduleName in gOptions.featured:
        AnnounceSubmodule(submoduleName)
        return gSubmodules[submoduleName](gOptions.featured[submoduleName])
    else:
        return False

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--featured',type=str,default="check",help="Comma-separated list of operations to run on the featured database.")
    parser.add_argument('--featuredDatabase',type=str,default="pages/assets/FeaturedDatabase.json",help="Featured database filename.")
    parser.add_argument('--randomExcerptCount',type=int,default=0,help="Include only this many random excerpts in the calendar.")
    parser.add_argument('--homepageDefaultExcerpt',type=str,default="WR2018-2_S03_F01",help="Item code of exerpt to embed in homepage.html.")

gSubmodules = {op.__name__.lower():op for op in [Remake,Check]}

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

def main() -> None:
    global gFeaturedDatabase

    random.seed(42)
    RunSubmodule("remake")
    
    if not gFeaturedDatabase:
        gFeaturedDatabase = ReadDatabase(gOptions.featuredDatabase)

    RunSubmodule("check")
    
    AnnounceSubmodule("")
    PrintInfo(gFeaturedDatabase)
    WriteDatabase(gFeaturedDatabase)
    
