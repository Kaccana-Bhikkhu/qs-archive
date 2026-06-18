"""Maintain pages/assets/FeaturedDatabase.json, which contains rendered random featured excerpts to display on the homepage.
"""

from __future__ import annotations

import shutil, json, datetime, re
from datetime import timedelta, date
from enum import Enum
import random
import itertools
from difflib import SequenceMatcher
from typing import Callable, TypedDict
from dataclasses import dataclass
import Utils, Alert, Build, Database
from copy import copy
import Filter
import ParseCSV
from collections import defaultdict, Counter, deque
import icalendar

# A submodule takes a string with its arguments and returns a bool indicating its status or None if the submodule doesn't run
SubmoduleType = Callable[[str],bool|None]
class ExcerptDict(TypedDict):
      text: str         # Text of the excerpt; used to identify this excerpt when its code changes
      fTags: list[str]  # The excerpt's fTags
      shortHtml: str    # Html code to render on the homepage
      html: str         # Html code to render on the daily featured excerpts page

class HolidayDisplay(TypedDict):
    """Information about a particular anniversary stored in the database."""
    date: str       # The date in iso format
    text: str       # The text string to display
class FeaturedDatabase(TypedDict):
    made: str                       # Date and time this database was first made in iso format
    updated: str                    # Date and time this database was last changed

    mirrors: dict[str,str]          # The dict of mirror names and URLs the last time this database was updated
    excerptSources: list[str]       # The list of mirrors used for excerpt mp3s
        # The above two items are important because the html must be re-rendered when the excerpt mirror changes
    
    excerpts: dict[str,ExcerptDict] # Details about the excerpts; keys are given by the excerpt codes
    oldFTags: dict[str,list[str]]   # Excerpts from which fTags have been removed
                                    # Keys are excerpt codes; values are the removed fTags

    startDate: str                  # The date to display the first exerpt in calendar in iso format
    calendar: list[str]             # The list of excerpt codes to display on each date

    holiday: dict[str,str]         # holiday[isoDateStr] = holidayText

@dataclass
class Holiday:
    """Information about an anniversary."""
    name: str                    # Name of the holiday, e.g. "Ajahn Chah's Death Anniversary"
    date: date                   # Date of the birth or death
    filter: Filter.Filter        # Feature an excerpt which passes this filter

    def Date(self,year: int) -> date:
        "Return the date this holiday occurs in a given year."
        return date(year,self.date.month,self.date.day)

    def Message(self,year) -> str:
        "Return the message to display for a given year."
        return f"{self.name} – {year - self.date.year} years"

class StrEnum(str,Enum):
    pass

class BuddhistHoliday(StrEnum):
    MAGHA = "Māgha Pūjā"
    VISAKHA = "Visākha Pūjā"
    ASALHA = "Āsāḷha Pūjā"

HOLIDAY_MEANING = {BuddhistHoliday.MAGHA: "Saṅgha Day",
                  BuddhistHoliday.VISAKHA: "Buddha Day",
                  BuddhistHoliday.ASALHA: "Dhamma Day"}

gLunarHolidayDate: dict[BuddhistHoliday,dict[int,date]] = defaultdict(lambda: {})

def LunarHolidayDate(holiday: BuddhistHoliday,year: int) -> date:
    """Return the date of a lunar holiday on a given year. """
    if not gLunarHolidayDate:
        calendar = icalendar.Calendar.from_ical(lunarCalendarFilename)
        for event in calendar.events:
            if (holidayName := event.get("summary")) in BuddhistHoliday:
                holidayDate = event.decoded("dtstart")
                gLunarHolidayDate[holidayName][holidayDate.year] = holidayDate
            
    return gLunarHolidayDate[holiday].get(year)

class LunarHoliday(Holiday):
    """Information about a lunar observance day. The first two fields of Holiday are redefined as follows:
    name: one of the three values of BuddhistHoliday
    date: ignored"""

    def Date(self,year: int) -> date:
        "Return the date this holiday occurs in a given year."
        return LunarHolidayDate(self.name,year)

    def Message(self,year) -> str:
        "Return the message to display for a given year."
        return f"{self.name.value} – {HOLIDAY_MEANING[self.name]}"

def AllHolidays() -> list[Holiday]:
    "Return a list of all anniversaries, sorted by month and day."
    chahFilter = Filter.And(Filter.Teacher("AChah"),Filter.Flags("!"))
    return [
        Holiday("Ajahn Chah's Death Anniversary",date(1992,1,16),chahFilter),
        Holiday("Abhayagiri's Anniversary",date(1996,6,1),Filter.FTag("Abhayagiri")),
        LunarHoliday(BuddhistHoliday.MAGHA,None,Filter.FTag("Saṅgha")),
        LunarHoliday(BuddhistHoliday.VISAKHA,None,Filter.FTag("Buddha")),
        Holiday("Ajahn Chah's Birthday",date(1918,6,17),chahFilter),
        LunarHoliday(BuddhistHoliday.ASALHA,None,Filter.FTag("Dhamma")),
        Holiday("Ajahn Pasanno's Birthday",date(1949,7,26),Filter.FTag("Ajahn Pasanno")),
        Holiday("Ajahn Sumedho's Birthday",date(1934,7,27),Filter.FTag("Ajahn Sumedho")),
        Holiday("Ajahn Liem's Birthday",date(1941,11,5),Filter.FTag("Ajahn Liem")),
    ]

def HolidayIndices(offsetFromPresent: int = 0, entireCalendar: bool = False) -> dict[int:tuple(Holiday,int)]:
    """Return a dict of holiday indices of the form: holidayIndices[index] = (Holiday,year).
    offsetFromPresent has the same meaning as in SplitPastAndFuture.
    if wholeDatabase, return holidays for the entire calendar."""

    holidayIndices:dict[int:tuple(Holiday,int)] = {}
    holidays = AllHolidays()
    if entireCalendar:
        baseDate = date.fromisoformat(gFeaturedDatabase["startDate"])
        endYear = (baseDate + timedelta(days=len(gFeaturedDatabase["calendar"]))).year
    else:
        baseDate = date.today() + timedelta(days=1 + offsetFromPresent)
        endYear = baseDate.year + 4 # Four years in the future
    for year in range(baseDate.year,endYear + 1):
        for holiday in holidays:
            thisYearsDate = holiday.Date(year)
            index = (thisYearsDate - baseDate).days
            if index < 0:
                continue # The holiday is in the past
            holidayIndices[index] = (holiday,year)

    return holidayIndices

def HolidayTexts() -> dict[str,str]:
    """Generate the list of holidays and display messages."""
    holidayDict: dict[str,str] = {}
    for index,(holiday,year) in HolidayIndices(entireCalendar=True).items():
        holidayDict[holiday.Date(year).isoformat()] = holiday.Message(year)
    
    return holidayDict


def ReadDatabase(backupNumber:int = 0) -> bool:
    """Read the featured excerpt database from disk.
    If backupNumber is given, read from the specified backup file or the lastest backup if -1."""
    global gFeaturedDatabase
    
    filename = gOptions.featuredDatabase
    try:
        with open(filename, 'r', encoding='utf-8') as file: # Otherwise read the database from disk
            gFeaturedDatabase = json.load(file)
        Alert.info(f"Read featured excerpt DB from {filename} with {len(gFeaturedDatabase['calendar'])} calendar entries.")
        if "oldFTags" not in gFeaturedDatabase:
            gFeaturedDatabase["oldFTags"] = {}
        return True
    except OSError as err:
        Alert.error(f"Could not read {gOptions.featuredDatabase} due to {err}")
        return False

def CompressExcerptKeys(db: FeaturedDatabase) -> None:
    """Convert excerpt keys like 'Chah2001_S05_F05' to shorter base64 encodings."""
    excerpts = db["excerpts"]
    codeBook = {key:str(n) for n,key in enumerate(excerpts)}
    for key,encoded in codeBook.items():
        excerpts[encoded] = excerpts[key]
        del excerpts[key]
    db["calendar"] = [codeBook[key] for key in db["calendar"]]

def HomepageDatabase(db: FeaturedDatabase) -> dict[str]:
    """Return a condensed database containing only what is needed to display the home page."""

    returnValue = {key:db[key] for key in ("startDate","calendar","holiday")}
    returnValue["excerpts"] = {x:db["excerpts"][x]["shortHtml"] for x in db["excerpts"]}
    returnValue["holidays"] = [] # Prevent an outdated version of homepage.js from crashing
    return returnValue

def HistoryDatabase(db: FeaturedDatabase) -> dict[str]:
    """Return a condensed database containing only what is needed to display the home page."""

    returnValue = {key:db[key] for key in ("startDate","calendar","holiday")}
    returnValue["excerpts"] = {x:db["excerpts"][x]["html"] for x in db["excerpts"]}
    returnValue["holidays"] = [] # Prevent an outdated version of homepage.js from crashing
    return returnValue

def WriteDatabase(newDatabase: FeaturedDatabase) -> bool:
    """Write newDatabase to the random excerpt .json file"""
    filename = gOptions.featuredDatabase
    homepageFilename = Utils.AppendToFilename(gOptions.featuredDatabase,"1_")
    historyFilename = Utils.AppendToFilename(gOptions.featuredDatabase,"2_")
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(newDatabase, file, ensure_ascii=False, indent=2)
        Alert.info(f"Wrote featured excerpt database to {filename}.")
        CompressExcerptKeys(newDatabase)
        with open(homepageFilename, 'w', encoding='utf-8') as file:
            json.dump(HomepageDatabase(newDatabase), file, ensure_ascii=False, indent=None)
        with open(historyFilename, 'w', encoding='utf-8') as file:
            json.dump(HistoryDatabase(newDatabase), file, ensure_ascii=False, indent=None)
        return True
    except OSError as err:
        Alert.error(f"Could not write {filename} due to {err}")
        return False
    
def SplitPastAndFuture(database: FeaturedDatabase,offsetFromPresent:int = 0) -> tuple[list[str],list[str]]:
    """Split database["calenar"] into two lists (past,future). If offset == 0, past includes today.
    if offsetFromPresent > 0, include this many days past today in past as well."""
    daysPast = (date.today() - date.fromisoformat(database["startDate"])).days

    cutPoint = daysPast + offsetFromPresent + 1
    cutPoint = max(min(cutPoint,len(database["calendar"]) - 1),0)

    return (database["calendar"][0:cutPoint],database["calendar"][cutPoint:])

def PrintInfo(database: FeaturedDatabase) -> None:
    """Print information about this featured excerpt database."""
    Alert.info("Featured excerpt database contains",len(database["excerpts"]),"excerpts.")

    calendarLength = len(database['calendar'])
    daysPast = (date.today() - date.fromisoformat(database["startDate"])).days

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

    if gFeaturedDatabase and gFeaturedDatabase.get("oldFTags"):
        oldFTags = gFeaturedDatabase["oldFTags"].get(Database.ItemCode(excerpt)) or []
    else:
        oldFTags = []
    if not topicTags: # If there are no current fTags, check for previous fTags
        topicTags = [tag for tag in oldFTags if tag in keyTopicTags]

    if topicTags:
        tag = topicTags[0]
        subtopic = gDatabase["subtopic"][gDatabase["tag"][tag]["partOfSubtopics"][0]]
        isCluster = subtopic["subtags"] # A cluster has subtags; a regular tag doesn't
        if isCluster:
            tagDescription = f"tag cluster {Build.HtmlSubtopicLink(subtopic['tag'])}"
        else:
            tagDescription = f"tag [{Build.HtmlTagLink(tag)}]"

        html += f"<hr><p>{'Formerly f' if oldFTags else 'F'}eatured in {tagDescription}, part of key topic {Build.HtmlKeyTopicLink(subtopic['topicCode'])}.</p>"
    else:
        if excerpt["fTags"]:
            html += f"<hr><p>Featured in tag [{Build.HtmlTagLink(excerpt['fTags'][0])}].</p>"
        elif otherTags := excerpt.get("homepageOnlyTags") or oldFTags:
            html += f"<hr><p>Other excerpts with tag [{Build.HtmlTagLink(otherTags[0])}].</p>"

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
    return Filter.Or(
        Filter.And(Filter.HomepageFlags(),keyTopicFilter,teacherFilter,kindFilter),
        Filter.Flags("!"),
        Filter.HomepageOnlyTag(Filter.All)
    )


def FeaturedExcerptEntries() -> dict[str,ExcerptDict]:
    """Return a list of entries corresponding to featured excerpts in key topics."""

    featuredExcerpts =  [x for x in FeaturedExcerptFilter()(gDatabase["excerpts"])]
    return {Database.ItemCode(x):ExcerptEntry(x) for x in featuredExcerpts}

def Header() -> FeaturedDatabase:
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
    startDate = (date.today() - timedelta(days=historyDays)).isoformat()
    
    gFeaturedDatabase = FeaturedDatabase(
        **Header(),
        startDate=startDate,
        excerpts=entries,
        calendar=calendar,
        oldFTags={},
        holidays=HolidayTexts())

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

def DemotedExcerpts() -> tuple[list[str],dict[str,list[str]]]:
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
        Alert.info("Run the RemakeFuture module to include them.")
        Alert.info.ShowFirstItems(sorted(newFeaturedExcerpts),"new excerpt")

    return databaseGood

def UpdateEntry(entry: ExcerptDict,newEntry: ExcerptDict,excerptCode: str) -> None:
    """Update entry so that it has the contents of newEntry.
    If newEntry removes fTags, store them in gFeaturedDatabase["oldFTags"]."""

    for fTag in entry["fTags"]:
        if fTag not in newEntry["fTags"]:
            gFeaturedDatabase["oldFTags"][excerptCode] = gFeaturedDatabase["oldFTags"].get("excerptCode",[])
            gFeaturedDatabase["oldFTags"][excerptCode].append(fTag)
            Alert.notice("Removing fTag",repr(fTag),"from",excerptCode)
            newEntry = ExcerptEntry(Database.FindExcerpt(excerptCode))
                # The entry html depends on gFeaturedDatabase["oldFTags"], so newEntry needs to be updated again
    entry.update(newEntry)

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
        Alert.info(f"Excerpt: {code}; ratio: {ratio:.3f}; {updated}.")
        Alert.extra("Old:",oldText,indent=6)
        Alert.extra("New:",currentEntry["text"],indent=6)

    if not databaseChanged:
        Alert.info("No changes made to database.")
    return databaseChanged

def IsFragment(entryOrExcerpt: ExcerptDict|dict) -> bool:
    "Returns True if entryOrExcerpt is a fragment."

    if "flags" in entryOrExcerpt:
        return ParseCSV.ExcerptFlag.FRAGMENT in entryOrExcerpt["flags"]
    elif "html" in entryOrExcerpt: # Use a regexp that finds decimal excerpt numbers
        return bool(re.search(r">Excerpt [0-9]+\.[0-9]</a>",entryOrExcerpt["html"]))
    else:
        raise ValueError(f"Utils.IsFragment cannot determine the type of argument {entryOrExcerpt}")

def Fix(paramStr: str) -> bool:
    """Search entries in the current database to match excerpts in gFeaturedDatabase that no longer match the same file number.
    This most commonly occurs when fragments have been inserted or removed earlier in the session.
    Return True if we modify gFeaturedDatabase."""

    textMatches,textMismatches,missingEntries = DatabaseMismatches()
    # At this point, Update will have already taken care of any textMatches
    
    databaseChanges:dict[str,str] = {} # The changes we will make to the database: databaseChanges[oldCode] = newCode
    unmatched:list[str] = [] # A list of excerpt codes we couldn't find matches for
    for code in textMismatches:
        mismatchedFragment = IsFragment(gFeaturedDatabase["excerpts"][code])
        oldText = gFeaturedDatabase["excerpts"][code]["text"]
        matcher = SequenceMatcher(b=oldText)

        event,sessionNumber,_ = Database.ParseItemCode(code)
        fileNumber = 1
        candidates:list[tuple[float,dict]] = [] # The list of tuples (ratio, excerpt)
        while candidateExcerpt := Database.FindExcerpt(event,sessionNumber,fileNumber):
            fileNumber += 1
            if IsFragment(candidateExcerpt) != mismatchedFragment:
                continue    # Don't allow fragment excerpts to match non-fragments
                            # This prevents confusion when main fragments have the same text as their origin excerpt.

            matcher.set_seq1(candidateExcerpt["text"])
            candidates.append((matcher.ratio(),candidateExcerpt))
        
        candidates.sort(key=lambda item:item[0],reverse=True)

        if len(candidates) < 1:
            Alert.error("There are no possible matches for excerpt",code,".")
            unmatched.append(code)
            continue

        best = candidates[0]
        secondBest = candidates[1] if len(candidates) > 1 else (0.0,{"text":""})
        
        if best[0] >= gOptions.updateThreshold:
            Alert.extra("")
            Alert.info(f"Excerpt: {code} matches {Database.ItemCode(best[1])}; ratio: {best[0]:.3f}.")
            Alert.extra("Old:",oldText,indent=6)
            Alert.extra("New:",best[1]["text"],indent=6)
            if secondBest[0] < gOptions.updateThreshold:
                databaseChanges[code] = Database.ItemCode(best[1])
            else:
                Alert.info(f"However, it also matches {Database.ItemCode(secondBest[1])}; ratio: {secondBest[0]:.3f}.")
                Alert.extra("Second-best:",secondBest[1]["text"],indent=6)
                Alert.info("Choose a different threshold or upgrade the Fix module to allow this situation to be resolved manually.")
                unmatched.append(code)
        else:
            Alert.warning(f"No match found for excerpt: {code}.")
            unmatched.append(code)

    if unmatched:
        Alert.error("Could not find matches for excerpt(s):",unmatched,". The database will remain unchanged.")
        return False
    
    if databaseChanges:
        # First rename the keys in the database
        Utils.RenameKeys(gFeaturedDatabase["excerpts"],databaseChanges)
        Utils.RenameKeys(gFeaturedDatabase["oldFTags"],databaseChanges)

        # Then update the contents of the entries we have changed
        for newCode in databaseChanges.values():
            UpdateEntry(gFeaturedDatabase["excerpts"][newCode],ExcerptEntry(Database.FindExcerpt(newCode)),newCode)

        # Finally change the entries in the calendar
        gFeaturedDatabase["calendar"] = [databaseChanges.get(code) or code for code in gFeaturedDatabase["calendar"]]

        Alert.info("Updated file numbers for",len(databaseChanges),"excerpts.")
        return True
    else:
        Alert.info("No changes need to be fixed.")


def RemakeFuture(paramStr: str) -> bool:
    """Remove any future featured excerpts that are no longer featured and add any newly featured excerpts.
    Swap calendar entries to minimize the changes needed to do this.
    paramStr (if given) specifies the number of future excerpts to preserve unchanged."""

    preserveDays = ParseNumericalParameter(paramStr)
    past,future = SplitPastAndFuture(gFeaturedDatabase,offsetFromPresent=preserveDays)
    holidayIndices = HolidayIndices(offsetFromPresent=preserveDays)

    demotedExcerpts,_ = DemotedExcerpts()
    demotedExcerptSet = set(demotedExcerpts)
    excerptsRemoved = sorted(demotedExcerptSet & set(future))

    excerptsInDatabase = set(gFeaturedDatabase["excerpts"])
    currentFeaturedExcerpts = set(Database.ItemCode(x) for x in FeaturedExcerptFilter()(gDatabase["excerpts"]))
    newExcerpts = sorted(currentFeaturedExcerpts - excerptsInDatabase)
    
    databaseChanged = bool(excerptsRemoved or newExcerpts)
    if databaseChanged:
        shuffled = list(newExcerpts)
        random.shuffle(shuffled)
        newExcerptIterator = iter(shuffled)

        for futureIndex in range(len(future)):
            if futureIndex < len(future) and future[futureIndex] in demotedExcerptSet:
                replacementExcerpt = next(newExcerptIterator,None)
                if replacementExcerpt: # Replace with a new featured excerpt if available
                    future[futureIndex] = replacementExcerpt
                else: # Otherwise replace with the last element of future
                    future[futureIndex] = future.pop()
        
        for newExcerpt in newExcerptIterator:
            while (swapIndex := random.randint(0,len(future) - 1)) in holidayIndices:
                pass
            future.append(future[swapIndex])
            future[swapIndex] = newExcerpt
        
        gFeaturedDatabase["calendar"] = past + future
        for newExcerpt in newExcerpts:
            gFeaturedDatabase["excerpts"][newExcerpt] = ExcerptEntry(Database.FindExcerpt(newExcerpt))

        Alert.info("Remake the featured excerpt calendar starting",preserveDays,"days in the future.")
        Alert.info("Removed",len(excerptsRemoved),"demoted excerpts:",excerptsRemoved,"; added",len(newExcerpts),"new excerpts.")

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

def Extend(paramStr: str) -> bool:
    """Extend the calendar by adding the shuffled contents of the database."""    
    entries = FeaturedExcerptEntries()
    newEntries = list(entries)
    random.shuffle(newEntries)

    oldExcerptCount = len(gFeaturedDatabase["excerpts"])
    for code,entry in entries.items():
        if code not in gFeaturedDatabase["excerpts"]:
            gFeaturedDatabase["excerpts"][code] = entry

    # Algorithm to avoid immediate repetition of excerpts:
    # 1. Make a list of excerpts at the end of the calendar and a dict that counts them.
    # The length of the list is is 2/3 len(newEntries).
    recentExcerpts = gFeaturedDatabase["calendar"][len(gFeaturedDatabase["calendar"]) - max(len(newEntries) * 2 // 3,50):]
    recentExcerptCount = Counter()
    for code in recentExcerpts:
        recentExcerptCount[code] += 1
    
    # 2. Add the excerpts in newEntries only if they do not appear in the previous 2/3 len(newExcepts) featured excepts.
    stillToAdd = deque(newEntries)
    remainingRecentExcerpts = iter(recentExcerpts)
    while (stillToAdd):
        toAdd = stillToAdd.popleft()
        if recentExcerptCount[toAdd]: # If the excerpt appeared too recently, put it back for future use
            stillToAdd.append(toAdd) 
        else: # Otherwise add this excerpt to the calendar and remove the oldest excerpt from recentExcerptCount
            gFeaturedDatabase["calendar"].append(toAdd)
            oldestRecentExcerpt = next(remainingRecentExcerpts,None)
            if oldestRecentExcerpt:
                recentExcerptCount[oldestRecentExcerpt] -= 1

    Alert.info("Extended the featured calendar by",len(newEntries),"entries")
    if addedExcerpts := len(gFeaturedDatabase["excerpts"]) - oldExcerptCount:
        Alert.info("Added",addedExcerpts,"new excerpt(s) to the database.")
    return True

lunarCalendarFilename = "tools/mahanikaya.ical"

def SummarizeLunarHolidays() -> None:
    """Summarize the available lunar holidays """
    calendar = icalendar.Calendar.from_ical(lunarCalendarFilename)
    yearSpan = []
    for event in calendar.events:
        if event.get("SUMMARY") in BuddhistHoliday:
            yearSpan.append(event.decoded("dtstart").year)
    Alert.info("Lunar holidays available from",min(yearSpan),"to",max(yearSpan))

def DownloadLunarCalendar() -> bool:
    """Download the lunar calendar to the documentation folder."""

    try:
        calendarAge = datetime.datetime.now() - Utils.ModificationDate(lunarCalendarFilename)
        if calendarAge < timedelta(days=180):
            Alert.info("The lunar calendar file is",calendarAge.days,"day(s) old; no need to download it again.")
            return False
    except OSError:
        pass

    url = "http://splendidmoons.github.io/ical/mahanikaya.ical"
    Alert.notice("Downloading the lunar calendar from",url)
    try:
        with Utils.OpenUrlOrFile("http://splendidmoons.github.io/ical/mahanikaya.ical") as calendarFile:
            with open(lunarCalendarFilename,"wb") as localFile:
                shutil.copyfileobj(calendarFile,localFile)
    except OSError as err:
        Alert.error(err,"occured when trying to download",url,"to",lunarCalendarFilename)
    
    SummarizeLunarHolidays()
    return True

def Holidays(paramStr: str) -> bool:
    """Swap future calendar entries so that holidays feature relevant excerpts."""    
    DownloadLunarCalendar()
    
    past,future = SplitPastAndFuture(gFeaturedDatabase)
    holidayIndices = HolidayIndices()

    changeCount = 0
    errorCount = 0
    # Then check if each holiday has an excerpt that matches the filter
    for index,(holiday,year) in holidayIndices.items():
        if index >= len(future):
            break
        if holiday.filter.Match(Database.FindExcerpt(future[index])):
            continue

        swapIndex = None
        # Loop over all indices of future in the sequence:
        # index - 1, index + 1, index - 2, index + 2, ...
        for scanIndex in itertools.chain.from_iterable(itertools.zip_longest(reversed(range(index)),range(index + 1,len(future)))):
            if scanIndex is not None and holiday.filter.Match(Database.FindExcerpt(future[scanIndex])):
                if scanIndex not in holidayIndices: # Don't swap with another holiday
                    swapIndex = scanIndex
                    break
        
        if swapIndex is not None:
            future[index],future[swapIndex] = future[swapIndex],future[index]
            Alert.info("Featuring",Database.FindExcerpt(future[index]),"for",holiday.name,"in",year)
            changeCount += 1
        else:
            Alert.warning("Unable to find a suitable excerpt for",holiday.name,"in",year)
            errorCount += 1

    if changeCount:
        gFeaturedDatabase["calendar"] = past + future
        Alert.info()
        Alert.info("Moved",changeCount,"relevant excerpts to holidays.")
    if errorCount:
        Alert.info("Could not find suitable excerpts for",errorCount,"holiday(s).")
    else:
        Alert.info("All future holidays feature relevant excerpts.")
    return bool(changeCount)

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
    if "fix" in gOptions.featured and "update" not in gOptions.featured: # Always run update before fix
        gOptions.featured["update"] = ""

    unrecognized = [op for op in gOptions.featured if op not in gSubmodules]
    if unrecognized:
        Alert.warning("--featured specifies unknown operation(s)",unrecognized,". Available operations are",gSubmodules)

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

gFeaturedDatabase:FeaturedDatabase = {}
gRepairModules:list[SubmoduleType] = [Update,Fix,RemakeFuture,Trim]
gEnhanceModules:list[SubmoduleType] = [Extend,Holidays]
gSubmodules:dict[str,SubmoduleType] = {op.__name__.lower():op for op in [Remake,Read,Check,Write] + gRepairModules + gEnhanceModules}

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

    databaseRepaired = any([RunSubmodule(m) for m in gRepairModules])

    newHolidayRecords = HolidayTexts()
    if newHolidayRecords != gFeaturedDatabase.get("holiday"):
        gFeaturedDatabase["holiday"] = newHolidayRecords
        databaseRepaired = True

    if databaseRepaired:
        UpdateHeader(gFeaturedDatabase)

    databaseChanged = databaseRepaired or databaseChanged
    
    if not goodDatabase or databaseChanged:
        goodDatabase = RunSubmodule(Check,alwaysRun=True)

    if goodDatabase:
        databaseEnhanced = any(RunSubmodule(m) for m in gEnhanceModules)
        if databaseEnhanced:
            goodDatabase = RunSubmodule(Check,alwaysRun=True)
        databaseChanged = databaseChanged or databaseEnhanced
    elif set(op.__name__.lower() for op in gEnhanceModules) & set(gOptions.featured):
        Alert.warning("Cannot run additional module(s)",[op.__name__ for op in gEnhanceModules],"due to database errors.")


    if databaseChanged or "write" in gOptions.featured:
        RunSubmodule(Write,alwaysRun=True,goodDatabase=goodDatabase)
    else:
        AnnounceSubmodule(None)
        Alert.info("No changes need to be written to disk.")