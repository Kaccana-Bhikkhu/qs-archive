"""A module to read csv files from ./csv and create the Database.json file used by subsequent operations"""

from __future__ import annotations

import os, sys, re, csv, json, unicodedata, copy
import Database
import Filter
import Render
import SplitMp3,Mp3DirectCut
from Mp3DirectCut import TimeDeltaToStr,ToTimeDelta
import Utils
from typing import List, Iterator, Tuple, Callable, Any, TextIO
from datetime import timedelta
import Prototype, Alert
from enum import Enum
from collections import Counter, defaultdict
import itertools

class StrEnum(str,Enum):
    pass

class TagFlag(StrEnum):
    VIRTUAL = "."               # A virtual tag can't be applied to excerpts but can have subtags
    PRIMARY = "*"               # The primary instance of this tag in the hierarchical tag list
    PROPER_NOUN = "p"           # Alphabetize as a proper noun
    PROPER_NOUN_SUBTAGS = "P"   # Alphabetize all subtags as proper nouns
    SORT_SUBTAGS = "S"          # Sort this tag's subtags using the "sortBy"
    DISPLAY_GLOSS = "g"         # Display the first gloss in the tag name; e.g. Saṅgha (Monastic community)
    ENGLISH_ALSO = "E"          # Show in English tags as well as Pali or proper nouns
    CAPITALIZE = "C"            # Capitalize the Pali entry; e.g. Nibbāna
    HIDE = "h"                  # Hide this tag in alphabetical lists

class KeyTagFlag(StrEnum):
    PEER_TAG = "+"              # Subtag of previous topic X. Shown as: X, Y, and Z
    SUBORDINATE_TAG = "-"       # Subtag of previous topic X. Shown as: X (includes Y)

SUBTAG_FLAGS = set([KeyTagFlag.PEER_TAG,KeyTagFlag.SUBORDINATE_TAG])
class ExcerptFlag(StrEnum):
    INDENT = "-"            # Increment the annotation's indentLevel. Base indent level is 1.
    ATTRIBUTE = "a"         # Always attribute this item
    OVERLAP = "o"           # This excerpt overlaps with the previous excerpt
    PLURAL = "s"            # Use the plural form, e.g. stories instead of story
    UNQUOTE = "u"           # Remove quotes from this items's template
    FRAGMENT = "f"          # This excerpt is a fragment of the excerpt above it.
    MANUAL_FRAGMENTS = "m"  # Don't automatically extract fragments from this excerpt.
    RELATIVE_AUDIO = "r"    # Interpret Cut Audio and Fragment times relative to excerpt start time.
    ZERO_MARGIN = "z"       # Annotations have zero leftmost margins - useful for videos
        # These flags are informational only:
    AMPLIFY_QUESTION = "Q"  # The question needs to be amplified
    AUDIO_EDITING = "E"     # Would benefit from audio editing

# Each fTagOrder integer is followed by a single character flag specifying where to display this featured excerpt
class FTagOrderFlag(StrEnum):
    EVERYWHERE = "E"        # Display this featured excerpt everywhere (default)
    TAG_ONLY = "T"          # Display only on tag pages (no subtopic pages)
    PRIMARY_SUBTOPIC = "P"  # Display on tag pages and when this tag appears in a subtopic
                            # not followed by an apostrophe
    # Lowercase versions of these flags indicate not to feature the excerpt on the front page
    

gCamelCaseTranslation = {}
def CamelCase(input: str) -> str: 
    """Convert a string to camel case and remove all diacritics and special characters
    "Based on https://www.w3resource.com/python-exercises/string/python-data-type-string-exercise-96.php"""
    
    try:
        return gCamelCaseTranslation[input]
    except KeyError:
        pass
    text = unicodedata.normalize('NFKD', input).encode('ascii', 'ignore').decode('ascii')
    text = text.replace("#"," Number")
    
    text = re.sub(r"([a-zA-Z])([A-Z])(?![A-Z]*\b)",r"\1 \2",text) # Add spaces where the string is already camel case to avoid converting to lower case

    s = re.sub(r"[(_|)?+:\.\/-]", " ", text).title().replace(" ", "")
    if s:
        returnValue = ''.join([s[0].lower(), s[1:]])
    else:
        returnValue = ''

    gCamelCaseTranslation[input] = returnValue
    return returnValue

def CamelCaseKeys(d: dict,reallyChange = True):
    """Convert all keys in dict d to camel case strings"""

    for key in list(d.keys()):
        if reallyChange:
            d[CamelCase(key)] = d.pop(key)
        else:
            CamelCase(key) # Just log what the change would be in the camel case dictionary


def SniffCSVDialect(inFile,scanLength = 4096):
	inFile.seek(0)
	dialect = csv.Sniffer().sniff(inFile.read(scanLength))
	inFile.seek(0)
	return dialect

def BlankDict(inDict):
    "Returns True if all values are either an empty string or None"
    
    for key in inDict:
        value = inDict[key]
        if value is not None and value != '':
            return False
    
    return True

def FirstValidValue(inDict,keyList,inDefault = None):
    for key in keyList:
        if inDict[key]:
            return inDict[key]
    
    return inDefault

def BooleanValue(text: str) -> bool:
    """Returns true if the first three characters of text are 'Yes'.
    This is the standard way of encoding boolean values in the csv files from AP QS Archive main."""
    
    return text[:3] == 'Yes'

def AppendUnique(ioList,inToAppend):
    "Append values to a list unless they are already in it"
    for item in inToAppend:
        if not item in ioList:
            ioList.append(item)

def CSVToDictList(file: TextIO,skipLines = 0,removeKeys = [],endOfSection = None,convertBools = BooleanValue,camelCase = True):
    for _ in range(skipLines):
        file.readline()
    
    reader = csv.DictReader(file)
    output = []
    for row in reader:
        firstDictValue = row[next(iter(row))].strip()
        if firstDictValue == endOfSection:
            break
        elif not BlankDict(row):
            if not firstDictValue:
                Alert.warning("blank first field in",row)
        
            # Increase robustness by stripping values and keys
            for key in list(row):
                row[key] = row[key].strip()
                if key != key.strip():
                    row[key.strip()] = row.pop(key)
            
            if convertBools:
                for key in row:
                    if key[-1:] == '?':
                        row[key] = convertBools(row[key])
            
            if camelCase:
                CamelCaseKeys(row)
            output.append(row)
    
    removeKeys.append("")
    for key in removeKeys:
        for row in output:
            row.pop(key,None)
    
    return output

def SkipModificationLine(file: TextIO) -> None:
    """Skip the first line of the file if it is of the form "Modified:DATE"""
    if file.tell() == 0:
        if not file.readline().startswith("Modified:"):
            file.seek(0)
    
def CSVFileToDictList(fileName,*args,**kwArgs):
    """Read a CSV file and convert it to a list of dictionaries"""
    
    with open(fileName,encoding='utf8') as file:
        SkipModificationLine(file)
        return CSVToDictList(file,*args,**kwArgs)

def ListifyKey(dictList: list|dict,key: str,delimiter:str = ';',removeBlank = True) -> None:
    """Convert the values in a specific key to a list for all dictionaries in dictList.
    First, look for other keys with names like dictKey+'2', etc.
    Then split all these keys using the given delimiter, concatenate the results, and store it in dictKey.
    Remove any other keys found."""
    
    for d in Utils.Contents(dictList):
        if key not in d:
            d[key] = []
            continue

        keyList = [key]
        if key[-1] == '1': # Does the key name end in 1?
            baseKey = key[:-1].strip()
        else:
            baseKey = key
        
        keyIndex = 1
        foundKey = True
        while foundKey:
            keyIndex += 1
            foundKey = False
            for testKey in [baseKey + str(keyIndex),baseKey + ' ' + str(keyIndex)]:
                if testKey in d:
                    keyList.append(testKey)
                    foundKey = True
        
        items = []
        for sequentialKey in keyList:
            items += d[sequentialKey].split(delimiter)
        if removeBlank:
            items = [s.strip() for s in items if s.strip()]
        d[baseKey] = items
                    
        if baseKey == key:
            delStart = 1
        else:
            delStart = 0
        for index in range(delStart,len(keyList)):
            del d[keyList[index]]

def ConvertToInteger(dictList,key,defaultValue = None,reportError:Alert.AlertClass|None = None):
    "Convert the values in key to ints"
    
    def Convert(s: str) -> int:
        try:
            return int(s)
        except ValueError as err:
            if reportError and s:
                reportError("Cannot convert",repr(s),"to an integer in",d)
            return defaultValue

    sequences = frozenset((list,tuple))
    for d in Utils.Contents(dictList):
        if type(d[key]) in sequences:
            d[key] = [Convert(item) for item in d[key]]
        else:
            d[key] = Convert(d[key])

def ListToDict(inList,key = None):
    """Convert a list of dicts to a dict of dicts using key. If key is None, use the first key
    Throw an exception if there are duplicate values."""
    
    if key is None:
        key = next(iter(inList[0]))
    
    outDict = {}
    for item in inList:
        newKey = item[key]
        if newKey in outDict:
            Alert.warning("ListToDict: Duplicate key:",newKey,". Will use the value of the old key:",outDict[newKey])
        else:
            outDict[newKey] = item
    
    return outDict

def DictFromPairs(inList,keyKey,valueKey,camelCase = True):
    "Convert a list of dicts to a dict by taking a single key/value pair from each dict."
    
    outDict = {}
    for item in inList:
        newKey = item[keyKey]
        if newKey in outDict:
            Alert.warning("DictFromPairs: Duplicate key:",newKey,". Will use the value of the old key:",outDict[newKey])
        else:
            outDict[newKey] = item[valueKey]
    
    if camelCase:
        CamelCaseKeys(outDict)
    return outDict

def LoadSummary(database,summaryFileName):
    summaryList = CSVFileToDictList(summaryFileName,skipLines = 1,removeKeys = ["seconds","sortBy"],endOfSection = '<---->')
    
    for numericalKey in ["sessions","excerpts","answersListenedTo","tagsApplied","invalidTags"]:
        ConvertToInteger(summaryList,numericalKey)
    
    database["summary"] = ListToDict(summaryList,"eventCode")

class TagStackItem:
    """Information about a supertag
        tag - str - name of the supertag at this level
        collectSubtags - bool - do we add subtags to this tag?
        subtagIndex - int - index of the next subtag to add to this supertag."""
        
    def __init__(self,tag,collectSubtags = False,indexSubtags = False):
        self.tag = tag
        self.collectSubtags = collectSubtags
        if indexSubtags:
            self.subtagIndex = 1
        else:
            self.subtagIndex = None
    
    def Increment(self,count = 1):
        if self.subtagIndex:
            self.subtagIndex += count
    

def LoadTagsFile(database,tagFileName):
    "Load Tag_Raw from a file and parse it to create the Tag dictionary"

    # First load the raw tags from the csv file
    rawTagList = CSVFileToDictList(tagFileName,skipLines = 1,removeKeys = ["indentedTags","paliTerm","tagMenu","Tag count","paliTagMenu"])
        
    ListifyKey(rawTagList,"alternateTranslations")
    ListifyKey(rawTagList,"glosses")
    ListifyKey(rawTagList,"related")
    ConvertToInteger(rawTagList,"level",reportError=Alert.error)
    
    for item in rawTagList:     
        digitFlag = re.search("[0-9]",item["flags"])
        if digitFlag:
            item["itemCount"] = int(digitFlag[0])
        else:
            item["itemCount"] = 0 if TagFlag.VIRTUAL in item["flags"] else 1

    # Next build the main tag dictionary
    tags = {}
    namePreference = ["abbreviation","fullTag","paliAbbreviation","pali"]
    paliPreference = ["paliAbbreviation","pali"]
    fullNamePreference = ["fullTag","pali"]
    referencedTag = ["subsumedUnder","abbreviation","fullTag","paliAbbreviation","pali"]
    
    # Remove any blank values from the list before looping over it
    rawTagList = [tag for tag in rawTagList if FirstValidValue(tag,namePreference)]
    
    # Redact tags for teachers who haven't given consent - teacher names are never abbreviated, so use fullTag
    unallowedTeachers = [teacher["fullName"] for abbrev,teacher in database["teacher"].items() if not TeacherConsent(database["teacher"],[abbrev],"allowTag")]
    redactedTags = [tag["abbreviation"] or tag["fullTag"] for tag in rawTagList if tag["fullTag"] in unallowedTeachers]
    rawTagList = [tag for tag in rawTagList if tag["fullTag"] not in unallowedTeachers]

    subsumedTags = {} # A dictionary of subsumed tags for future reference
    virtualHeadings = set() # Tags used only as list headers

    tagStack = [] # Supertag ancestry stack
    
    lastTagLevel = 1
    lastTag = TagStackItem("")
    for rawTagIndex,rawTag in enumerate(rawTagList):
        
        tagName = FirstValidValue(rawTag,namePreference)
        tagPaliName = FirstValidValue(rawTag,paliPreference,"")

        rawTag["tag"] = FirstValidValue(rawTag,referencedTag)

        tagDesc = {}
        tagDesc["tag"] = tagName
        tagDesc["pali"] = tagPaliName
        tagDesc["fullTag"] = FirstValidValue(rawTag,fullNamePreference)
        tagDesc["fullPali"] = rawTag["pali"]
        for key in ["number","alternateTranslations","glosses","related","flags"]:
            tagDesc[key] = rawTag[key]
                
        # Assign subtags and supertags based on the tag level. Interpret tag level like indented code sections.
        curTagLevel = rawTag["level"]        
        while (curTagLevel < lastTagLevel):
            tagStack.pop()
            lastTagLevel -= 1
        
        if curTagLevel > lastTagLevel:
            assert curTagLevel == lastTagLevel + 1, f"Level of tag {tagName} increased by more than one."
            if curTagLevel > 1:
                if lastTag.collectSubtags: # If the previous tag was flagged as primary, remove subtags from previous instances and accumulate new subtags
                    tags[lastTag.tag]["subtags"] = []
                elif lastTag.tag not in subsumedTags and not tags[lastTag.tag]["subtags"]: # But even if it's not primary, accumulate subtags if there are no prior subtags
                    lastTag.collectSubtags = True
                
                tagStack.append(lastTag)
 
        tagDesc["subtags"] = []
        rawTag["indexNumber"] = ""
        if curTagLevel > 1:
            tagDesc["supertags"] = [tagStack[-1].tag]
            if tagStack[-1].subtagIndex:
                if rawTag["itemCount"]:
                    rawTag["indexNumber"] = str(tagStack[-1].subtagIndex)
                    tagStack[-1].Increment(rawTag["itemCount"])
            if tagStack[-1].collectSubtags:
                tags[tagStack[-1].tag]["subtags"].append(tagName)
        else:
            tagDesc["supertags"] = []

        lastTagLevel = curTagLevel
        lastTag = TagStackItem(tagName,TagFlag.PRIMARY in rawTag["flags"] and not rawTag["subsumedUnder"],
                               bool(rawTag["number"])) # Count subtags if this tag is numerical
        
        # Subsumed tags don't have a tag entry
        if rawTag["subsumedUnder"]:
            if TagFlag.PRIMARY in tagDesc["flags"] or tagName not in subsumedTags:
                tagDesc["subsumedUnder"] = rawTag["subsumedUnder"]
                subsumedTags[tagName] = tagDesc
            continue
        
        # If this is a duplicate tag, insert only if the primary flag is true
        tagDesc["copies"] = 1
        tagDesc["primaries"] = 1 if TagFlag.PRIMARY in rawTag["flags"] else 0
        if tagName in tags:
            if TagFlag.PRIMARY in rawTag["flags"]:
                tagDesc["copies"] += tags[tagName]["copies"]
                tagDesc["primaries"] += tags[tagName]["primaries"]
                AppendUnique(tagDesc["supertags"],tags[tagName]["supertags"])
            else:
                tags[tagName]["copies"] += tagDesc["copies"]
                tags[tagName]["primaries"] += tagDesc["primaries"]
                AppendUnique(tags[tagName]["supertags"],tagDesc["supertags"])
                continue
        
        if TagFlag.VIRTUAL in rawTag["flags"] and (rawTagIndex + 1 >= len(rawTagList) or rawTagList[rawTagIndex + 1]["level"] <= rawTag["level"]):
            virtualHeadings.add(tagName)
            tagDesc["htmlFile"] = "" # Virtual tags with no subtags don't have a page
        else:
            tagDesc["htmlFile"] = Utils.slugify(tagName) + '.html'
        
        tags[tagName] = tagDesc
    
    for tag in tags.values():
        tag["subtags"] = [t for t in tag["subtags"] if t not in virtualHeadings]
            # Remove virtual headings from subtag lists

    database["tag"] = tags
    database["tagRaw"] = rawTagList
    database["tagSubsumed"] = subsumedTags
    database["tagRedacted"] = redactedTags

kNumberNames = ["zero","one","two","three","four","five","six","seven","eight","nine","ten","eleven","twelve"]


def RemoveUnusedTags(database: dict) -> None:
    """Remove unused tags from the raw tag list before building the tag display list."""

    def TagCount(tag: dict) -> bool:
        return tag.get("excerptCount",0) + tag.get("sessionCount",0) + tag.get("sessionCount",0)

    def NamedNumberTag(tag: dict) -> bool:
        "Does this tag explicitly mention a numbered list?"
        if tag["number"] and int(tag["number"]) < len(kNumberNames):
            return kNumberNames[int(tag["number"])] in tag["fullTag"]
        else:
            return False

    usedTags = set(tag["tag"] for tag in database["tag"].values() if TagCount(tag))
    usedTags.update(t["subsumedUnder"] for t in gDatabase["tagSubsumed"].values())
    for cluster in database["subtopic"].values():
        usedTags.add(cluster["tag"])
        usedTags.update(cluster["subtags"].keys())


    Alert.extra(len(usedTags),"unique tags applied.")
    
    prevTagCount = 0
    round = 0
    while prevTagCount < len(usedTags):
        round += 1
        prevTagCount = len(usedTags)

        for parent,children in WalkTags(database["tagRaw"]):
            anyTagUsed = numberedTagUsed = False
            for childTag in children:
                if childTag["tag"] in usedTags:
                    anyTagUsed = True
                    if childTag["indexNumber"]:
                        numberedTagUsed = True

            if anyTagUsed: # Mark the parent tag as used if any of the children are in use
                usedTags.add(parent["tag"])

            # Mark all numbered tags as used if any other numbered tag is in use or we expect to see a numbered list i.e. "Four Noble Truths"
            if (parent["tag"] in usedTags and NamedNumberTag(parent)) or numberedTagUsed: # Mark all numbered tags as used if
                seenNumberedTagYet = False
                for childTag in children:
                    if childTag["indexNumber"] or not seenNumberedTagYet: # Tags before the numbered list are essential headings
                        usedTags.add(childTag["tag"])
                    if childTag["indexNumber"]:
                        seenNumberedTagYet = True

    """remainingTags = set(usedTags)
    with open("prototype/UsedTags.txt",mode="w",encoding='utf-8') as file:
        for rawTag in database["tagRaw"]:
            tag = rawTag["tag"]
            name = FirstValidValue(rawTag,["fullTag","pali"])

            indent = "     " * (rawTag["level"] - 1)

            if tag in usedTags:
                remainingTags.discard(tag)
                name = name.upper()

            display = indent + (f"{rawTag['indexNumber']}. " if rawTag["indexNumber"] else "") + name + f" ({TagCount(database['tag'][tag])})"

            print(display,file=file)"""
    
    database["tagRaw"] = [tag for tag in database["tagRaw"] if tag["tag"] in usedTags]
    database["tagRemoved"] = [tagName for tagName,tag in database["tag"].items() if tagName not in usedTags]
    database["tag"] = {tagName:tag for tagName,tag in database["tag"].items() if tagName in usedTags}

    noSubsumed = {"subsumedUnder":""}
    for tag in database["tag"].values():
        tag["subtags"] = [t for t in tag["subtags"] if t in usedTags or database["tagSubsumed"].get(t,noSubsumed)["subsumedUnder"] in usedTags]
        tag["related"] = [t for t in tag["related"] if t in usedTags]

def IndexTags(database: dict) -> None:
    """Add listIndex tag to raw tags after we have removed unused tags."""
    tagsSoFar = set()
    for n,tag in enumerate(database["tagDisplayList"]):
        tagName = tag["tag"]
        if not tagName:
            tagName = tag["virtualTag"]
        if tag["subsumed"]:
            continue
        if tagName in tagsSoFar and TagFlag.PRIMARY not in tag["flags"]:
            continue

        tagsSoFar.add(tagName)
        
        database["tag"][tagName]["listIndex"] = n

    tagList = database["tagDisplayList"]
    # Cross-check tag indexes
    for tag in database["tag"]:
        if TagFlag.VIRTUAL not in database["tag"][tag]["flags"]:
            index = database["tag"][tag]["listIndex"]
            assert tag == tagList[index]["tag"],f"Tag {tag} has index {index} but TagList[{index}] = {tagList[index]['tag']}"

    """for tag in database["tag"].values():
        if tag["listIndex"] != tag["newListIndex"]:
            print(f"Mismatched numbers: {tag['tag']}: {tag['listIndex']=}, {tag['newListIndex']=}")"""

def SortTags(database: dict) -> None:
    """Sort subtags of tags with flag 'S' according to sort by dates in Name sheet."""

    datelessTags = []
    for parentIndex,childIndexes in WalkTags(database["tagDisplayList"],returnIndices=True):
        parent = database["tagDisplayList"][parentIndex]
        if TagFlag.SORT_SUBTAGS not in parent["flags"]:
            continue
        
        childIndexes = range(childIndexes[0],childIndexes[-1] + 1)
            # WalkTags omits subtags, so include all tags between the first and the last; 
        children = [database["tagDisplayList"][i] for i in childIndexes]

        def SortByDate(tagInfo:dict) -> float:
            fullTag = database["tag"][tagInfo["tag"]]["fullTag"]
            sortBy = database["name"].get(fullTag,{"sortBy":""})["sortBy"]
            if sortBy:
                try:
                    return float(sortBy)
                except ValueError:
                    pass
            datelessTags.append(fullTag)
            return 9999.0

        baseIndent = children[0]["level"]
        lastDate = None
        tagDates = {}
        for child in children:
            if child["level"] == baseIndent: # Any subtags sort by the date of their parent.
                    # Since the sort is stable, this keeps subtags with their parents.
                lastDate = SortByDate(child)
            tagDates[child["tag"]] = lastDate

        children.sort(key=lambda tag: tagDates[tag["tag"]])
        for index,child in zip(childIndexes,children):
            database["tagDisplayList"][index] = child
    if datelessTags:
        Alert.caution("Cannot find a date for",len(datelessTags),"tag(s) in the Name sheet. These tags will go last.")
        Alert.extra("Dateless tags:",datelessTags)

def CountSubtagExcerpts(database):
    """Add the subtagCount and subtagExcerptCount fields to each item in tagDisplayList which counts the number
    of excerpts which are tagged by this tag or any of its subtags."""

    tagList = database["tagDisplayList"]
    excerptsWithoutFragments = list(Database.RemoveFragments(database["excerpts"]))
    subtags = [None] * len(tagList)
    savedSearches = [None] * len(tagList)
    for parentIndex,childIndexes in WalkTags(tagList,returnIndices=True):
        theseTags = set()
        thisSearch = set()
        for index in childIndexes + [parentIndex]:
            if subtags[index] is None:
                tag = tagList[index]["tag"]
                if tag:
                    subtags[index] = {tag}
                    savedSearches[index] = {id(x) for x in Filter.Tag(tag)(excerptsWithoutFragments)}
                    #print(f"{index} {tag}: {len(savedSearches[index])} excerpts singly")
                else:
                    subtags[index] = set()
                    savedSearches[index] = set()
            
            theseTags.update(subtags[index])
            thisSearch.update(savedSearches[index])
        
        subtags[parentIndex] = theseTags
        savedSearches[parentIndex] = thisSearch
        #print(f"{parentIndex} {tagList[parentIndex]["tag"]}: {len(savedSearches[index])} excerpts singly")
        tagList[parentIndex]["subtagCount"] = len(theseTags) - 1
        tagList[parentIndex]["subtagExcerptCount"] = len(thisSearch)

def CollectKeyTopics(database:dict[str]) -> None:
    """Create keyTopic dictionary from subtopic dictionary."""

    keyTopic = {}
    currentKeyTopic = {}
    primarySubtopics = set()
    thisSubtopic = None
    for subtopic in database["subtopic"].values():
        secondarySubtopic = subtopic["tag"].endswith("'")
        if secondarySubtopic:
            subtopic["tag"] = subtopic["tag"].rstrip("'")

        if subtopic["keyTopic"]:
            currentKeyTopic = {
                "code": subtopic["topicCode"],
                "topic": subtopic["keyTopic"],
                "pali": subtopic["keyTopicPali"],
                "shortNote": subtopic["shortNote"],
                "longNote": subtopic["longNote"],
                "listFile": subtopic["topicCode"] + ".html",
                "subtopics": []
            }
            keyTopic[subtopic["topicCode"]] = currentKeyTopic
        
        if "subtopics" not in database["tag"][subtopic["tag"]]:
            database["tag"][subtopic["tag"]]["partOfSubtopics"] = [] # Add to this empty list later on

        if subtopic["flags"] in SUBTAG_FLAGS:
            thisSubtopic["subtags"][subtopic["tag"]] = subtopic["flags"]
            database["tag"][subtopic["tag"]]["partOfSubtopics"].append(thisSubtopic["tag"])
        else:
            primarySubtopics.add(subtopic["tag"])
            thisSubtopic = subtopic
            subtopic["subtags"] = {}
            subtopic["topicCode"] = currentKeyTopic["code"]

            if "subtopics" not in database["tag"][subtopic["tag"]]:
                database["tag"][subtopic["tag"]]["subtopics"] = []
            database["tag"][subtopic["tag"]]["partOfSubtopics"].append(subtopic["tag"])

            if not subtopic["displayAs"]:
                subtopic["displayAs"] = subtopic["tag"]
            for key in ("shortNote","longNote","keyTopic","keyTopicPali","flags"):
                subtopic.pop(key,None)
            
            currentKeyTopic["subtopics"].append(subtopic["tag"])
        
        if secondarySubtopic:
            thisSubtopic["secondarySubtags"] = thisSubtopic.get("secondarySubtags",[]) + [subtopic["tag"]]
    
    subtagsOnly = set(database["subtopic"]) - primarySubtopics
    for tag in subtagsOnly:
        extraFields = [{key:value} for key,value in database["subtopic"][tag].items() if value and key not in ("tag","flags")]
        if extraFields:
            Alert.notice("CollectKeyTopics: Extra fields in subtag",tag,":",extraFields)
        del database["subtopic"][tag]
    
    ListifyKey(database["subtopic"],"related")
    nonClustersWithRelated = [{c["tag"]:c["related"]} for c in database["subtopic"].values() if c["related"] and not c["subtags"]]
    if nonClustersWithRelated:
        Alert.notice("These",len(nonClustersWithRelated),"subtopics are mapped to tags. Their related tags should be moved to tags.",nonClustersWithRelated)

    for subtopic in database["subtopic"].values():
        if subtopic["subtags"]: # Topics with subtopics link to separate pages in the topics directory
            subtopic["htmlPath"] = f"clusters/{Utils.slugify(subtopic['tag'])}.html"
        else: # Tags without subtopics link to pages in the tags directory
            subtopic["htmlPath"] = f"tags/{database['tag'][subtopic['tag']]['htmlFile']}"

    database["keyTopic"] = keyTopic

def CreateTagDisplayList(database):
    """Generate Tag_DisplayList from Tag_Raw and Tag keys in database
    Format: level, text of display line, tag to open when clicked""" 
    
    tagList = []
    for rawTag in database["tagRaw"]:
        listItem = {}
        for key in ["level","indexNumber","flags"]:
            listItem[key] = rawTag[key]
        
        itemCount = rawTag["itemCount"]
        if itemCount > 1:
            indexNumber = int(rawTag["indexNumber"])
            separator = '-' if itemCount > 1 else ','
            listItem["indexNumber"] = separator.join((str(indexNumber),str(indexNumber + itemCount - 1)))
        
        name = FirstValidValue(rawTag,["fullTag","pali"])
        tag = rawTag["tag"]
        text = name
        
        try:
            excerptCount = database["tag"][tag]["excerptCount"]
        except KeyError:
            excerptCount = 0
        subsumed = bool(rawTag["subsumedUnder"])
        
        if excerptCount > 0 and not subsumed:
            text += " (" + str(excerptCount) + ")"
        
        if rawTag["fullTag"] and rawTag["pali"]:
            text += " [" + rawTag["pali"] + "]"

        if subsumed:
            text += " see " + rawTag["subsumedUnder"]
            if excerptCount > 0:
                text += " (" + str(excerptCount) + ")"
        
        listItem["name"] = name
        listItem["pali"] = rawTag["pali"]
        listItem["excerptCount"] = excerptCount
        listItem["subsumed"] = subsumed
        listItem["text"] = text
            
        if TagFlag.VIRTUAL in rawTag["flags"]:
            listItem["tag"] = "" # Virtual tags don't have a display page
            listItem["virtualTag"] = tag
        else:
            listItem["tag"] = tag
        
        tagList.append(listItem)
    
    database["tagDisplayList"] = tagList
    
    if not gOptions.jsonNoClean:
        del gDatabase["tagRaw"]

def WalkTags(tagDisplayList: list,returnIndices:bool = False,yieldRootTags = False) -> Iterator[Tuple[dict,List[dict]]]:
    """Return (tag,subtags) tuples for all tags that have subtags. Walk the list depth-first."""
    tagStack = []
    for n,tag in enumerate(tagDisplayList):
        tagLevel = tag["level"]
        while len(tagStack) > tagLevel: # If the tag level drops, then yield the accumulated tags and their parent 
            children = tagStack.pop()
            parent = tagStack[-1][-1] # The last item of the next-highest level is the parent tag
            yield parent,children
        
        if tagLevel > len(tagStack):
            if tagLevel != len(tagStack) + 1:
                Alert.error("Level of tag",tag,"increased by more than one.")
                Alert.error("This is a fatal error. Exiting.")
                sys.exit()
            tagStack.append([])
        
        if returnIndices:
            tagStack[-1].append(n)
        else:
            tagStack[-1].append(tag)
    
    while len(tagStack) > 1: # Yield sibling tags still in the list
        children = tagStack.pop()
        parent = tagStack[-1][-1] # The last item of the next-highest level is the parent tag
        yield parent,children
    
    if tagStack and yieldRootTags:
        yield None,tagStack[0]
        

def TeacherConsent(teacherDB: List[dict], teachers: List[str], policy: str, singleConsentOK = False) -> bool:
    """Scan teacherDB to see if all teachers in the list have consented to the given policy. Return False if not.
    If singleConsentOK then only one teacher must consent to return True."""
    
    if gOptions.ignoreTeacherConsent:
        return True
    
    consent = True
    for teacher in teachers:
        if teacherDB[teacher][policy]:
            if singleConsentOK:
                return True
        else:
            consent = False
        
    return consent

def PrepareReferences(reference) -> None:
    """Prepare database["reference"] for use."""

    ListifyKey(reference,"author1")
    ConvertToInteger(reference,"pdfPageOffset")

    # Convert ref["abbreviation"] to lowercase for dictionary matching
    # ref["title"] still has the correct case
    for ref in list(reference.keys()):
        reference[ref.lower()] = reference.pop(ref)


def PrepareTeachers(teacherDB) -> None:
    """Prepare database["teacher"] for use."""
    for t in teacherDB.values():
        if not t.get("attributionName",""):
            t["attributionName"] = t["fullName"]
        if TeacherConsent(teacherDB,[t["teacher"]],"teacherPage") and t.get("excerptCount",0):
            t["htmlFile"] = Utils.slugify(t["attributionName"]) + ".html"
        else:
            t["htmlFile"] = ""

itemAllowedFields = {"startTime": "takesTimes", "endTime": "takesTimes", "teachers": "takesTeachers", "aTag": "takesTags", "qTag": "takesTags"}

def CheckItemContents(item: dict,prevExcerpt: dict|None,kind: dict) -> bool:
    """Print alerts if there are unexpectedly blank or filled fields in item based on its kind."""

    isExcerpt = bool(item["startTime"]) and kind["canBeExcerpt"]
        # excerpts specify a start time
    
    if not isExcerpt and not kind["canBeAnnotation"]:
        Alert.warning(item,"to",prevExcerpt,f": Kind {repr(item['kind'])} is not allowed for annotations.")
    
    for key,permission in itemAllowedFields.items():
        if item[key] and not kind[permission]:
            message = f"has ['{key}'] = {repr(item[key])}, but kind {repr(item['kind'])} does not allow this."
            if isExcerpt or not prevExcerpt:
                Alert.caution(item,message)
            else:
                Alert.caution(item,"to",prevExcerpt,message)

def FinalizeExcerptTags(x: dict) -> None:
    """Combine qTags and aTags into a single list, but keep track of how many qTags there are."""
    x["tags"] = x["qTag"] + x["aTag"]
    x["qTagCount"] = len(x["qTag"])
    if len(x["fTagOrder"]) != len(x["fTags"]):
        Alert.caution(x,f"has {len(x['fTags'])} fTags but specifies {len(x['fTagOrder'])} fTagOrder numbers.")

    if not gOptions.jsonNoClean:
        del x["qTag"]
        del x["aTag"]
        x.pop("aListen",None)
        if not x["fTags"]:
            x.pop("fTagOrder")
            x.pop("fTagOrderFlags",None)
        
        # Remove these keys from all annotations
        for a in x["annotations"]:
            for key in ("qTag","aTag","fTags","fTagOrder","fTagOrderFlags"):
                a.pop(key,None)

def AddExcerptTags(excerpt: dict,annotation: dict) -> None:
    "Combine qTag, aTag, fTag, and fTagOrder keys from an Extra Tags annotation with an existing excerpt."

    for key in ("qTag","aTag","fTags","fTagOrder"):
        excerpt[key] = excerpt.get(key,[]) + annotation.get(key,[])
    excerpt["fTagOrderFlags"] = excerpt.get("fTagOrderFlags","") + annotation.get("fTagOrderFlags","")

def AddAnnotation(database: dict, excerpt: dict,annotation: dict) -> None:
    """Add an annotation to a excerpt."""
    
    if annotation["sessionNumber"] != excerpt["sessionNumber"]:
        Alert.warning("Annotation",annotation,"to",excerpt,f"has a different session number ({annotation['sessionNumber']}) than its excerpt ({excerpt['sessionNumber']})")
    global gRemovedAnnotations
    if annotation["exclude"]:
        excludeAlert(annotation,"to",excerpt,"- exclude flag Yes.")
        gRemovedAnnotations += 1
        return
    if database["kind"][annotation["kind"]].get("exclude",False):
        excludeAlert(annotation,"to",excerpt,"- kind",repr(annotation["kind"]),"exclude flag Yes.")
        gRemovedAnnotations += 1
        return
    
    CheckItemContents(annotation,excerpt,database["kind"][annotation["kind"]])
    if annotation["kind"] == "Extra tags":
        for prevAnnotation in reversed(excerpt["annotations"]): # look backwards and add these tags to the first annotation that supports them
            if "tags" in prevAnnotation:
                prevAnnotation["tags"] += annotation["qTag"]
                prevAnnotation["tags"] += annotation["aTag"] # Annotations don't distinguish between q and a tags,
                AddExcerptTags(prevAnnotation,annotation) # but store qTags and aTags separately in case this annotation is a fragment that will be promoted to an excerpt
                return
        
        AddExcerptTags(excerpt,annotation) # If no annotation takes the tags, give them to the excerpt
        return
    
    kind = database["kind"][annotation["kind"]]
    
    keysToRemove = ["sessionNumber","offTopic","aListen","exclude"]
    
    if kind["takesTeachers"]:
        if not annotation["teachers"]:
            defaultTeacher = kind["inheritTeachersFrom"]
            if defaultTeacher == "Anon": # Check if the default teacher is anonymous
                annotation["teachers"] = ["Anon"]
            elif defaultTeacher == "Excerpt":
                annotation["teachers"] = excerpt["teachers"]
            elif defaultTeacher == "Session" or (defaultTeacher == "Session unless text" and not annotation["text"]):
                ourSession = Database.FindSession(database["sessions"],excerpt["event"],excerpt["sessionNumber"])
                annotation["teachers"] = ourSession["teachers"]
        
        if not (TeacherConsent(database["teacher"],annotation["teachers"],"indexExcerpts") or database["kind"][annotation["kind"]]["ignoreConsent"]):
            # If a teacher of one of the annotations hasn't given consent, we redact the excerpt itself
            if annotation["teachers"] == excerpt["teachers"] and database["kind"][excerpt["kind"]]["ignoreConsent"]:
                pass # Unless the annotation has the same teachers as the excerpt and the excerpt kind ignores consent; e.g. "Reading"
            else:
                excerpt["exclude"] = True
                excludeAlert(excerpt,"due to teachers",annotation["teachers"],"of",annotation)
                return
        
        teacherList = [teacher for teacher in annotation["teachers"] if TeacherConsent(database["teacher"],[teacher],"attribute") or database["kind"][annotation["kind"]]["ignoreConsent"]]
        for teacher in set(annotation["teachers"]) - set(teacherList):
            gUnattributedTeachers[teacher] += 1

        # If the annotation is a reading and the teacher is not specified, make the author the teacher.
        if annotation["kind"] == "Reading" and not annotation["teachers"]:
            AppendUnique(teacherList,ReferenceAuthors(annotation["text"]))

        annotation["teachers"] = teacherList
    else:
        keysToRemove.append("teachers")
    
    if kind["takesTags"]:
        annotation["tags"] = annotation["qTag"] + annotation["aTag"] # Annotations don't distiguish between q and a tags
    
    if kind["canBeExcerpt"] or not kind["takesTimes"]:
        keysToRemove += ["startTime","endTime"]
    
    for key in keysToRemove:
        annotation.pop(key,None)    # Remove keys that aren't relevant for annotations
    
    annotation["indentLevel"] = len(annotation["flags"].split(ExcerptFlag.INDENT))
    if len(excerpt["annotations"]):
        prevAnnotationLevel = excerpt["annotations"][-1]["indentLevel"]
    else:
        prevAnnotationLevel = 0
    if annotation["indentLevel"] - 1 > prevAnnotationLevel:
        Alert.warning("Annotation",annotation,"to",excerpt,": Cannot increase indentation level by more than one.")
    
    excerpt["annotations"].append(annotation)

gAuthorRegexList = None
def ReferenceAuthors(textToScan: str) -> list[str]:
    global gAuthorRegexList
    if not gAuthorRegexList:
        gAuthorRegexList = Render.ReferenceMatchRegExs(gDatabase["reference"])
    authors = []
    for regex in gAuthorRegexList:
        matches = re.findall(regex,textToScan,flags = re.IGNORECASE)
        for match in matches:
            AppendUnique(authors,gDatabase["reference"][match[0].lower()]["author"])

    return authors

def FilterAndExplain(items: list,filter: Callable[[Any],bool],printer: Alert.AlertClass,message: str) -> list:
    """Return [i for in items if filter(i)].
    Print a message for each excluded item using printer and message."""
    filteredItems = []
    excludedItems = []
    for i in items:
        if filter(i):
            filteredItems.append(i)
        else:
            excludedItems.append(i)

    for i in excludedItems:
        printer(i,message)
    return filteredItems

def NumberExcerpts(excerpts: dict[str]) -> None:
    "Add excerptNumber to these excerpts"
    xNumber = 1
    lastSession = -1
    for x in excerpts:
        if x["sessionNumber"] != lastSession:
            if "clips" in x: # Does the session begin with a regular (non-session) excerpt?
                xNumber = 1
            else:
                xNumber = 0
            lastSession = x["sessionNumber"]
        else:
            if ExcerptFlag.FRAGMENT in x["flags"]:
                xNumber = round(xNumber + 0.1,1)  # Fragments have fractional excerpt numbers
            else:
                xNumber = int(xNumber) + 1
        
        x["excerptNumber"] = xNumber

def CreateClips(excerpts: list[dict], sessions: list[dict], database: dict) -> None:
    """For excerpts in a given event, convert startTime and endTime keys into the clips key.
    Add audio sources from sessions (and eventually audio annotations) to database["audioSource"]
    Process Alternate audio, Edited audio, Append audio, and Cut audio annotations."""
    
    def AddAudioSource(filename:str, duration:str, event: str, url: str) -> None:
        """Add an audio source to database["audioSource"]."""
        noDiacritics = Utils.RemoveDiacritics(filename)
        if filename != noDiacritics:
            Alert.error("Audio filename",repr(filename),"contains diacritics, which are not allowed.")
            filename = noDiacritics

        try:
            ToTimeDelta(duration)
        except ValueError:
            Alert.error(filename,"in event",event,"has invalid duration:",repr(duration))

        source = {"filename": filename, "duration":duration, "event":event, "url":url}
        
        # Check if duration and url match with an existing audio source; prefer the old values if they conflict
        existingSource = database["audioSource"].get(filename,None) or source
        for key in source:
            if key != "event" and existingSource[key] and source[key] and existingSource[key] != source[key]:
                Alert.warning(f"Audio file {filename} in event {event}: {key} ({source[key]}) does not match url given previously ({existingSource[key]}). Will use the old value.")
            source[key] = existingSource[key] or source[key]

        database["audioSource"][filename] = source

    def ExcerptDuration(excerpt: dict,sessionDuration:timedelta) -> str:
        "Return the duration of excerpt as a string."
        try:
            duration = timedelta(0)
            for clip in excerpt["clips"]:
                if clip.file == "$":
                    fileDuration = sessionDuration
                else:
                    fileDuration = database["audioSource"][clip.file]["duration"]
                duration += clip.Duration(fileDuration)
        except Mp3DirectCut.TimeError as error:
            Alert.error(excerpt,"generates time error:",error.args[0])
            return "0:00"
        return TimeDeltaToStr(duration)

    def SplitAudioSourceText(text: str) -> tuple[str,str,str]:
        """Split an audio annotation of the form duration|filename|url into the tuple filename,url,duration.
        url and duration are optional; empty strings are returned if they are omitted."""
        duration = url = ""
        splitBits = text.split("|")
        if len(splitBits) >= 3:
            duration,filename,url = splitBits[0:3]
        elif len(splitBits) == 2:
            filename,url = splitBits
        else:
            filename = splitBits[0]
        return filename,url,duration

    def ProcessAltAudio(excerpt: dict,altAudioAnnotation: dict) -> None:
        """Prepare for an excerpt that specifies an alternate audio source."""
        filename,url,duration = SplitAudioSourceText(altAudioAnnotation["text"])
        duration = altAudioAnnotation["endTime"] or duration # Duration usually comes from endTime
        if altAudioAnnotation["kind"] == "Edited audio":
            clip = excerpt["clips"][0]
            if not duration and clip.end:
                duration = TimeDeltaToStr(clip.Duration(fileDuration=None))
            excerpt["startTimeInSession"] = clip.start
            excerpt["clips"][0] = clip._replace(start="0:00",end="")
            excerpt["duration"] = duration
        AddAudioSource(filename,duration,excerpt["event"],url)

    def ProcessAppendAudio(excerpt: dict[str],appendAudioAnnotations: list[dict[str]]):
        """Add clips to an excerpt that contains Append audio or Cut audio annotations."""
        audioStart = Mp3DirectCut.ToTimeDelta(excerpt["clips"][0].start)
        for annotation in appendAudioAnnotations:
            if annotation["kind"] == "Append audio":
                filename,url,duration = SplitAudioSourceText(annotation["text"])
                if filename:
                    if filename != "$":
                        AddAudioSource(filename,duration,excerpt["event"],url)
                else:
                    filename = excerpt["clips"][-1].file
                
                excerpt["clips"].append(SplitMp3.Clip(filename,annotation["startTime"],annotation["endTime"]))
                audioStart = Mp3DirectCut.ToTimeDelta(annotation["startTime"])
            elif annotation["kind"] == "Cut audio":
                try:
                    cut = [annotation["startTime"],annotation["endTime"]]
                    if ExcerptFlag.RELATIVE_AUDIO in annotation["flags"]:
                        cut = [Mp3DirectCut.TimeDeltaToStr(audioStart + Mp3DirectCut.ToTimeDelta(time),decimal=True) for time in cut]
                    excerpt["clips"][-1:] = excerpt["clips"][-1].Cut(*cut)
                except (Mp3DirectCut.ParseError,Mp3DirectCut.TimeError) as error:
                    Alert.error(annotation,"to",excerpt,"produces error:",error.args[0])

    def CalcEditedAudioDuration(excerpt:dict[str],nextExcerptStartTime:str) -> None:
        """If the duration of the Edited audio annotation to this excerpt is not already specified, 
        set it to the time between the beginning of this excerpt and the start of the next one."""
        editedAudiAnnotation = [a for a in excerpt["annotations"] if a["kind"] == "Edited audio"][0]
        filename,url,duration = SplitAudioSourceText(editedAudiAnnotation["text"])
        if not database["audioSource"][filename]["duration"]:
            originalExcerptDuration = Mp3DirectCut.ToTimeDelta(nextExcerptStartTime) - Mp3DirectCut.ToTimeDelta(excerpt["startTimeInSession"])
            originalExcerptDuration = timedelta(seconds=round(originalExcerptDuration.total_seconds()))
            database["audioSource"][filename]["duration"] = Mp3DirectCut.TimeDeltaToStr(originalExcerptDuration)


    # First eliminate excerpts with fatal parsing errors.
    deletedExcerptIDs = set() # Ids of excerpts with fatal parsing errors
    for x in excerpts:
        try:
            if x["startTime"] != "Session":
                startTime = ToTimeDelta(x["startTime"])
                if startTime is None:
                    deletedExcerptIDs.add(id(x))
            endTime = ToTimeDelta(x["endTime"])
        except Mp3DirectCut.ParseError:
            deletedExcerptIDs.add(id(x))

    for index in reversed(range(len(excerpts))):
        if id(excerpts[index]) in deletedExcerptIDs:
            Alert.error("Misformed time string in",excerpts[index],". Will delete this excerpt.")
            del excerpts[index]

    # Then scan through the excerpts and add key "clips"
    for session,sessionExcerpts in Database.GroupBySession(excerpts,sessions):
        if session["filename"]:
            AddAudioSource(session["filename"],session["duration"],session["event"],session["remoteMp3Url"])
            try:
                sessionDuration = ToTimeDelta(session["duration"])
            except ValueError:
                sessionDuration = None
        else:
            sessionDuration = None
        del session["remoteMp3Url"]

        for x in sessionExcerpts:
            # First check if there is an Alternate audio or Edited audio annotation
            altAudioList = [a for a in x["annotations"] if a["kind"] in ("Alternate audio","Edited audio")]
            if altAudioList:
                if len(altAudioList) > 1:
                    Alert.caution(x,"has more than one Alternate audio or Edited audio annotation. Only the first will be used.")
                audioSource = SplitAudioSourceText(altAudioList[0]["text"])[0]
                    # The annotation text contains the audio source file name
            else:
                audioSource = "$"

            startTime = x["startTime"]
            endTime = x["endTime"]
            if startTime == "Session":
                    # The session excerpt has the length of the session and has no clips key
                session = Database.FindSession(sessions,x["event"],x["sessionNumber"])
                x["duration"] = session["duration"]
                if not x["duration"]:
                    Alert.error("Deleting session excerpt",x,"since the session has no duration.")
                    deletedExcerptIDs.add(id(x))
                continue
            
            
            x["clips"] = [SplitMp3.Clip(audioSource,startTime,endTime)]
            if altAudioList:
                ProcessAltAudio(x,altAudioList[0])
            
            appendAudioList = [a for a in x["annotations"] if a["kind"] in ("Append audio","Cut audio")]
            if appendAudioList:
                ProcessAppendAudio(x,appendAudioList)

        # Calculate the duration of each excerpt and handle overlapping excerpts
        # Excerpts without an end time end when the next non-fragment excerpt starts
        for xf1,xf2 in itertools.pairwise(Database.GroupFragments(sessionExcerpts)):
            if "clips" not in xf1[0]: # Skip the session excerpt
                continue
            
            nextExcerpt = xf2[0]
            if "startTimeInSession" in nextExcerpt:
                nextClip = Mp3DirectCut.Clip("$",nextExcerpt["startTimeInSession"])
            else:
                nextClip = nextExcerpt["clips"][0]
            for x in xf1:
                lastClip = x["clips"][-1]
                sameFile = lastClip.file == nextClip.file
                if not lastClip.end:
                    if sameFile:
                        x["clips"][-1] = lastClip._replace(end=nextClip.start)
                    
                    if "startTimeInSession" in x:
                        CalcEditedAudioDuration(x,nextClip.start)

                endTime = lastClip.ToClipTD().end
                if sameFile and endTime and endTime > nextClip.ToClipTD().start:
                    if ExcerptFlag.OVERLAP not in nextExcerpt["flags"]:
                        Alert.warning(nextExcerpt,"unexpectedly overlaps with the previous excerpt. This should be either changed or flagged with 'o'.")
        
        # If a session ends with an Edited audio excerpt, calculate its duration.
        if "startTimeInSession" in sessionExcerpts[-1]:
            CalcEditedAudioDuration(sessionExcerpts[-1],session["duration"])

        for x in sessionExcerpts:
            if "clips" in x:
                x["duration"] = ExcerptDuration(x,sessionDuration)
    
    for session in sessions:
        # Add information about session audio files that are not used directly
        # The presence of remoteMp3Url key means we haven't processed this session yet
        if "remoteMp3Url" in session and session["filename"] in database["audioSource"]:
            AddAudioSource(session["filename"],session["duration"],session["event"],session["remoteMp3Url"])
            del session["remoteMp3Url"]


def ProcessFragments(excerpt: dict[str]) -> list[dict[str]]:
    """Process the fragments in excerpt and return a list to add to the event."""
    # fragmentNumbers = [n for n,a in enumerate(excerpt["annotations"]) if a["Kind"] == "Fragment"]
    
    fragmentExcerpts = []
    nextFileNumber = excerpt["fileNumber"] + 1
    baseAnnotations = excerpt["annotations"]
    for n,fragmentAnnotation in enumerate(baseAnnotations):
        if fragmentAnnotation["kind"] not in ("Fragment","Main fragment"):
            continue
        mainFragment = fragmentAnnotation["kind"] == "Main fragment"

        if not ExcerptFlag.MANUAL_FRAGMENTS in excerpt["flags"]:
            if mainFragment:
                fragmentExcerptTemplate = excerpt
                fragmentAnnotations = [copy.copy(baseAnnotations[number]) for number in range(n)]
                    # Copy all annotations previous to the Main fragment annotation
                fragmentFTagSource = fragmentTagSource = fragmentAnnotation
                if not fragmentTagSource["qTag"] and not fragmentTagSource["aTag"]:
                    fragmentTagSource = excerpt
            else:
                if n + 1 >= len(baseAnnotations) or baseAnnotations[n]["indentLevel"] != baseAnnotations[n + 1]["indentLevel"]:
                    Alert.error("Error processing Fragment annotation #",n,"in",excerpt,": an annotation at the same level must follow a Fragment annotation.")
                    return fragmentExcerpts
                
                baseLevel = fragmentAnnotation["indentLevel"]
                fragmentExcerptTemplate = fragmentFTagSource = fragmentTagSource = baseAnnotations[n + 1]

                fragmentAnnotations = [copy.copy(a) for a in Database.SubAnnotations(excerpt,baseAnnotations[n + 1])]
                for a in fragmentAnnotations:
                    a["indentLevel"] = a["indentLevel"] - baseLevel

            fragmentExcerpt = dict(
                event = excerpt["event"],
                sessionNumber = excerpt["sessionNumber"],
                fileNumber = nextFileNumber,
                annotations = fragmentAnnotations,

                kind = fragmentExcerptTemplate["kind"],
                flags = fragmentExcerptTemplate["flags"] + ExcerptFlag.FRAGMENT,
                teachers = fragmentExcerptTemplate["teachers"],
                text = fragmentExcerptTemplate["text"],

                qTag = fragmentTagSource["qTag"],
                aTag = fragmentTagSource["aTag"],
                fTags = fragmentFTagSource["fTags"],
                fTagOrder = fragmentFTagSource["fTagOrder"],
                fTagOrderFlags = fragmentFTagSource["fTagOrderFlags"],

                startTime = fragmentAnnotation["startTime"],
                endTime = fragmentAnnotation["endTime"],

                exclude = False
            )

            audioEdited = any(a["kind"] == "Edited audio" for a in excerpt["annotations"])
            relativeAudio = ExcerptFlag.RELATIVE_AUDIO in fragmentAnnotation["flags"]
            if audioEdited and not relativeAudio:
                Alert.error(excerpt,": Excerpts with edited audio must specify relative fragment times.")
            elif relativeAudio:
                offsetTime = ToTimeDelta(excerpt["startTime"])
                fragmentExcerpt["startTime"] = TimeDeltaToStr(ToTimeDelta(fragmentExcerpt["startTime"]) + offsetTime,decimal=True)
                if fragmentExcerpt["endTime"]:
                    fragmentExcerpt["endTime"] = TimeDeltaToStr(ToTimeDelta(fragmentExcerpt["endTime"]) + offsetTime,decimal=True)
                elif excerpt["endTime"]:
                    fragmentExcerpt["endTime"] = excerpt["endTime"]
            
            fragmentExcerpts.append(fragmentExcerpt)

        if fragmentAnnotation["text"].lower() == "noplayer":
            fragmentAnnotation["text"] = ""
        elif not mainFragment: # Main fragments don't display a player
            fragmentAnnotation["text"] = f"[](player:{Database.ItemCode(event=excerpt['event'],session=excerpt['sessionNumber'],fileNumber=nextFileNumber)})"
        nextFileNumber += 1
    
    return fragmentExcerpts


gUnattributedTeachers = Counter()
"Counts the number of times we hide a teacher's name when their attribute permission is false."

def LoadEventFile(database,eventName,directory):
    
    with open(os.path.join(directory,eventName + '.csv'),encoding='utf8') as file:
        SkipModificationLine(file)
        rawEventDesc = CSVToDictList(file,endOfSection = '<---->')
        sessions = CSVToDictList(file,removeKeys = ["seconds"],endOfSection = '<---->')
        try: # First look for a separate excerpt sheet ending in x.csv
            with open(os.path.join(directory,eventName + 'x.csv'),encoding='utf8') as excerptFile:
                SkipModificationLine(excerptFile)
                rawExcerpts = CSVToDictList(excerptFile,endOfSection = '<---->')
        except FileNotFoundError:
            rawExcerpts = CSVToDictList(file,endOfSection = '<---->')

    def RemoveUnknownTeachers(teacherList: list[str],item: dict) -> None:
        """Remove teachers that aren't present in the teacher database.
        Report an error mentioning item if this is the case."""

        unknownTeachers = [t for t in teacherList if t not in database["teacher"]]
        if unknownTeachers:
            Alert.warning("Teacher(s)",repr(unknownTeachers),"in",item,"do not appear in the Teacher sheet.")
            for t in unknownTeachers:
                teacherList.remove(t)

    eventDesc = DictFromPairs(rawEventDesc,"key","value")
    eventDesc["code"] = eventName

    for key in ["teachers","tags"]:
        eventDesc[key] = [s.strip() for s in eventDesc[key].split(';') if s.strip()]
    for key in ["sessions","excerpts","answersListenedTo","tagsApplied","invalidTags","duration"]:
        eventDesc.pop(key,None) # The spreadsheet often miscounts these items, so remove them.

    RemoveUnknownTeachers(eventDesc["teachers"],eventDesc)
    
    
    for key in ["tags","teachers"]:
        ListifyKey(sessions,key)
    ConvertToInteger(sessions,"sessionNumber")
    
    for s in sessions:
        s["event"] = eventName
        s.pop("excerpts",None)
        Utils.ReorderKeys(s,["event","sessionNumber"])
        RemoveUnknownTeachers(s["teachers"],s)
        s["teachers"] = [teacher for teacher in s["teachers"] if TeacherConsent(database["teacher"],[teacher],"attribute")]

    if not gOptions.ignoreExcludes:
        sessions = FilterAndExplain(sessions,lambda s: not s["exclude"],excludeAlert,"- exclude flag Yes.")
        # Remove excluded sessions
        
    for s in sessions:
        if not gOptions.jsonNoClean:
            del s["exclude"]
    
    sessions = FilterAndExplain(sessions,lambda s: TeacherConsent(database["teacher"],s["teachers"],"indexSessions",singleConsentOK=True),excludeAlert,"due to teacher consent.")
        # Remove sessions if none of the session teachers have given consent
    database["sessions"] += sessions

    # Convert ? characters to numbers indicating draft fTags
    for x in rawExcerpts:
        x["fTagOrder"] = re.sub(r"\?+",lambda m: str(len(m[0]) + 1000),x["fTagOrder"])
    for key in ["teachers","qTag1","aTag1","fTags","fTagOrder"]:
        ListifyKey(rawExcerpts,key)
    for x in rawExcerpts:
        # Handle fTag order flags
        flags = [re.search(r"[a-zA-Z]$",s) for s in x["fTagOrder"]]
        flags = [f[0] if f else FTagOrderFlag.EVERYWHERE for f in flags]
        for n,f in enumerate(flags):
            try:
                FTagOrderFlag(f.upper()) # This conversion fails if we don't recognize the flag
            except ValueError:
                Alert.warning("Ignoring unknown fTag order flag",repr(f),"in",x)
                flags[n] = FTagOrderFlag.EVERYWHERE
        x["fTagOrderFlags"] = "".join(flags)

        x["fTagOrder"]= [re.sub(r"[a-zA-Z]","",s) for s in x["fTagOrder"]]
    ConvertToInteger(rawExcerpts,"sessionNumber")
    ConvertToInteger(rawExcerpts,"fTagOrder")
    
    includedSessions = set(s["sessionNumber"] for s in sessions)
    rawExcerpts = [x for x in rawExcerpts if x["sessionNumber"] in includedSessions]
        # Remove excerpts and annotations in sessions we didn't get consent for
        
    fileNumber = 1
    lastSession = -1
    prevExcerpt = None
    excerpts = []
    blankExcerpts = 0
    redactedTagSet = set(database["tagRedacted"])
    for x in rawExcerpts:
        if all(not value for key,value in x.items() if key != "sessionNumber"): # Skip lines which have a session number and nothing else
            blankExcerpts += 1
            continue

        x["flags"] = x.get("flags","")
        x["kind"] = x.get("kind","")

        x["qTag"] = [tag for tag in x["qTag"] if tag not in redactedTagSet] # Redact non-consenting teacher tags for both annotations and excerpts
        x["aTag"] = [tag for tag in x["aTag"] if tag not in redactedTagSet]
        x["fTags"] = [tag for tag in x["fTags"] if tag not in redactedTagSet]

        if not x["kind"]:
            x["kind"] = "Question"

        if not x["startTime"] or not database["kind"][x["kind"]]["canBeExcerpt"]:
                # If Start time is blank or it's an audio annotation, this is an annotation to the previous excerpt
            if prevExcerpt is not None:
                AddAnnotation(database,prevExcerpt,x)
            else:
                Alert.error(f"Error: The first item in {eventName} session {x['sessionNumber']} must specify at start time.")
            continue
        elif prevExcerpt: # Process the fragments of the previous excerpt once all annotations have been appended
            fragments = ProcessFragments(prevExcerpt)
            excerpts.extend(fragments)
            fileNumber += len(fragments)

        x["annotations"] = []    
        x["event"] = eventName
        
        ourSession = Database.FindSession(sessions,eventName,x["sessionNumber"])
        
        if not x.pop("offTopic",False): # We don't need the off topic key after this, so throw it away with pop
            Utils.ExtendUnique(x["qTag"],ourSession["tags"])

        RemoveUnknownTeachers(x["teachers"],x)

        if not x["teachers"]:
            defaultTeacher = database["kind"][x["kind"]]["inheritTeachersFrom"]
            if defaultTeacher == "Anon": # Check if the default teacher is anonymous
                x["teachers"] = ["Anon"]
            elif defaultTeacher != "None":
                x["teachers"] = list(ourSession["teachers"]) # Make a copy to prevent subtle errors
        
        # If the excerpt is a reading and the teacher is not specified, make the author the teacher.
        if x["kind"] == "Reading" and not x["teachers"]:
            AppendUnique(x["teachers"],ReferenceAuthors(x["text"]))
        
        if x["sessionNumber"] != lastSession:
            if lastSession > x["sessionNumber"]:
                Alert.error(f"Session number out of order after excerpt number {fileNumber} in session {lastSession} of",eventDesc," Will discard this excerpt.")
                continue
            lastSession = x["sessionNumber"]
            if x["startTime"] == "Session":
                fileNumber = 0
            else:
                fileNumber = 1
        else:
            fileNumber += 1 # File number counts all excerpts listed for the event
            if x["startTime"] == "Session":
                Alert.warning("Session excerpt",x,"must occur as the first excerpt in the session. Excluding this excerpt.")
                x["exclude"] = True
        x["fileNumber"] = fileNumber

        excludeReason = []
        if x["exclude"] and not gOptions.ignoreExcludes:
            excludeReason = [x," - marked for exclusion in spreadsheet"]
        elif database["kind"][x["kind"]].get("exclude",False):
            excludeReason = [x,"is of kind",x["kind"],"which is excluded in the spreadsheet"]
        elif not (TeacherConsent(database["teacher"],x["teachers"],"indexExcerpts") or database["kind"][x["kind"]]["ignoreConsent"]):
            x["exclude"] = True
            excludeReason = [x,"due to excerpt teachers",x["teachers"]]

        CheckItemContents(x,None,database["kind"][x["kind"]])

        if excludeReason:
            excludeAlert(*excludeReason)

        attributedTeachers = [teacher for teacher in x["teachers"] if TeacherConsent(database["teacher"],[teacher],"attribute") or database["kind"][x["kind"]]["ignoreConsent"]]
        for teacher in set(x["teachers"]) - set(attributedTeachers):
            if not x["exclude"]:
                gUnattributedTeachers[teacher] += 1
        x["teachers"] = attributedTeachers
        
        excerpts.append(x)
        prevExcerpt = x

    fragments = ProcessFragments(prevExcerpt) # Process the fragments of the last excerpt
    excerpts.extend(fragments)

    if blankExcerpts:
        Alert.notice(blankExcerpts,"blank excerpts in",eventDesc)

    for x in excerpts:
        FinalizeExcerptTags(x)

    # Apply temporary excerpt numbers before calling CreateClips
    NumberExcerpts(excerpts)
    CreateClips(excerpts,sessions,database)
    
    originalCount = len(excerpts)
    excerpts = [x for x in excerpts if not x["exclude"]]
        # Remove excluded excerpts, those we didn't get consent for, and excerpts which are too corrupted to interpret
    global gRemovedExcerpts
    gRemovedExcerpts += originalCount - len(excerpts)
    sessionsWithExcerpts = set(x["sessionNumber"] for x in excerpts)
    for unusedSession in includedSessions - sessionsWithExcerpts:
        del gDatabase["sessions"][Utils.SessionIndex(gDatabase["sessions"],eventName,unusedSession)]
        # Remove sessions with no excerpts

    # Renumber the excerpts after removing excluded excerpts
    NumberExcerpts(excerpts)

    if sessionsWithExcerpts:
        database["event"][eventName] = eventDesc
    else:
        Alert.caution(eventDesc,"has no non-excluded session. Removing this event from the database.")
        return

    
    for index in range(len(excerpts)):
        Utils.ReorderKeys(excerpts[index],["event","sessionNumber","excerptNumber","fileNumber"])
    
    if not gOptions.jsonNoClean:
        for x in excerpts:
            del x["exclude"]
            del x["startTime"]
            del x["endTime"]

    database["excerpts"] += excerpts

    eventDesc["sessions"] = len(sessions)
    eventDesc["excerpts"] = Database.CountExcerpts(excerpts) # Count only non-session excerpts   

def CountInstances(source: dict|list,sourceKey: str,countDicts: List[dict],countKey: str,zeroCount = False) -> int:
    """Loop through items in a collection of dicts and count the number of appearances a given str.
        source: A dict of dicts or a list of dicts containing the items to count.
        sourceKey: The key whose values we should count.
        countDicts: A dict of dicts that we use to count the items. Each item should be a key in this dict.
        countKey: The key we add to countDicts[item] with the running tally of each item.
        zeroCount: add countKey even when there are no items counted?
        return the total number of items counted"""
        
    if zeroCount:
        for key in countDicts:
            if countKey not in countDicts[key]:
                countDicts[key][countKey] = 0

    totalCount = 0
    excerptsCounted = 0
    for d in Utils.Contents(source):
        excerptsCounted += 1
        valuesToCount = d[sourceKey]
        if type(valuesToCount) != list:
            valuesToCount = [valuesToCount]
        
        removeItems = []
        for item in valuesToCount:
            try:
                countDicts[item][countKey] = countDicts[item].get(countKey,0) + 1
                totalCount += 1
            except KeyError:
                Alert.warning(f"CountInstances: Can't match key {item} from {d} in list of {sourceKey}. Will remove {item}.")
                removeItems.append(item)

        if type(d[sourceKey]) == list:
            for item in removeItems:
                valuesToCount.remove(item)
    
    return excerptsCounted

def CountAndVerify(database):
    
    tagDB = database["tag"]
    tagCount = CountInstances(database["event"],"tags",tagDB,"eventCount")
    tagCount += CountInstances(database["sessions"],"tags",tagDB,"sessionCount")

    fTagCount = draftFTagCount = 0
    # Don't count tags on fragments which are duplicated in their source excerpt
    for excerptWithFragments in Database.GroupFragments(database["excerpts"]):
        tagSet = set()
        for x in excerptWithFragments:
            tagSet.update(Filter.AllTags(x))

        tagsToRemove = []
        topics = set()
        subtopics = set()
        for tag in tagSet:
            try:
                tagDB[tag]["excerptCount"] = tagDB[tag].get("excerptCount",0) + 1
                tagCount += 1
            except KeyError:
                Alert.warning(f"CountAndVerify: Tag",repr(tag),"is not defined. Will remove this tag.")
                tagsToRemove.append(tag)
            else:
                for subtopic in tagDB[tag].get("partOfSubtopics",()):
                    subtopics.add(subtopic)
                    topics.add(database["subtopic"][subtopic]["topicCode"])
        
        for topic in topics:
            database["keyTopic"][topic]["excerptCount"] = database["keyTopic"][topic].get("excerptCount",0) + 1
        for subtopic in subtopics:
            database["subtopic"][subtopic]["excerptCount"] = database["subtopic"][subtopic].get("excerptCount",0) + 1   
        
        if tagsToRemove:
            for item in Filter.AllItems(x):
                if "tags" in item:
                    item["tags"] = [t for t in item["tags"] if t not in tagsToRemove]
        
        for x in excerptWithFragments:
            tagSet = Filter.AllTags(x)

            for index in reversed(range(len(x["fTags"]))):
                fTag = x["fTags"][index]
                fTagOrder = x["fTagOrder"][index]
                if fTag not in tagSet:
                    Alert.caution(x,"specifies fTag",fTag,"but this does not appear as a regular tag.")

                if gOptions.draftFTags == "omit" and fTagOrder > 1000:
                    del x["fTagOrder"][index]
                    del x["fTags"][index]
                    draftFTagCount += 1
                else:
                    tagDB[fTag]["fTagCount"] = tagDB[fTag].get("fTagCount",0) + 1
                    if fTagOrder > 1000:
                        draftFTagCount += 1
                    else:
                        fTagCount += 1
            
        # The source excerpt should display stars for its fragements' fTags, so set the fragmentFTags key
        for fragment in excerptWithFragments[1:]:
            for fTag,fTagOrder in zip(fragment["fTags"],fragment.get("fTagOrder",())):
                excerptWithFragments[0]["fragmentFTags"] = excerptWithFragments[0].get("fragmentFTags",[]) + [fTag]

    Alert.info(tagCount,"total tags applied.",
               fTagCount,"featured tags applied.",draftFTagCount,f"draft featured tags{' have been omitted' if gOptions.draftFTags == 'omit' else ''}.")
    
    CountInstances(database["event"],"teachers",database["teacher"],"eventCount")
    CountInstances(database["sessions"],"teachers",database["teacher"],"sessionCount")

    for teacher in database["teacher"].values():
        teacher["excerptCount"] = len(list(Filter.Teacher(teacher["teacher"])(Database.RemoveFragments(database["excerpts"]))))
        # Count indirect quotes from teachers as well as attributed teachers
    
    for topic in database["keyTopic"].values():
        topicExcerpts = set()
        for cluster in topic["subtopics"]:
            tagExcerpts = set(id(x) for x in Filter.ClusterFTag(cluster)(database["excerpts"]))
            database["subtopic"][cluster]["fTagCount"] = len(tagExcerpts)
            topicExcerpts.update(tagExcerpts)
        
        topic["fTagCount"] = len(topicExcerpts)

    if gOptions.detailedCount:
        for key in ["venue","series","format","medium"]:
            CountInstances(database["event"],key,database[key],"eventCount")
    
    # Are tags flagged Primary as needed?
    for cluster in database["tag"]:
        tagDesc = database["tag"][cluster]
        if tagDesc["primaries"] > 1:
            Alert.caution(f"{tagDesc['primaries']} instances of tag {tagDesc['tag']} are flagged as primary.")
        if tagDesc["copies"] > 1 and tagDesc["primaries"] == 0 and TagFlag.VIRTUAL not in tagDesc["flags"]:
            Alert.notice(f"Notice: None of {tagDesc['copies']} instances of tag {tagDesc['tag']} are designated as primary.")


def AddArguments(parser):
    "Add command-line arguments used by this module"
    
    parser.add_argument('--ignoreTeacherConsent',**Utils.STORE_TRUE,help="Ignore teacher consent flags - debugging only")
    parser.add_argument('--pendingMeansYes',**Utils.STORE_TRUE,help="Treat teacher consent pending as yes - debugging only")
    parser.add_argument('--ignoreExcludes',**Utils.STORE_TRUE,help="Ignore exclude session and excerpt flags - debugging only")
    parser.add_argument('--parseOnlySpecifiedEvents',**Utils.STORE_TRUE,help="Load only events specified by --events into the database")
    parser.add_argument('--includeTestEvent',**Utils.STORE_TRUE,help="Include event Test1999 in the database.")
    parser.add_argument('--draftFTags',type=str,default="omit",help='What to do with fTags marked "?" "omit", "mark", "number", or "show"')
    parser.add_argument('--detailedCount',**Utils.STORE_TRUE,help="Count all possible items; otherwise just count tags")
    parser.add_argument('--keepUnusedTags',**Utils.STORE_TRUE,help="Don't remove unused tags")
    parser.add_argument('--jsonNoClean',**Utils.STORE_TRUE,help="Keep intermediate data in json file for debugging")
    parser.add_argument('--explainExcludes',**Utils.STORE_TRUE,help="Print a message for each excluded/redacted excerpt")

def ParseArguments() -> None:
    gOptions.draftFTags = gOptions.draftFTags.lower()
    if gOptions.draftFTags not in ("omit","mark","number","show"):
        Alert.caution("Cannot recognize --draftFTags",repr(gOptions.draftFTags),"; reverting to omit.")
        gOptions.draftFTags = "omit"

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy
gRemovedExcerpts = 0 # Count the total number of removed excerpts
gRemovedAnnotations = 0

# AlertClass for explanations of excluded excerpts. Don't show by default.
excludeAlert = Alert.AlertClass("Exclude","Exclude",printAtVerbosity=999,logging = False,lineSpacing = 1)

def main():
    """ Parse a directory full of csv files into the dictionary database and write it to a .json file.
    Each .csv sheet gets one entry in the database.
    Tags.csv and event files indicated by four digits e.g. TG2015.csv are parsed separately."""

    global gDatabase
    LoadSummary(gDatabase,os.path.join(gOptions.csvDir,"Summary.csv"))
   
    specialFiles = {'Summary','Tag','EventTemplate'}
    for fileName in os.listdir(gOptions.csvDir):
        fullPath = os.path.join(gOptions.csvDir,fileName)
        if not os.path.isfile(fullPath):
            continue
        
        baseName,extension = os.path.splitext(fileName)
        if extension.lower() != '.csv':
            continue
        
        if baseName in specialFiles or baseName[0] == '_':
            continue
        
        if re.match(".*[0-9]{4}",baseName): # Event files contain a four-digit year and are loaded after all other files
            continue
        
        def PendingBoolean(s:str):
            return s.startswith("Yes") or s.startswith("Pending")

        extraArgs = {}
        if baseName == "Teacher" and gOptions.pendingMeansYes:
            extraArgs["convertBools"] = PendingBoolean

        gDatabase[CamelCase(baseName)] = ListToDict(CSVFileToDictList(fullPath,**extraArgs))
    
    LoadTagsFile(gDatabase,os.path.join(gOptions.csvDir,"Tag.csv"))
    PrepareReferences(gDatabase["reference"])

    if gOptions.explainExcludes:
        excludeAlert.printAtVerbosity = -999

    if gOptions.events != "All":
        unknownEvents = set(gOptions.events) - set(gDatabase["summary"])
        if unknownEvents:
            Alert.warning("Events",unknownEvents,"are not listed in the Summary sheet and will not be parsed.")

    gDatabase["event"] = {}
    gDatabase["sessions"] = []
    gDatabase["audioSource"] = {}
    gDatabase["excerpts"] = []
    for event in gDatabase["summary"]:
        if not gOptions.parseOnlySpecifiedEvents or gOptions.events == "All" or event in gOptions.events:
            if not event.startswith("Test") or gOptions.includeTestEvent:
                LoadEventFile(gDatabase,event,gOptions.csvDir)
    ListifyKey(gDatabase["event"],"series")
    excludeAlert(f": {gRemovedExcerpts} excerpts and {gRemovedAnnotations} annotations in all.")
    gUnattributedTeachers.pop("Anon",None)
    if gUnattributedTeachers:
        excludeAlert(f": Did not attribute excerpts to the following teachers:",dict(gUnattributedTeachers))
    if gDatabase["tagRedacted"]:
        excludeAlert(f": Redacted these tags due to teacher consent:",gDatabase["tagRedacted"])

    if not len(gDatabase["event"]):
        Alert.error("No excerpts have been parsed. Aborting.")
        sys.exit(1)

    CollectKeyTopics(gDatabase)
    CountAndVerify(gDatabase)
    if not gOptions.keepUnusedTags:
        RemoveUnusedTags(gDatabase)
    else:
        gDatabase["tagRemoved"] = []

    PrepareTeachers(gDatabase["teacher"])

    CreateTagDisplayList(gDatabase)
    SortTags(gDatabase)
    IndexTags(gDatabase)  
    CountSubtagExcerpts(gDatabase)

    gDatabase["keyCaseTranslation"] = {key:gCamelCaseTranslation[key] for key in sorted(gCamelCaseTranslation)}

    Utils.ReorderKeys(gDatabase,["excerpts","event","sessions","audioSource","kind","category","teacher","tag","series","venue","format","medium","reference","tagDisplayList"])

    Alert.extra("Spreadsheet database contents:",indent = 0)
    Utils.SummarizeDict(gDatabase,Alert.extra)

    with open(gOptions.spreadsheetDatabase, 'w', encoding='utf-8') as file:
        json.dump(gDatabase, file, ensure_ascii=False, indent=2)

    Alert.info(Prototype.ExcerptDurationStr(gDatabase["excerpts"],countSessionExcerpts=True,sessionExcerptDuration=False),indent = 0)