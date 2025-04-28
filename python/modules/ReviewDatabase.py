"""Check SpreadsheetDatabase.json for errors, inconsistencies, and incompleteness.
"""

from __future__ import annotations

import os, bisect, csv, re
from functools import lru_cache
import Database, Filter
import Utils, Database, Alert
import FileRegister
import ParseCSV
from typing import Iterable
from collections import defaultdict

@lru_cache(maxsize=None)
def AllKeyTopicTags() -> set[str]:
    """Return the set of tags included under any key topic."""

    keyTopicTags = set()
    for subtopic in gDatabase["subtopic"].values():
        keyTopicTags.add(subtopic["tag"])
        keyTopicTags.update(subtopic["subtags"])
    
    return keyTopicTags

@lru_cache(maxsize=None)
def SignificantSubtagsWithoutFTags() -> set[str]:
    """Return the set of tags that: 
    1) Are included under a subtopic but are not the subtopic itself.
    2) The subtopic is not marked as reviewed
    3) Have no featured excerpts.
    4) Have more excerpts than the significance threshold.
    5) Have more than signficantSubtagPercent of the total excerpts in their subtag"""

    tags = set()
    for subtopic in gDatabase["subtopic"].values():
        if subtopic["status"] == "Reviewed":
            continue
        for tagName in Database.SubtagIterator(subtopic):
            tag = gDatabase["tag"][tagName]
            excerptCount = tag.get("excerptCount",0)
            if not tag.get("fTagCount",0) and \
                    excerptCount >= gOptions.significantTagThreshold and \
                    excerptCount >= gOptions.signficantSubtagPercent * subtopic["excerptCount"] // 100:
                tags.add(tagName)
            
    return tags

def OptimalFTagCount(tagOrSubtopic: dict[str],database:dict[str] = {}) -> tuple[int,int,int]:
    """For a given tag or subtopic, returns the tuple (minFTags,maxFTags,difference).
    tagOrSubtopic: a tag or subtopic dict
    database: the under-construction database if gDatabase isn't yet initialized.
    minFTags,maxFTags: heuristic estimates of the optimal number of featured excerpts.
    difference: the difference between the actual number of fTags and these limits;
        0 if minFTags <= fTagCount <= maxFTags"""

    if not database:
        database = gDatabase
    soloSubtopics = Database.SoloSubtopics()
    subtopic = ("topicCode" in tagOrSubtopic or tagOrSubtopic["tag"] in soloSubtopics)
            # Use the subtopic formula for tags which are subtopics containing no subtags

    # Start with an estimate based on the number of excerpts for this tag/subtopic
    excerptCount = tagOrSubtopic.get("excerptCount",0)
    if subtopic:
        minFTags = bisect.bisect_right((6,18,54,144,384,1024),excerptCount)
    else:
        minFTags = bisect.bisect_right((12,30,72,180,480,1278),excerptCount)
    maxFTags = bisect.bisect_right((4,8,16,32,80,200,500,1250),excerptCount)

    # Then add fTags to subtopics with many significant subtags
    significantTags = 0
    insignificantTags = -1
    for subtag in Database.SubtagIterator(tagOrSubtopic):
        if database["tag"][subtag].get("excerptCount",0) >= gOptions.significantTagThreshold:
            significantTags += 1
        else:
            insignificantTags += 1

    # oldMin,oldMax = minFTags,maxFTags
    minFTags += (2*significantTags + insignificantTags) // 10
    maxFTags += (4*significantTags + 2*insignificantTags) // 10

    #if oldMax != maxFTags:
    #    Alert.extra(tagOrSubtopic,"now needs",minFTags,"-",maxFTags,"fTags. Subtags:",significantTags,"significant;",insignificantTags,"insignificant.")

    fTagCount = tagOrSubtopic.get("fTagCount",0)
    difference = min(fTagCount - minFTags,0) or max(fTagCount - maxFTags,0)

    return minFTags,maxFTags,difference

def FTagStatusCode(tagOrSubtopic: dict[str]) -> str:
    """Return a one-character code indicating the status of this tag or subtopic's featured excerpts."""

    tagName = tagOrSubtopic["tag"]
    _,_,diffFTag = OptimalFTagCount(tagOrSubtopic)
    if tagOrSubtopic.get("status","") == "Reviewed" or \
            (tagName in Database.SoloSubtopics() and gDatabase["subtopic"][tagName]["status"] == "Reviewed"):
        prefixChar = "☑"
    elif tagOrSubtopic.get("fTagCount",0) == 0:
        prefixChar = "∅"
    else:
        prefixChar = "⊟☐⊞"[(diffFTag > 0) - (diffFTag < 0) + 1]
        if diffFTag == 0 and tagOrSubtopic.get("status","") == "Sorted":
            prefixChar = "⊡"
    return prefixChar

def VerifyListCounts() -> None:
    # Check that the number of items in each numbered tag list matches the supertag item count
    tagList = gDatabase["tagDisplayList"]
    for tagIndex,subtagIndices in ParseCSV.WalkTags(tagList,returnIndices=True):
        tag = tagList[tagIndex]["tag"]
        if not tag:
            continue
        tagSubitemCount = gDatabase["tag"][tag]["number"]
        if tagList[tagIndex]["subsumed"] or not tagSubitemCount:
            continue   # Skip virtual, subsumed and unnumbered tags
        
        finalIndex = 0
        for subtag in subtagIndices:
            finalIndexStr = tagList[subtag]["indexNumber"]
            if finalIndexStr:
                finalIndex = re.split(r"[-,]",finalIndexStr)[-1]

        if tagSubitemCount != finalIndex: # Note that this compares two strings
            Alert.warning(f'Notice: Mismatched list count in line {tagIndex} of tag list. {tag} indicates {tagSubitemCount} items, but we count {finalIndex}')

    # Check for duplicate excerpt tags
    for x in gDatabase["excerpts"]:
        if len(set(x["tags"])) != len(x["tags"]):
            Alert.caution(f"Duplicate tags in {x['event']} S{x['sessionNumber']} Q{x['excerptNumber']} {x['tags']}")

def AuditNames() -> None:
    """Write assets/NameAudit.csv summarizing the information in the Tag, Teacher, and Name sheets.
    This can be used to check consistency and see which teachers still need ordination dates."""

    teacherFields = ["attributionName","group","lineage","indexExcerpts","indexSessions","searchable","teacherPage","attribute","allowTag"]
    allFields = ["name","sortBy","nameEntry","tagEntry","teacherEntry","dateText","dateKnown","tag","supertag"] + teacherFields

    def NameData() -> dict:
        "Return a dictionary with keys for the name audit."
        d = dict.fromkeys(allFields,"")
        d["sortBy"] = 0.0
        d["nameEntry"] = d["tagEntry"] = d["teacherEntry"] = False
        d["dateKnown"] = "unknown"
        return d
    
    names = defaultdict(NameData)

    # Copy data from tags
    for supertag,subtags in ParseCSV.WalkTags(gDatabase["tagDisplayList"]):
        if ParseCSV.TagFlag.SORT_SUBTAGS in supertag["flags"] or supertag["tag"] == "Thai Forest Tradition":
            for tag in subtags:
                if not tag["tag"] or gDatabase["tag"][tag["tag"]]["subtags"]: # Names don't have subtags
                    continue
                n = names[gDatabase["tag"][tag["tag"]]["fullTag"]]
                n["tagEntry"] = True
                n["tag"] = gDatabase["tag"][tag["tag"]]["tag"]
                n["supertag"] = supertag["tag"]

   # Copy data from teachers
    for teacher in gDatabase["teacher"].values():
        names[teacher["fullName"]]["teacherEntry"] = True
        for field in teacherFields:
            names[teacher["fullName"]][field] = teacher[field]
    
    # Copy data from names sheet
    dateHierarchy = ["exactDate","knownMonth","knownYear","estimatedYear"]
    for name in gDatabase["name"].values():
        n = names[name["fullName"]]
        n["nameEntry"] = True
        if name["sortBy"]:
            n["sortBy"] = float(name["sortBy"])
        for dateField in dateHierarchy:
            if name[dateField]:
                n["dateText"] = name[dateField]
                n["dateKnown"] = dateField
                break

    for name,n in names.items():
        n["name"] = name

    # Check names for potential problems
    lineageExpectedSupertag = {"Thai disciples of Ajahn Chah":"Thai Ajahn Chah lineage",
                        "Western disciples of Ajahn Chah":"Western Ajahn Chah lineage",
                        "Other Thai Forest":"Thai teachers",
                        "Other Thai":"Other Thai monastics",
                        "Other Theravāda":"Other Theravāda monastics",
                        "Vajrayāna":"Mahāyāna monastics"}
    groupExpectedSupertag = {"Lay teachers":"Lay teachers"}
    namesByDate = defaultdict(list)
    for n in names.values():
        if n["tag"] and n["attributionName"] and n["tag"] != n["attributionName"]:
            Alert.notice(f"Short names don't match: tag: {repr(n['tag'])}; attributionName: {repr(n['attributionName'])}.")
        if n["supertag"] and n["lineage"] and lineageExpectedSupertag.get(n["lineage"],n["supertag"]) != n["supertag"]:
            Alert.caution(f"{n['name']} mismatch: lineage: {n['lineage']}, supertag: {n['supertag']}")
        if n["supertag"] and n["group"] and groupExpectedSupertag.get(n["group"],n["supertag"]) != n["supertag"]:
            Alert.caution(f"{n['name']} mismatch: group: {n['group']}, supertag: {n['supertag']}")
        namesByDate[n["sortBy"]].append(n)
    
    for date,namesWithDate in namesByDate.items():
        if len(namesWithDate) < 2 or not date:
            continue
        alertItems = [[n["name"] for n in namesWithDate],f"all have date {date}."]
        duplicateSupertags = Utils.Duplicates(n["supertag"] for n in namesWithDate if n["supertag"])
        for s in duplicateSupertags:
            alertItems.append(f"This will cause ambiguous sort order under supertag {s}.")
        duplicateGroups = Utils.Duplicates(n["group"] for n in namesWithDate if n["group"])
        for g in duplicateGroups:
            alertItems.append(f"This will cause ambiguous sort order in teacher group {g}.")

        if len(alertItems) > 2:
            Alert.caution(*alertItems)

    """ The code below isn't working. Fix it only if needed.
    # Configure sort order
    supertags = set(n["supertag"] for n in names.values())
    supertagIndices = {}
    for tag in supertags:
        for n,tagEntry in enumerate(gDatabase["tagDisplayList"]):
            if tagEntry.get("virtualTag",None):
                print(tagEntry["virtualTag"])
            if tagEntry["tag"] == tag or tagEntry.get("virtualTag",None) == tag:
                supertagIndices[tag] = n
                break

    def SortKey(name) -> tuple:
        supertag = name["supertag"] or lineageExpectedSupertag.get(name["lineage"],None) or groupExpectedSupertag.get(name["group"],None)
        if supertag:
            if name["sortBy"]:
                return supertagIndices[supertag], name["sortBy"]
            else:
                return supertagIndices[supertag], 9999.0
        else:
            return 9999, name["sortBy"]

    nameList = sorted(names.values(),key=SortKey)
    for name in nameList:
        name["sortBy"] = SortKey(name)

    with open(Utils.PosixJoin(gOptions.prototypeDir,"assets/NameAudit.csv"), 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(allFields)
        for n in nameList:
            writer.writerow(n.values())

    Alert.info("Wrote",len(nameList),"names to assets/NameAudit.csv.") """

def CheckAttributions() -> None:
    """Give warnings for unattributed excerpts and annotations."""

    for x in gDatabase["excerpts"]:
        for item in Filter.AllItems(x):
            if item["kind"] == "Other" and not item["teachers"]:
                Alert.caution(item,"takes teachers but does not have any.")

def CheckTags() -> None:
    """Raise a caution if there are unsorted tags."""
    unsortedTags = gDatabase["tag"].get("New unsorted tags",None)
    if unsortedTags:
        Alert.caution("There are",len(unsortedTags["subtags"]),"unsorted tags:",unsortedTags["subtags"])

def CheckRelatedTags() -> None:
    """Print alerts if related tags are duplicated elsewhere in the tag info page."""
    for tagInfo in gDatabase["tag"].values():
        otherTags = set(tagInfo["subtags"])
        otherTags.update(tagInfo["supertags"])
        overlap = otherTags & set(tagInfo["related"])
        if overlap:
            Alert.caution(tagInfo,"related tags",overlap,"are already mentioned as subtags or supertags.")

def FeaturedExcerptSummary(subtopicOrTag: str,header: bool = False,printFTag: bool = False) -> str:
    """Return a list of this subtopic's featured excerpts in tab separated values format."""
    lines = []
    if header:
        columns = ["fTagOrder","code","duration","kind","text"]
        if printFTag:
            columns[1:1] = ["fTag","topic"]
        lines.append("\t".join(columns))

    subtopicOrTag = gDatabase["subtopic"].get(subtopicOrTag,None) or gDatabase["tag"].get(subtopicOrTag)
    if "topicCode" in subtopicOrTag:
        tags = [subtopicOrTag["tag"]] + list(subtopicOrTag["subtags"])
    else:
        tags = [subtopicOrTag["tag"]]
    featuredExcerpts = Filter.FTag(tags)(gDatabase["excerpts"])
    featuredExcerpts = sorted(featuredExcerpts,key=lambda x: Database.FTagOrder(x,tags))
    for x in featuredExcerpts:
        fTagAndOrder = Database.FTagAndOrder(x,tags)
        items = [
            str(fTagAndOrder[1]),
            Database.ItemCode(x),
            x["duration"],
            x["kind"],
            Utils.EllideText(x["text"],70)
        ]
        if printFTag:
            subtopic = gDatabase["tag"][fTagAndOrder[0]].get("partOfSubtopics",(0,))[0]
            topic = gDatabase["subtopic"][subtopic]["topicCode"] if subtopic else ""
            items[1:1] = [fTagAndOrder[0],topic]
        lines.append("\t".join(items))
    return "\n".join(lines)

def CheckFTagOrder() -> None:
    """Print alerts when there is ambiguity sorting featured excerpts."""
    for subtopicOrTag in Database.SubtopicsAndTags():
        tags = [subtopicOrTag["tag"]]
        if "topicCode" in subtopicOrTag: # Is this a subtopic?
            tags += list(subtopicOrTag.get("subtags",()))
        featuredExcerpts = Filter.FTag(tags)(gDatabase["excerpts"])
        problems = []
        fTagOrder = set(Database.FTagOrder(x,tags) for x in featuredExcerpts)
        if len(fTagOrder) < len(featuredExcerpts):
            problems.append("ambiguous sort order")
        if any(n > 1000 for n in fTagOrder):
            problems.append("draft featured excerpts")
        if problems:
            Alert.notice(subtopicOrTag,f"has {' and '.join(problems)}:",lineSpacing=0)
            print(FeaturedExcerptSummary(subtopicOrTag["tag"]))
            print()

def LogReviewedFTags() -> None:
    """Write one file for each reviewed subtopic or tag containing its list of featured excerpts so git will flag any changes."""
    directory = "documentation/reviewedFTags/"
    os.makedirs(directory,exist_ok=True)

    def LogFile(subtopicOrTag: dict[str]) -> str:
        "Return the contents of the log file for this subtopic or tag."
        fileLines = ["\t".join(("fTagOrder","excerpt","duration","kind","text")),
            FeaturedExcerptSummary(subtopicOrTag["tag"])]
        
        fTagCount = subtopicOrTag.get("fTagCount",0)
        minFTag,maxFTag,diffFTag = OptimalFTagCount(subtopicOrTag)

        fileLines.append("")
        fileLines.append(f"{fTagCount} featured excerpts; {minFTag}-{maxFTag} optimal.")

        if "displayAs" in subtopicOrTag:
            fileLines += ["","Subtopic tags:",subtopicOrTag["tag"]] + list(subtopicOrTag["subtags"].keys())
        return "\n".join(fileLines)
    
    with FileRegister.HashWriter(directory) as writer:
        for subtopic in gDatabase["subtopic"].values():
            if subtopic["status"] == "Reviewed":
                filename = Utils.RemoveDiacritics(subtopic["tag"]).replace("/","-") + ".tsv"
                writer.WriteTextFile(Utils.PosixJoin("subtopics",filename),LogFile(subtopic))
        for tag in gDatabase["tag"].values():
            if tag["tag"] in gDatabase["reviewedTag"]:
                filename = Utils.RemoveDiacritics(tag["tag"]).replace("/","-") + ".tsv"
                writer.WriteTextFile(Utils.PosixJoin("tags",filename),LogFile(tag))

def NeedsAudioEditing() -> None:
    "Print which excerpts need audio editing."
    amplifyQuestions = [x for x in gDatabase["excerpts"] if ParseCSV.ExcerptFlag.AMPLIFY_QUESTION in x["flags"]]
    if amplifyQuestions:
        Alert.notice("Questions should be amplified for the following",len(amplifyQuestions),"excerpts:",lineSpacing=0)
        print("\n".join(Database.ItemRepr(x) for x in amplifyQuestions))
        print()
    
    audioEditing = [x for x in gDatabase["excerpts"] if ParseCSV.ExcerptFlag.AUDIO_EDITING in x["flags"]]
    if audioEditing:
        Alert.notice("The following",len(audioEditing),"excerpts need audio editing:",lineSpacing=0)
        print("\n".join(Database.ItemRepr(x) for x in audioEditing))
        print()

def DumpCSV(directory:str) -> None:
    "Write a summary of gDatabase to csv files in directory."

    os.makedirs(directory,exist_ok=True)

    columns = ["event","sessionNumber","excerptNumber","indentLevel","kind","flags","teachers","text","tags","duration"]
    with open(Utils.PosixJoin(directory,"excerpts.csv"), 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for x in gDatabase["excerpts"]:
            for i in Filter.AllSingularItems(x):
                duplicate = dict(i)
                duplicate["teachers"] = ";".join(gDatabase["teacher"][t]["attributionName"] for t in i.get("teachers",[]))
                duplicate["tags"] = ";".join(i.get("tags",[]))
                writer.writerow(duplicate.get(field,"") for field in columns)

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--dumpCSV',type=str,default='',help='Dump a summary of the database to csv files to this directory.')
    parser.add_argument('--significantTagThreshold',type=int,default=12,help='Tags count as significant if they have this many excerpts.')
    parser.add_argument('--signficantSubtagPercent',type=int,default=25,help="Subtags count as significant if they account for more than this percentage of their subtopics' excerpts.")

def ParseArguments() -> None:
    pass    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def main() -> None:
    VerifyListCounts()
    AuditNames()
    # CheckAttributions()
    CheckTags()
    CheckRelatedTags()
    CheckFTagOrder()
    LogReviewedFTags()
    NeedsAudioEditing()

    if gOptions.dumpCSV:
        DumpCSV(gOptions.dumpCSV)
    
