"""Create assets/SearchDatabase.json for easily searching the excerpts.
"""

from __future__ import annotations

import os, json, re
import Database, SetupRandom
import Utils, Alert, ParseCSV, Prototype, Filter
import Html2 as Html
from typing import Iterable, Iterator, Callable
import itertools

def Enclose(items: Iterable[str],encloseChars: str = "()") -> str:
    """Enclose the strings in items in the specified characters:
    ['foo','bar'] => '(foo)(bar)'
    If encloseChars is length one, put only one character between items."""

    startChar = joinChars = encloseChars[0]
    endChar = encloseChars[-1]
    if len(encloseChars) > 1:
        joinChars = endChar + startChar
    
    return startChar + joinChars.join(items) + endChar


def RawBlobify(item: str) -> str:
    """Convert item to lowercase, remove diacritics, special characters, 
    remove html tags, ++Kind++ markers, and Markdown hyperlinks, and normalize whitespace."""
    output = re.sub(r'[‘’"“”]',"'",item) # Convert all quotes to single quotes
    output = output.replace("–","-").replace("—","-") # Conert all dashes to hypens
    output = Utils.RemoveDiacritics(output.lower())
    output = re.sub(r"\<[^>]*\>","",output) # Remove html tags
    output = re.sub(r"!?\[([^]]*)\]\([^)]*\)",r"\1",output) # Extract text from Markdown hyperlinks
    output = output.replace("++","") # Remove ++ bold format markers
    output = re.sub(r"[|]"," ",output) # convert these characters to a space
    output = re.sub(r"[][#()@_*]^","",output) # remove these characters
    output = re.sub(r"\s+"," ",output.strip()) # normalize whitespace
    return output

gBlobDict = {}
gInputChars:set[str] = set()
gOutputChars:set[str] = set()
gNonSearchableTeacherRegex = None
def Blobify(items: Iterable[str],alphanumericOnly = False) -> Iterator[str]:
    """Convert strings to lowercase, remove diacritics, special characters, 
    remove html tags, ++ markers, and Markdown hyperlinks, and normalize whitespace.
    Also remove teacher names who haven't given search consent."""

    global gNonSearchableTeacherRegex
    if gNonSearchableTeacherRegex is None:
        nonSearchableTeachers = set()
        for teacher in gDatabase["teacher"].values(): # Add teacher names
            if teacher["searchable"]:
                continue
            nonSearchableTeachers.update(RawBlobify(teacher["fullName"]).split(" "))

        for prefix in gDatabase["prefix"]: # But discard generic titles
            nonSearchableTeachers.discard(RawBlobify(prefix))
        Alert.debug(len(nonSearchableTeachers),"non-consenting teachers:",nonSearchableTeachers)

        if nonSearchableTeachers:
            gNonSearchableTeacherRegex = Utils.RegexMatchAny(nonSearchableTeachers,literal=True)
        else:
            gNonSearchableTeacherRegex = r"^a\bc" # Matches nothing


    for item in items:
        gInputChars.update(item)
        blob = re.sub(gNonSearchableTeacherRegex,"",RawBlobify(item)) # Remove nonconsenting teachers
        blob = re.sub(r"\s+"," ",blob.strip()) # Normalize or remove whitespace
        if alphanumericOnly:
            blob = re.sub(r"\W","",blob.strip()) # Remove all non-alphanumeric characters
        gOutputChars.update(blob)
        if gOptions.debug:
            gBlobDict[item] = blob
        if blob:
            yield blob

def AllNames(teachers:Iterable[str]) -> Iterator[str]:
    "Yield the names of teachers; include full and attribution names if they differ"
    teacherDB = gDatabase["teacher"]
    for t in teachers:
        yield teacherDB[t]["fullName"]
        if teacherDB[t]["attributionName"] != teacherDB[t]["fullName"]:
            yield teacherDB[t]["attributionName"]

def ExcerptBlobs(excerpt: dict) -> list[str]:
    """Create a list of search strings corresponding to the items in excerpt."""
    returnValue = []
    for item in Filter.AllItems(excerpt):
        aTags = item.get("tags",[])
        if item is excerpt:
            qTags = aTags[0:item["qTagCount"]]
            aTags = aTags[item["qTagCount"]:]
        else:
            qTags = []

        bits = [
            Enclose(Blobify([item["text"]]),"^"),
            Enclose(Blobify(AllNames(item.get("teachers",[]))),"{}"),
            Enclose(Blobify(qTags),"[]") if qTags else "",
            "//",
            Enclose(Blobify(aTags),"[]"),
            "|",
            Enclose(Blobify([item["kind"]],alphanumericOnly=True),"#"),
            Enclose(Blobify([gDatabase["kind"][item["kind"]]["category"]],alphanumericOnly=True),"&")
        ]
        if item is excerpt:
            bits.append(Enclose(Blobify([excerpt["event"] + f"@s{excerpt['sessionNumber']:02d}"]),"@"))
        
        joined = "".join(bits)
        for fTag in itertools.chain(excerpt["fTags"],excerpt.get("fragmentFTags",())):
            tagCode = f"[{RawBlobify(fTag)}]"
            joined = joined.replace(tagCode,tagCode + "+")
        returnValue.append(joined)
    return returnValue

def OptimizedExcerpts() -> list[dict]:
    returnValue = []
    formatter = Prototype.Formatter()
    formatter.excerptOmitSessionTags = False
    formatter.showHeading = False
    formatter.headingShowTeacher = False
    for x in Database.RemoveFragments(gDatabase["excerpts"]):
        xDict = {"session": Database.ItemCode(event=x["event"],session=x["sessionNumber"]),
                 "blobs": ExcerptBlobs(x),
                 "html": formatter.HtmlExcerptList([x])}
        returnValue.append(xDict)
    return returnValue

def SessionHeader() -> dict[str,str]:
    "Return a dict of session headers rendered into html."
    returnValue = {}
    formatter = Prototype.Formatter()
    formatter.headingShowTags = False
    formatter.headingShowTeacher = False

    for s in gDatabase["sessions"]:
        returnValue[Database.ItemCode(s)] = formatter.FormatSessionHeading(s,horizontalRule=False)
    
    return returnValue

def AlphabetizeName(string: str) -> str:
    return Utils.RemoveDiacritics(string).lower()

def KeyTopicBlobs() -> Iterator[dict]:
    """Return a blob for each key topic."""

    for topic in gDatabase["keyTopic"].values():
        yield {
            "blobs": ["".join([
                Enclose(Blobify([topic["topic"]]),"^"),
                Enclose(Blobify([topic["pali"]]),"<>")
                ])],
            "html": re.sub(r"\)$",f"{Prototype.FA_STAR})",Prototype.HtmlKeyTopicLink(topic["code"],count=True))
                # Add a star before the last parenthesis to indicate these are featured excerpts.
        }

def SubtopicBlob(subtopic:str) -> str:
    "Make a search blob from this subtopic."

    subtopic = gDatabase["subtopic"][subtopic]
    bits = [
        Enclose(Blobify(Database.SubtagIterator(subtopic)),"[]"),
        Enclose(Blobify([subtopic["pali"]]),"<>"),
        Enclose(Blobify([subtopic["displayAs"]]),"^"),
    ]
    blob = "".join(bits)
    return blob

def SubtopicBlobs() -> Iterator[dict]:
    """Return a blob for each subtopic, sorted alphabetically."""

    alphabetizedSubtopics = [(AlphabetizeName(subtopic["displayAs"]),subtopic["tag"]) for subtopic in gDatabase["subtopic"].values()]
    alphabetizedSubtopics.sort()

    for _,subtopic in alphabetizedSubtopics:
        s = gDatabase["subtopic"][subtopic]

        if s["fTagCount"]:
            fTagStr = f"{s['fTagCount']}{Prototype.FA_STAR}/"
        else:
            fTagStr = ""
        relevantCount = Database.CountExcerpts(Filter.MostRelevant(Database.SubtagIterator(s))(gDatabase["excerpts"]),countSessionExcerpts=True)
        
        htmlParts = [
            Prototype.HtmlSubtopicLink(subtopic).replace(".html","-relevant.html"),
            f"({fTagStr}{relevantCount})"
        ]
        if s["pali"]:
            htmlParts.insert(1,f"({s['pali']})")

        yield {
            "blobs": [SubtopicBlob(subtopic)],
            "html": " ".join(htmlParts)
        }

def TagBlob(tagName:str) -> str:
    "Make a search blob from this tag."

    subsumesTags = Database.SubsumesTags()
    bits = []
    for tagData in [gDatabase["tag"][tagName]] + subsumesTags.get(tagName,[]):
        bits += [
            Enclose(Blobify(sorted({tagData["tag"],tagData["fullTag"]})),"[]"), # Use sets to remove duplicates
            Enclose(Blobify(sorted({tagData["pali"],tagData["fullPali"]})),"<>"),
            Enclose(Blobify(tagData["alternateTranslations"] + tagData["glosses"]),"^^")
        ]
        if tagData["number"]:
            bits.append("^" + tagData["number"] + "^")

    blob = "".join(bits)
    if "topicHeading" in gDatabase["tag"][tagName]: # If this tag is listed under a key topic,
        blob = blob.replace("]","]+") # add "+" after each tag closure.
    return blob

def TagBlobs() -> Iterator[dict]:
    """Return a blob for each tag, sorted alphabetically."""

    alphabetizedTags = [(AlphabetizeName(tag["fullTag"]),tag["tag"]) for tag in gDatabase["tag"].values() 
                        if tag["htmlFile"] and not ParseCSV.TagFlag.HIDE in tag["flags"]]
    alphabetizedTags.sort()

    for _,tag in alphabetizedTags:
        yield {
            "blobs": [TagBlob(tag)],
            "html": Prototype.TagDescription(gDatabase["tag"][tag],fullTag=True,drilldownLink=True,flags=Prototype.TagDescriptionFlag.SHOW_STAR)
        }

def TeacherBlobs() -> Iterator[dict]:
    """Return a blob for each teacher, sorted alphabetically."""

    teachersWithPages = [t for t in gDatabase["teacher"].values() if t["htmlFile"]]

    alphabetizedTeachers = Prototype.AlphabetizedTeachers(teachersWithPages)

    for name,teacher in alphabetizedTeachers:
        yield {
            "blobs": [Enclose(Blobify(AllNames([teacher["teacher"]])),"{}")],
            "html": re.sub("(^<p>|</p>$)","",Prototype.TeacherDescription(teacher,name)).strip()
                # Remove the paragraph markers added by TeacherDescription
        }

def EventBlob(event: dict[str],listedTeachers: list[str]) -> str:
    """Return a search blob for this event."""
    titles = [event["title"]]
    if event["subtitle"]:
        titles.append(event["subtitle"])

    bits = [
        Enclose(Blobify(titles),"^"),
        Enclose(Blobify(AllNames(listedTeachers)),"{}"),
        Enclose(Blobify(event["tags"]),"[]"),
        "|",
        Enclose(Blobify(event["series"],alphanumericOnly=True),"#"),
        Enclose(Blobify([event["venue"]],alphanumericOnly=True),"&"),
        Enclose(Blobify([event["code"]]),"@")
    ]
    return "".join(bits)

def EventBlobs() -> Iterator[dict]:
    """Return a blob for each event."""
    for event in gDatabase["event"].values():
        sessionTeachers = set()
        for session in Database.SessionDict()[event["code"]].values():
            sessionTeachers.update(session["teachers"])
        listedTeachers = [teacherCode for teacherCode in event["teachers"] if teacherCode in sessionTeachers]

        tagString = "".join(f'[{Prototype.HtmlTagLink(tag)}]' for tag in event["tags"])

        lines = [
            f"{Database.ItemCitation(event)}{': ' + event['subtitle'] if event['subtitle'] else ''} {tagString}",
            Prototype.ItemList([gDatabase["teacher"][t]["attributionName"] for t in listedTeachers])
        ]

        yield {
            "blobs": [EventBlob(event,listedTeachers)],
            "html": "<br>".join(lines)
        } 

def AddSearch(searchList: dict[str,dict],code: str,name: str,blobsAndHtml: Iterator[dict]) -> None:
    """Add the search (tags, teachers, etc.) to searchList.
    code: a one-letter code to identify the search.
    name: the name of the search.
    blobsAndHtml: an iterator that yields a dict for each search item.
    separator: the html code to separate each displayed search result.
    plural: the plural name of the search. 's' means just add s.
    itemsPerPage: the number of items to show per search display page.
    showAtFirst: the number of items to show before displaying the "more" prompt in a multi-search.
    divClass: the class of <div> tag to enclose the search in."""

    searchList[code] = {
        "code": code,
        "name": name,
        "items": [b for b in blobsAndHtml],
    }

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    pass

def ParseArguments() -> None:
    pass
    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main() -> None:
    optimizedDB = {"searches": {}}

    AddSearch(optimizedDB["searches"],"k","key topic",KeyTopicBlobs())
    AddSearch(optimizedDB["searches"],"b","subtopic",SubtopicBlobs())
    AddSearch(optimizedDB["searches"],"g","tag",TagBlobs())
    AddSearch(optimizedDB["searches"],"t","teacher",TeacherBlobs())
    AddSearch(optimizedDB["searches"],"e","event",EventBlobs())
    AddSearch(optimizedDB["searches"],"x","excerpt",OptimizedExcerpts())
    optimizedDB["searches"]["x"]["sessionHeader"] = SessionHeader()

    optimizedDB["searches"]["random"] = {"items":SetupRandom.RemakeRandomExcerpts(shuffle=False)}
    optimizedDB["blobDict"] = list(gBlobDict.values())

    Alert.debug("Removed these chars:","".join(sorted(gInputChars - gOutputChars)))
    Alert.debug("Characters remaining in blobs:","".join(sorted(gOutputChars)))

    with open(Utils.PosixJoin(gOptions.prototypeDir,"assets","SearchDatabase.json"), 'w', encoding='utf-8') as file:
        json.dump(optimizedDB, file, ensure_ascii=False, indent=2)