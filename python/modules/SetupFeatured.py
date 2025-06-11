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

def RemakeRandomExcerpts(maxLength:int = 0,shuffle = True,historyDays = 0) -> dict[str]:
    """Return a completely new random excerpt dictionary."""
    """maxLength is the maximum length of the random excerpt calendar.
    begin with historyDays of initial history."""

    entries = FeaturedExcerptEntries()
    calendar = list(entries)
    if shuffle:
        random.shuffle(calendar)
    if maxLength:
        calendar = calendar[:maxLength]

    startDate = (datetime.date.today() - timedelta(days=historyDays)).isoformat()

    return dict(**Header(),startDate=startDate,excerpts=entries,calendar=calendar)

def ReadDatabase(filename:str) -> dict[str]:
    """Read a FeaturedDatabase.json file specified by filename"""
    with open(filename, 'r', encoding='utf-8') as file: # Otherwise read the database from disk
        newDB = json.load(file)
    return newDB

def WriteDatabase(newDatabase: dict[str]) -> None:
    """Write newDatabase to the random excerpt .json file"""
    with open(gOptions.featuredDatabase, 'w', encoding='utf-8') as file:
        json.dump(newDatabase, file, ensure_ascii=False, indent=2)

def PrintInfo(database: dict[str]) -> None:
    """Print information about this featured excerpt database."""
    Alert.info("Database contains",len(database["excerpts"]),"random excerpts.")

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--featured',type=str,default="check",help="Comma-separated list of operations to run on the featured database.")
    parser.add_argument('--featuredDatabase',type=str,default="pages/assets/FeaturedDatabase.json",help="Featured database filename.")
    parser.add_argument('--randomExcerptCount',type=int,default=0,help="Include only this many random excerpts in the calendar.")
    parser.add_argument('--homepageDefaultExcerpt',type=str,default="WR2018-2_S03_F01",help="Item code of exerpt to embed in homepage.html.")

gOperations = ["remake","check"]

def ParseArguments() -> None:
    # --featured is a comma-separated list of operations from gOperations optionally followed by non-alphabetic parameters
    gOptions.featured = [re.match(r"([a-z]*)(.*)",op.strip(),re.IGNORECASE) for op in gOptions.featured.split(',')]
    gOptions.featured = {m[1].lower():m[2] for m in gOptions.featured}

    unrecognized = [op for op in gOptions.featured if op not in gOperations]
    if unrecognized:
        Alert.warning("--featured specifies unknown operation(s)",unrecognized,". Available operations are",gOperations)

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy
gFeaturedDatabase:FeaturedDatabase = {}

def main() -> None:
    global gFeaturedDatabase
    if "remake" in gOptions.featured:
        random.seed(42)
        gFeaturedDatabase = RemakeRandomExcerpts(maxLength=gOptions.randomExcerptCount,historyDays = 30)
        Alert.info(gOptions.featuredDatabase,"remade with",len(gFeaturedDatabase["excerpts"]),"random excerpts.")
    else:
        gFeaturedDatabase = ReadDatabase(gOptions.featuredDatabase)
    
    PrintInfo(gFeaturedDatabase)
    WriteDatabase(gFeaturedDatabase)
    
