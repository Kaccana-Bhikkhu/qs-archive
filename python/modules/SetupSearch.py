"""Create assets/SearchDatabase.json for easily searching the excerpts.
"""

from __future__ import annotations

import os, json, re
import Database, BuildReferences, Suttaplex
import Utils, Alert, ParseCSV, Build, Filter, Mp3DirectCut
import Html2 as Html
from typing import Iterable, Iterator, Callable
import itertools
from collections import Counter
from datetime import timedelta
from bisect import bisect_right
from SetupFeatured import FeaturedExcerptFilter

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
    output = re.sub(r"\{[^>]*\}","",output) # Remove template evaluation expressions, e.g. {teachers}
    output = re.sub(r"!?\[([^]]*)\]\([^)]*\)",r"\1",output) # Extract text from Markdown hyperlinks
    output = output.replace("++","") # Remove ++ bold format markers
    output = re.sub(r"[|]"," ",output) # convert these characters to a space
    output = re.sub(r"[][#()@_*^]","",output) # remove these characters
    output = re.sub(r"\s+"," ",output.strip()) # normalize whitespace
    return output

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
        if gOptions.explainExcludes or gOptions.debug:
            Alert.essential(len(nonSearchableTeachers),"non-consenting teachers:",nonSearchableTeachers)

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
        if blob:
            yield blob

def AllNames(teachers:Iterable[str]) -> Iterator[str]:
    "Yield the names of teachers; include full and attribution names if they differ"
    teacherDB = gDatabase["teacher"]
    for t in teachers:
        yield teacherDB[t]["fullName"]
        if teacherDB[t]["attributionName"] != teacherDB[t]["fullName"]:
            yield teacherDB[t]["attributionName"]

DURATION_BOUNDARIES = tuple(timedelta(minutes = n) for n in (1,2,5,10))
DURATION_NAMES = ("veryshort","short","medium","long","verylong")

def ExcerptBlobs(excerpt: dict) -> list[str]:
    """Create a list of search strings corresponding to the items in excerpt."""
    returnValue = []
    for item in Filter.AllItems(excerpt):
        if gDatabase["kind"][item["kind"]]["category"] in ("Fragment","Audio"):
            continue
        aTags = item.get("tags",[])
        if item is excerpt:
            qTags = aTags[0:item["qTagCount"]]
            aTags = aTags[item["qTagCount"]:]
        else:
            qTags = []

        text = item["text"]
        if item.get("teachers") and "{teachers}" in text:
            text = text.replace("{teachers}",Build.ListLinkedTeachers(item["teachers"],lastJoinStr = " and "))
        kindList = [item["kind"]]
        if item.get("duration"):
            kindList.append(DURATION_NAMES[bisect_right(DURATION_BOUNDARIES,Mp3DirectCut.ToTimeDelta(item["duration"]))])
        bits = [
            Enclose(Blobify([text]),"^"),
            Enclose(Blobify(AllNames(item.get("teachers",[]))),"{}"),
            Enclose(Blobify(qTags),"[]") if qTags else "",
            "//",
            Enclose(Blobify(aTags),"[]"),
            "|",
            Enclose(Blobify(kindList,alphanumericOnly=True),"#"),
            Enclose(Blobify([gDatabase["kind"][item["kind"]]["category"]],alphanumericOnly=True),"&")
        ]
        if item is excerpt:
            bits.append(Enclose(Blobify(Database.ExcerptNumberCode(excerpt).split("_")),"@"))
        
        joined = "".join(bits)
        for fTag in itertools.chain(excerpt["fTags"],excerpt.get("fragmentFTags",())):
            tagCode = f"[{RawBlobify(fTag)}]"
            joined = joined.replace(tagCode,tagCode + "+")
        returnValue.append(joined)
    return returnValue

def OptimizedExcerpts() -> list[dict]:
    returnValue = []
    formatter = Build.Formatter()
    formatter.SetHeaderlessFormat()
    formatter.excerptNumbers = True
    featuredFilter = FeaturedExcerptFilter()
    for fragmentGroup in Database.GroupFragments(gDatabase["excerpts"]):
        x = fragmentGroup[0]
        xDict = {"session": Database.ItemCode(event=x["event"],session=x["sessionNumber"]),
                 "blobs": ExcerptBlobs(x),
                 "html": formatter.HtmlExcerptList([x]),
                 "uniqueTeachers": len(Filter.AllTeachers(x))}
        if featuredFilter(fragmentGroup):
            xDict["blobs"][0] = xDict["blobs"][0].replace("|#","|#homepage#")
        returnValue.append(xDict)
    return returnValue

def SessionHeader() -> dict[str,str]:
    "Return a dict of session headers rendered into html."
    returnValue = {}
    formatter = Build.Formatter()
    formatter.headingShowTags = False
    formatter.headingShowTeacher = False

    for s in gDatabase["sessions"]:
        returnValue[Database.ItemCode(s)] = formatter.FormatSessionHeading(s,horizontalRule=False)
    
    return returnValue

def CommonWordBlob() -> str:
    """Return a blob of common words; search terms matching it are less important."""
    commonWords = "a in of on to and for not the with after from".split(" ")
    commonWords.extend(p for p in gDatabase["prefix"] if not p.endswith("/"))
    return "|".join(map(RawBlobify,commonWords))

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
            "html": Build.HtmlIcon("Key.png") + " " + Build.HtmlKeyTopicLink(topic["code"],count=True)
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

        if not s["subtags"]:
            blob = TagBlob(s["tag"])
            if s["tag"] != s["displayAs"]:
                blob += Enclose([RawBlobify(s["displayAs"])],"^")
            yield {
                "blobs": [blob],
                "html": Build.HtmlIcon("tag") + " " + Build.TagDescription(gDatabase["tag"][s["tag"]],listAs=s["displayAs"])
            }
            continue

        htmlParts = [
            Build.HtmlIcon("Cluster.png"),
            Build.HtmlSubtopicLink(subtopic),
            f"({s['excerptCount']})"
        ]
        if s["pali"]:
            htmlParts.insert(2,f"({s['pali']})")

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

def TagBlobEntry(tagName:str) -> dict:
    return {
        "blobs": [TagBlob(tagName)],
        "html": Build.HtmlIcon("tag") + " " + Build.TagDescription(gDatabase["tag"][tagName],fullTag=True)
    }

def TagBlobs() -> Iterator[dict]:
    """Return a blob for each tag, sorted alphabetically."""

    soloSubtopics = Database.SoloSubtopics()
    alphabetizedTags = [(AlphabetizeName(tag["fullTag"]),tag["tag"]) for tag in gDatabase["tag"].values() 
                        if tag["htmlFile"] and not ParseCSV.TagFlag.HIDE in tag["flags"]
                        and tag["tag"] not in soloSubtopics]
    alphabetizedTags.sort()

    for _,tag in alphabetizedTags:
        yield TagBlobEntry(tag)

def TeacherBlobs() -> Iterator[dict]:
    """Return a blob for each teacher, sorted alphabetically."""

    teachersWithPages = [t for t in gDatabase["teacher"].values() if t["htmlFile"]]

    alphabetizedTeachers = Build.AlphabetizedTeachers(teachersWithPages)

    for name,teacher in alphabetizedTeachers:
        yield {
            "blobs": [Enclose(Blobify(AllNames([teacher["teacher"]])),"{}")],
            "html": Build.HtmlIcon("user") + " " + re.sub("(^<p>|</p>$)","",Build.TeacherDescription(teacher,name)).strip()
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
        if not listedTeachers:
            listedTeachers = event["teachers"]

        tagString = " ".join(f'[{Build.HtmlTagLink(tag)}]' for tag in event["tags"])

        lines = [
            Build.HtmlIcon("calendar") + " " + f"{Database.ItemCitation(event)}{': ' + event['subtitle'] if event['subtitle'] else ''} {tagString}",
            Build.ItemList(([gDatabase["teacher"][t]["attributionName"] for t in listedTeachers]),lastJoinStr = " and ")
        ]

        yield {
            "blobs": [EventBlob(event,listedTeachers)],
            "html": "<br>".join(lines)
        } 

def SessionBlob(session: dict[str]) -> str:
    """Return a search blob for this session."""

    bits = [
        Enclose(Blobify([session["sessionTitle"]]),"^"),
        Enclose(Blobify(AllNames(session["teachers"])),"{}"),
        Enclose(Blobify(session["tags"]),"[]"),
        "|",
        Enclose(Blobify([Database.ItemCode(session).replace("_","@")]),"@")
    ]
    return "".join(bits)

def SessionBlobs() -> Iterator[dict]:
    """Return a blob for each session."""
    for session in gDatabase["sessions"]:
        tagString = " ".join(f'[{Build.HtmlTagLink(tag)}]' for tag in session["tags"])
        if session["teachers"]:
            teacherList = " – " + Build.ItemList(([gDatabase["teacher"][t]["attributionName"] for t in session["teachers"]]),lastJoinStr = " and ")
        else:
            teacherList = ""
        title = session["sessionTitle"] or f"Session {session['sessionNumber'] or 1}"
        title = Html.Tag("a",{"href":Database.EventLink(session["event"],session["sessionNumber"])})(title)

        lines = [
            Build.HtmlIcon("Cushion-black.png") + f" {title}{teacherList} {tagString}",
        ]

        yield {
            "blobs": [SessionBlob(session)],
            "html": "<br>".join(lines),
            "event": session["event"]
        } 

def SessionEventHtml() -> dict[str,str]:
    """Return a dict of the event information to display after each group of sessions by event."""
    returnValue = {}
    for event in gDatabase["event"].values():
        returnValue[event["code"]] = Html.Tag("p",{"class":"x-cite"})(Database.ItemCitation(event))
    return returnValue

def TextBlobs() -> Iterator[dict]:
    """Return a blob for each text (sutta or vinaya reference)."""
    BuildReferences.ReadReferenceDatabase()
    for text,linkInfo in BuildReferences.gSavedReferences["text"].items():
        reference = BuildReferences.TextReference.FromString(text)
        uid = reference.Uid()
        paliTitle = Suttaplex.Title(uid,False)
        title = Suttaplex.Title(uid)
        textName = Suttaplex.Title(reference.Truncate(1).Uid(),False)
        textSearches = [text,paliTitle,title]
        
        if reference.n0:
            linkedPart = f"{text}: {paliTitle}"
            suffix = f", {title}"
            textSearches.append(textName)
        else:
            linkedPart = f"{textName}"
            suffix = f": {title}"
        suffix += f" ({linkInfo['count']})"
        htmlLink = Html.Tag("a",{"href":"../" + linkInfo["link"]})(linkedPart) + suffix
        yield {
            "blobs": [Enclose(Blobify(textSearches),"^")],
            "html": Build.HtmlIcon("DhammaWheel.png") + " " + htmlLink
        }

def BookBlobs() -> Iterator[dict]:
    """Return a blob for each book."""
    BuildReferences.ReadReferenceDatabase()

    def SortTitle(bookName: str) -> str:
        """Return the title string to sort this book by."""
        return RawBlobify(gDatabase["reference"][bookName]["title"]).replace("'","")

    bookRefs = sorted(BuildReferences.gSavedReferences["book"].items(),
                      key = lambda item:SortTitle(item[0]))
    for bookName,linkInfo in bookRefs:
        reference = BuildReferences.BookReference.FromString(bookName)
        book = gDatabase["reference"][bookName]
        textSearches = [book["title"]]
        if not reference.IsCommentary() and book["year"]:
            textSearches.append(book["year"])
        
        linkedPart = reference.FullName(showYear = False)
        suffix = f" ({linkInfo['count']})"
        if book["author"]:
            authorNames = [gDatabase["teacher"][a]["attributionName"] for a in book["author"]]
            suffix = f" by {Build.ItemList(authorNames,lastJoinStr = ' and ')}" + suffix
            
        htmlLink = Html.Tag("a",{"href":"../" + linkInfo["link"]})(linkedPart) + suffix
        yield {
            "blobs": [Enclose(Blobify(textSearches),"^") + 
                      Enclose(Blobify(AllNames(book["author"])),"{}")],
            "html": Build.HtmlIcon("book-open") + " " + htmlLink
        }

def AuthorBlobs() -> Iterator[dict]:
    """Return a blob for each author (teacher credited with books)."""
    BuildReferences.ReadReferenceDatabase()

    bookCount = Counter()
    for book in BuildReferences.gSavedReferences["book"]:
        for author in gDatabase["reference"][book]["author"]:
            bookCount[author] += 1

    authorRecords = [gDatabase["teacher"][a] for a in BuildReferences.gSavedReferences["author"]]
    alphabetizedAuthors = Build.AlphabetizedTeachers(authorRecords)

    for name,authorInfo in alphabetizedAuthors:
        author = authorInfo["teacher"]
        htmlLink = Html.Tag("a",{"href":BuildReferences.ReferenceLink("author",author)})(name)
        yield {
            "blobs": [Enclose(Blobify(AllNames([author])),"{}")],
            "html": Build.HtmlIcon("user") + " " + htmlLink + f" ({bookCount[author]})"
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

def AllBlobs(database:dict[str]) -> Iterable[str]:
    """Yield all blobs in database"""

    for search in database["searches"].values():
        for item in search["items"]:
            yield from item["blobs"]
    
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
    AddSearch(optimizedDB["searches"],"s","session",SessionBlobs())
    optimizedDB["searches"]["s"]["eventHtml"] = SessionEventHtml()
    AddSearch(optimizedDB["searches"],"p","text",TextBlobs()) # p for Pali
    AddSearch(optimizedDB["searches"],"o","book",BookBlobs()) # only letter available
    AddSearch(optimizedDB["searches"],"a","author",AuthorBlobs())
    AddSearch(optimizedDB["searches"],"x","excerpt",OptimizedExcerpts())
    optimizedDB["searches"]["x"]["sessionHeader"] = SessionHeader()
    optimizedDB["searches"]["x"]["commonWordBlob"] = CommonWordBlob()

    if gOptions.debug:        
        Alert.debug("Removed these chars:","".join(sorted(gInputChars - gOutputChars)))
        Alert.debug("Characters remaining in blob texts:                  ","".join(sorted(gOutputChars)))

        allBlobChars = set()
        teacherBlobChars = set()
        tagBlobChars = set()
        for blob in AllBlobs(optimizedDB):
            allBlobChars.update(blob)
            for teacherMatch in re.findall(r"\{(.*?)\}",blob):
                teacherBlobChars.update(teacherMatch)
            for tagMatch in re.findall(r"\[(.*?)\]",blob):
                tagBlobChars.update(tagMatch)
        Alert.debug("Characters remaining in blobs (including separators):","".join(sorted(allBlobChars)))
        Alert.debug("Characters remaining in teacher blobs               :","".join(sorted(teacherBlobChars)))
        Alert.debug("Characters remaining in tag blobs                   :","".join(sorted(tagBlobChars)))

    with open(Utils.PosixJoin(gOptions.pagesDir,"assets","SearchDatabase.json"), 'w', encoding='utf-8') as file:
        json.dump(optimizedDB, file, ensure_ascii=False, indent=2)