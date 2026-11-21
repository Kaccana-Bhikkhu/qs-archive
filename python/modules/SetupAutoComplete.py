"""Write pages/assets/AutoCompleteDatabase.json which contains the information needed for
homepage.js to build the search dropdown list.
"""

from __future__ import annotations

import os,json,itertools,re
from Html2 import Icon
import Utils, Alert, Database
from typing import TypedDict, Iterable
from Build import FA_STAR, RemoveLanguageTag
from ParseCSV import TagFlag
import BuildReferences, Suttaplex
from bs4 import BeautifulSoup
from FileRegister import HashWriter
import Filter

class AutoCompleteEntry(TypedDict):
    short: str          # The short (or only) entry, e.g. Ajahn Chah
    long: str           # The longer teacher or tag name, e.g. Ajahn Chah Subadho
    number: str         # Digit(s) associated with this entry; e.g. Four Noble Truths
    link: str           # Link to page, e.g. teachers/ajahn-chah.html
    chip: str           # The search chip query corresponding to the page
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
    return dict(short=short,link=link,long=long,number=number,icon=Icon(icon,directoryDepth=0),suffix=suffix,excerptCount=excerptCount)

def FilterOnlyEntry(short: str,regexp: str = "",long: str = "", query: str = "",number: int = None,icon: str = "",suffix:str = "",excerptCount: int = 0) -> AutoCompleteEntry:
    "Return an AutoCompleteEntry representing a search defined by a query or regexp without a corresponding html page."
    number = "" if number is None else str(number)
    if not query:
        if not regexp:
            raise ValueError("FilterOnlyEntry requires either regexp or query")
        query = f"`{regexp}`"
    chip = Filter.QueryChip(short + suffix,query,icon)

    if not excerptCount:
        if not regexp:
            raise ValueError("FilterOnlyEntry must specify excerptCount if regexp is missing")
        foundExcerpts = list(Filter.RegexpFilter(regexp)(gDatabase["excerpts"]))
        excerptCount = len(foundExcerpts)
    return dict(short=short,chip=str(chip),long=long,number=number,icon=Icon(icon,directoryDepth=0),suffix=suffix,excerptCount = excerptCount)


def FilterOnlyEntries() -> Iterable[AutoCompleteEntry]:
    "Yield entries for searches without corresponding pages."

    # Featured and homepage excerpts
    yield FilterOnlyEntry("Featured excerpts",r"\+",query="+",icon="fa-star")

    # Categories
    for category in ("Questions","Stories","Quotes","Teachings","Meditations","Readings"):
        query = f"&{category.lower()}&"
        yield FilterOnlyEntry(f"Category: {category}",regexp=query,query=query,icon="All.png")

    # Filters for event series
    for series in gDatabase["series"].values():
        if series["abbreviation"] == "varies":
            continue
        query = f"@{series['abbreviation']}"
        yield FilterOnlyEntry(f"Event series: {series['series']}",regexp=query.lower(),query=query,icon="calendar")

    # Filters for each decade
    for decade in range(3):
        yield FilterOnlyEntry(f"Decade: 20{decade}0s",f"20{decade}[0-9]-?[1-9]?@",icon="calendar")

    yield FilterOnlyEntry("Homepage excerpts","#homepage",query="#homepage",icon="fa-star")

    # Filters for excerpt duration
    DURATION_NAMES = ("Very short","Short","Medium","Long","Very long")
    DURATION_DESCRIPTION = ("< 1 minute","1-2 minutes","2-5 minutes","5-10 minutes","> 10 minutes")
    for name,desc in zip(DURATION_NAMES,DURATION_DESCRIPTION):
        tag = f"#{name.replace(' ','').lower()}"
        yield FilterOnlyEntry(f"Duration: {name} ({desc})",tag,query=tag,icon="clock")
 

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

        yield (entry := Entry(text,subtopic["htmlPath"],
                    icon = "Cluster.png" if isCluster else "tag",
                    excerptCount = subtopic['excerptCount'],
                    number=NumberFromText(text)))
        if not isCluster:
            yield from SubtagQueryEntry(subtopic["tag"],entry)

def SubtagQueryEntry(tag: str,tagEntry:Entry) -> Iterable[AutoCompleteEntry]:
    """Return a filter-only entry which matches tag and all subtags.
    tagEntry is the entry generated for the tag so we can copy its form exactly."""

    subtags = Database.Subtags(tag)
    if not subtags:
        return
    subtags.add(tag)
    tagFilter = Filter.Tag(subtags)
    filterFound = list(tagFilter(Database.RemoveFragments(gDatabase["excerpts"])))
    filterCount = len(filterFound)

    """regexpFilter = Filter.RegexpFilter(tagFilter.Query(Filter.QueryType.REGEXP)) # Check regexp functionality
    regexpFound = list(regexpFilter(Database.RemoveFragments(gDatabase["excerpts"])))
    regexpCount = len(regexpFound)
    if (filterCount != regexpCount):
        Alert.warning(f"For tag {tag}, tag filter finds {filterCount} excerpts; regexp filter finds {regexpCount} excerpts")
        filterFound = {Database.ItemCode(x) for x in filterFound}
        regexpFound = {Database.ItemCode(x) for x in regexpFound}
        print("tag - regexp = ",filterFound - regexpFound)
        print("regep - tag = ",regexpFound - filterFound) """

    subtagDesc = f" and its {len(subtags) - 1} subtags" if len(subtags) > 2 else "subtag"
    if len(subtags) <= 20: # Too many tags and the search engine starts glitching; regexps are faster and seem to always work.
        yield FilterOnlyEntry(tagEntry["short"],long=tagEntry["long"],suffix = subtagDesc,query = tagFilter.Query(),icon="tags",excerptCount=filterCount)
    else:
        yield FilterOnlyEntry(tagEntry["short"],long=tagEntry["long"],suffix = subtagDesc,regexp=tagFilter.Query(Filter.QueryType.REGEXP),icon="tags")


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
    soloSubtopics = Database.SoloSubtopics()
    for tag in tags:
        if tag["tag"] not in soloSubtopics: # SubtopicEntries already yielded these above
            yield (entry := TagEntry(tag))
            yield from SubtagQueryEntry(tag["tag"],entry)

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

    otherPages = {
        "Upāsikā Day Themes": "UpasikaDays.html",
    } 

    for title,filename in otherPages.items():
        yield Entry("About: " + title,Utils.PosixJoin("about",filename),icon="text")

def TextEntries() -> Iterable[AutoCompleteEntry]:
    "Yield an entry for each about text (Sutta or Vinaya) referenced."
    
    yield Entry("Sutta references","texts/Sutta.html",icon="DhammaWheel.png")
    yield Entry("Vinaya references","texts/Vinaya.html",icon="DhammaWheel.png")

    dhammapada = Suttaplex.DhammapadaVerses()
    BuildReferences.ReadReferenceDatabase()

    for textData in gDatabase["text"].values():
        textRecord = BuildReferences.gSavedReferences["text"].get(textData["uid"])
        if textRecord:
            yield Entry(textData["name"] + f" ({textData['uid']})",textRecord["link"],icon="DhammaWheel.png",excerptCount=textRecord["count"])
        if textData["uid"] == 'Kd':
            yield Entry("Mahāvagga (Mv)",textRecord["link"],icon="DhammaWheel.png",excerptCount=textRecord["count"])

    for text,textData in BuildReferences.gSavedReferences["text"].items():
        if re.search(r"[0-9]$",text): # We already linked to full texts above
            ref = BuildReferences.TextReference.FromString(text)
            uid = ref.Uid()
            if gDatabase["text"][ref.text]["citeFullName"]:
                text = text.replace(ref.text,gDatabase["text"][ref.text]["name"])
            paliTitle = Suttaplex.Title(uid,translated=False)
            title = Suttaplex.Title(uid)
            combinedTitle = f"{paliTitle}, {title}" if (paliTitle and title) else paliTitle or title or ""
            if combinedTitle:
                combinedTitle = f"{text}: " + combinedTitle
            elif ref.text == "Dhp" and ref.n0:
                combinedTitle = f'{text}: “{Utils.EllideText(dhammapada[ref.n0],40,endAtWordBoundary=True)}”'
            else:
                combinedTitle = text
            yield Entry(combinedTitle,textData["link"],icon="DhammaWheel.png",excerptCount=textData["count"])

def BookEntries() -> Iterable[AutoCompleteEntry]:
    "Yield an entry for each about book referenced."
    
    yield Entry("Commentary references","books/Commentary.html",icon="book-open")
    yield Entry("Modern book references","books/Modern.html",icon="book-open")
    BuildReferences.ReadReferenceDatabase()
    for book,bookData in BuildReferences.gSavedReferences["book"].items():
        reference = BuildReferences.BookReference.FromString(gDatabase["reference"][book]["abbreviation"])
        entry = re.sub(r'["“”]',"",Utils.RemoveHtmlTags(reference.FullName(showAuthors=True,showYear=False)))
        yield Entry(entry,bookData["link"],icon="book-open",excerptCount=bookData["count"])
   

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
    entrySources = [FilterOnlyEntries(),KeyTopicEntries(),SutopicEntries(),TagEntries(),
                    EventEntries(),TeacherEntries(),CategoryEntries(),AboutEntries(),TextEntries(),BookEntries()]
    newDatabase:list[AutoCompleteEntry] = list(itertools.chain.from_iterable(entrySources))

    with HashWriter(gOptions.pagesDir,"assets/HashCache.json",exactDates=True) as pageDatabase:
        for entry in newDatabase:
            if entry.get("link") in pageDatabase.record and not entry["link"].startswith("indexes/AllExcerpts"):
                metadata = pageDatabase.GetMetadata(entry["link"])
                if "searchChip" in metadata:
                    entry["chip"] = metadata["searchChip"]
                    

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
        with open(Utils.AppendToFilename(filename,"_"), 'w', encoding='utf-8') as file:
            json.dump(newDatabase, file, ensure_ascii=False, indent=None)
        return True
    except OSError as err:
        Alert.error(f"Could not write {filename} due to {err}")
        return False
    