"""Maintain pages/assets/FeaturedDatabase.json, which contains rendered random featured excerpts to display on the homepage.
"""

from __future__ import annotations

import os, json, datetime
import random
from typing import NamedTuple, Iterable
import Utils, Alert, Build, Filter, Database
from copy import copy
import Filter
import Html2 as Html

def ExcerptEntry(excerpt:dict[str]) -> dict[str]:
    """Return a dictionary containing the information needed to display this excerpt on the front page."""
    
    formatter = Build.Formatter()
    formatter.SetHeaderlessFormat()
    formatter.excerptDefaultTeacher = {"AP"}
    html = formatter.HtmlExcerptList([excerpt])

    simpleExcerpt = copy(excerpt)
    simpleExcerpt["annotations"] = ()
    simpleExcerpt["tags"] = ()
    formatter.SetHeaderlessFormat(False)
    moreLink = Html.Tag("i","a",{"href":"search/Featured.html"})("details...")
    shortHtml = Html.Tag("p")(f"{formatter.FormatExcerpt(simpleExcerpt)} {moreLink}")

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
        "code": Database.ItemCode(excerpt),
        "text": excerpt["text"],
        "fTag": topicTags[0] if topicTags else "",
        "html": html,
        "shortHtml": shortHtml
    }

def FeaturedExcerptEntries() -> list[dict[str]]:
    """Return a list of entries corresponding to featured excerpts in key topics."""

    keyTopicFilter = Filter.FTag(Database.KeyTopicTags().keys())
    teacherFilter = Filter.And(Filter.Teacher("AP"))
    homepageFilter = Filter.And(keyTopicFilter,teacherFilter,Filter.HomepageExcerpts())
    featuredExcerpts =  [x for x in homepageFilter(gDatabase["excerpts"])]

    removeFragments = Filter.Kind(Filter.InverseSet(["Fragment"]))
    featuredExcerpts = [removeFragments.FilterAnnotations(x) for x in featuredExcerpts]
    return [ExcerptEntry(x) for x in featuredExcerpts]

def Header() -> dict[str]:
    """Return a dict describing the conditions under which the random excerpts were built."""

    now = datetime.datetime.now().isoformat()
    return {
        "made": now,
        "updated": now,
        "mirrors": gOptions.mirrorUrl,
        "excerptSources": gOptions.excerptMp3
    }

def RemakeRandomExcerpts(maxLength:int = 0,shuffle = True) -> dict[str]:
    """Return a completely new random excerpt dictionary"""

    entries = FeaturedExcerptEntries()
    if shuffle:
        random.shuffle(entries)
    if maxLength:
        entries = entries[:maxLength]
    
    return dict(**Header(),excerpts=entries)

def WriteDatabase(newDatabase: dict[str]) -> None:
    """Write newDatabase to the random excerpt .json file"""
    with open(gOptions.featuredDatabase, 'w', encoding='utf-8') as file:
        json.dump(newDatabase, file, ensure_ascii=False, indent=2)

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--featuredDatabase',type=str,default="pages/assets/FeaturedDatabase.json",help="Featured database filename.")
    parser.add_argument('--randomExcerptCount',type=int,default=0,help="Include only this many random excerpts in the database.")
    parser.add_argument('--homepageDefaultExcerpt',type=str,default="WR2018-2_S03_F01",help="Item code of exerpt to embed in homepage.html.")
    # parser.add_argument('--option',**Utils.STORE_TRUE,help='This is an option.')

def ParseArguments() -> None:
    pass    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main() -> None:
    random.seed(42)
    database = RemakeRandomExcerpts(maxLength=gOptions.randomExcerptCount)
    WriteDatabase(database)
    Alert.info(gOptions.featuredDatabase,"remade with",len(database["excerpts"]),"random excerpts.")
    
