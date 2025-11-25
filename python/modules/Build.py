"""Write html files to the pages directory"""

from __future__ import annotations

import os, time
from typing import List, Iterator, Iterable, Tuple, Callable
from airium import Airium
import Mp3DirectCut
import Database, ReviewDatabase
import Utils, Alert, Filter, ParseCSV, Document, Render, SetupFeatured, BuildReferences
import Html2 as Html
from datetime import timedelta
import re, copy, itertools
import pyratemp, markdown
from markdown_newtab_remote import NewTabRemoteExtension
from typing import NamedTuple, Generator
from collections import defaultdict, Counter
from enum import Enum
import itertools
import FileRegister
from contextlib import nullcontext
from functools import lru_cache
import urllib.parse

BASE_MENU_STYLE = dict(separator="\n"+6*" ",highlight={"class":"active"})
MAIN_MENU_STYLE = BASE_MENU_STYLE | dict(menuSection="mainMenu")
SUBMENU_STYLE = BASE_MENU_STYLE | dict(menuSection="subMenu")
LONG_SUBMENU_STYLE = BASE_MENU_STYLE | dict(menuSection="customSubMenu",
                           menuClass=Html.ResponsivePopupMenu,
                           responsiveContainer = "",
                           wrapper=Html.Tag("div",{"class":"sublink hide-thin-screen-3 noscript-show"}),
                           popupMenu_wrapper=Html.Tag("div",{"class":"sublink-popup hide-wide-screen-3 noscript-hide"}))
EXTRA_MENU_STYLE = BASE_MENU_STYLE | dict(menuClass=Html.ResponsivePopupMenu,
                                          wrapper=Html.Tag("div",{"class":"sublink2"}) + "\n<hr>\n",
                                          popupMenu_wrapper=Html.Tag("div",{"class":"sublink2-popup"}) + "\n<hr>\n")


FA_STAR = '<i class="fa fa-star"></i>'

def WriteIndentedTagDisplayList(fileName):
    with open(fileName,'w',encoding='utf-8') as file:
        for item in gDatabase["tagDisplayList"]:
            indent = "    " * (item["level"] - 1)
            indexStr = item["indexNumber"] + ". " if item["indexNumber"] else ""
            
            
            tagFromText = item['text'].split(' [')[0].split(' {')[0] # Extract the text before either ' [' or ' {'
            if tagFromText != item['tag']:
                reference = " -> " + item['tag']
            else:
                reference = ""
            
            print(''.join([indent,indexStr,item['text'],reference]),file = file)

def WritePage(page: Html.PageDesc,writer: FileRegister.HashWriter) -> None:
    """Write an html file for page using the global template"""
    page.gOptions = gOptions
    if page.HasSection("titleIcon"):
        page.section["titleIcon"] = HtmlIcon(page.section["titleIcon"]) + " "

    template = Utils.PosixJoin(gOptions.pagesDir,gOptions.globalTemplate)
    if page.info.file.endswith("_print.html"):
        template = Utils.AppendToFilename(template,"_print")
    pageHtml = page.RenderWithTemplate(template)
    writer.WriteTextFile(page.info.file,pageHtml)


def DirectoriesToDeleteFrom() -> set[str]:
    """Return the list of directories which will be scanned by DeleteUnwrittenHtmlFiles."""
    # Delete files only in directories we have built
    dirs = gOptions.buildOnly - {"allexcerpts"}
    if gOptions.buildOnly == gAllSections:
        dirs.add("indexes")
    return dirs

def DeleteUnwrittenHtmlFiles(writer: FileRegister.HashWriter) -> None:
    """Remove old html files from previous runs to keep things neat and tidy."""

    dirs = DirectoriesToDeleteFrom()

    deletedFiles = 0
    for dir in dirs:
        deletedFiles += writer.DeleteUnregisteredFiles(dir,filterRegex=r".*\.html$")
    if deletedFiles:
        Alert.extra(deletedFiles,"html file(s) deleted.")

def ItemList(items:List[str], joinStr:str = ", ", lastJoinStr:str = None, capitalize = False):
    """Format a list of items"""
    
    if lastJoinStr is None:
        lastJoinStr = joinStr
    
    if not items:
        return ""
    if len(items) == 1:
        return Utils.CapitalizeFirst(items[0]) if capitalize else items[0]
    
    firstItems = joinStr.join(items[:-1])
    returnValue = lastJoinStr.join([firstItems,items[-1]])
    if capitalize:
        returnValue = Utils.CapitalizeFirst(returnValue)
    return returnValue

def TitledList(title:str, items:List[str], plural:str = "s", joinStr:str = ", ",lastJoinStr:str = None,titleEnd:str = ": ",endStr:str = "<br>") -> str:
    """Format a list of items with a title as a single line in html code."""
    
    if not items:
        return ""
    if not title:
        titleEnd = ""
    if title and len(items) > 1:
        title += plural
    
    listStr = ItemList(items,joinStr,lastJoinStr)
    #listStr = joinStr.join(items)
    
    return title + titleEnd + listStr + endStr

def HtmlIcon(iconName:str,iconClass:str = "",directoryDepth:int = 1) -> str:
    "Return html code for an icon"
    if not iconName:
        return ""
    if "<" in iconName: # Return raw html unchanged
        return iconName
    elif iconName.lower().split(".")[-1] in ("png","svg","jpg","jpeg"):
        return f'''<img src="{'../'*directoryDepth}images/icons/{iconName}"{f' class="{iconClass}"' if iconClass else ""}>'''
    else:
        attributes = {"data-lucide":iconName}
        if iconClass:
            attributes["class"] = iconClass
        return Html.Tag("i",attributes)("")

def HtmlTagLink(tag:str, fullTag: bool = False,text:str = "",link = True,showStar = False) -> str:
    """Turn a tag name into a hyperlink to that tag.
    Simplying assumption: All html pages (except homepage.html and index.html) are in a subdirectory of pages.
    Thus ../tags will reference the tags directory from any other html pages.
    If fullTag, the link text contains the full tag name."""
    
    tagData = None
    try:
        tagData = gDatabase["tag"][tag]
    except KeyError:
        tagData = gDatabase["tag"][gDatabase["tagSubsumed"][tag]["subsumedUnder"]]
    
    ref = tagData["htmlFile"]
    if fullTag:
        tag = tagData["fullTag"]
    
    if not text:
        text = tag

    flag = f'&nbsp{FA_STAR}' if showStar and tagData and tagData.get("fTagCount",0) else ""

    if link:
        splitItalics = text.split("<i>")
        if len(splitItalics) > 1:
            textOutsideLink = " <i>" + splitItalics[1]
        else:
            textOutsideLink = ""
        return f'<a href = "../tags/{ref}">{splitItalics[0].strip() + flag}</a>{textOutsideLink}'
    else:
        return text + flag

def HtmlKeyTopicLink(headingCode:str,text:str = "",link=True,count = False) -> str:
    "Return a link to the specified key topic."

    if not text:
        text = gDatabase["keyTopic"][headingCode]["topic"]

    if link:
        returnValue = Html.Tag("a",{"href":Utils.PosixJoin("../topics",headingCode+".html")})(text)
    else:
        returnValue = text

    if count and gDatabase['keyTopic'][headingCode]['fTagCount']:
        returnValue += f" ({gDatabase['keyTopic'][headingCode]['fTagCount']})"
    return returnValue

    
def HtmlSubtopicLink(subtopic:str,text:str = "",link=True,count=False) -> str:
    "Return a link to the specified subtopic."

    isTag = subtopic not in gDatabase["subtopic"]
    if not text:
        text = subtopic if isTag else gDatabase["subtopic"][subtopic]["displayAs"]

    if link:
        if isTag:
            htmlPath = Utils.PosixJoin("../tags/",gDatabase["tag"][subtopic]["htmlFile"])
        else:
            htmlPath = Utils.PosixJoin("../",gDatabase["subtopic"][subtopic]["htmlPath"])
        returnValue = Html.Tag("a",{"href":htmlPath})(text)
    else:
        returnValue = text
    if count and gDatabase['subtopic'][subtopic]['fTagCount']:
        returnValue += f" ({gDatabase['subtopic'][subtopic]['fTagCount']})"
    return returnValue

def HtmlSubtopicTagList(subtopic:dict,summarize:int = 0,group:bool = False,showStar = False) -> str:
    """Return a list of tags in the given cluster.
    summarize: Don't list subtags if the total number of tags exceeds this value.
    group: Use the form: Tag1 (Subtag1, Subtag2), Tag2 (Subtag3)..."""

    subordinateTags = sum(1 for flag in subtopic["subtags"].values() if flag == ParseCSV.KeyTagFlag.SUBORDINATE_TAG)
    listSubtags = (summarize and len(subtopic["subtags"]) + 1 <= summarize) or subordinateTags < 2
    bits = []
    for tag,flag in itertools.chain([(subtopic["tag"],ParseCSV.KeyTagFlag.PEER_TAG)],subtopic["subtags"].items()):
        if listSubtags or flag == ParseCSV.KeyTagFlag.PEER_TAG:
            bits.append(HtmlTagLink(tag,showStar=showStar))
    
    if not listSubtags:
        bits.append(f"and {len(subtopic['subtags']) + 1 - len(bits)} subtags")

    return ", ".join(bits)

def SearchLink(query:str,searchType:str = "x") -> str:
    """Returns a link to the search page with a specifed search string."""

    htmlQuery = urllib.parse.urlencode({"q":query,"search":searchType},doseq=True,quote_via=urllib.parse.quote)
    return f"../search/Text-search.html?{htmlQuery}"

def ListLinkedTags(title:str, tags:Iterable[str],*args,**kwargs) -> str:
    "Write a list of hyperlinked tags"
    
    linkedTags = [HtmlTagLink(tag) for tag in tags]
    return TitledList(title,linkedTags,*args,**kwargs)

gAllTeacherRegex = ""
def LinkTeachersInText(text: str,specificTeachers:Iterable[str]|None = None) -> str:
    """Search text for the names of teachers with teacher pages and add hyperlinks accordingly."""

    global gAllTeacherRegex
    if not gAllTeacherRegex:
        teacherList = sorted((t["attributionName"] for t in gDatabase["teacher"].values() if t["htmlFile"]),key=lambda s: -len(s))
            # Put longest items first so that Ajahn Chah Sangha doesn't match Ajahn Chah
        gAllTeacherRegex = Utils.RegexMatchAny(teacherList)
    
    if specificTeachers is None:
        teacherRegex = gAllTeacherRegex
    else:
        teacherRegex = Utils.RegexMatchAny(gDatabase["teacher"][t]["attributionName"] for t in specificTeachers if gDatabase["teacher"][t]["htmlFile"])

    def HtmlTeacherLink(matchObject: re.Match) -> str:
        teacher = Database.TeacherLookup(matchObject[1])
        htmlFile = TeacherLink(teacher)
        return f'<a href="{htmlFile}">{matchObject[1]}</a>'

    return re.sub(teacherRegex,HtmlTeacherLink,text,flags=re.RegexFlag.IGNORECASE)


def ListLinkedTeachers(teachers:List[str],*args,**kwargs) -> str:
    """Write a list of hyperlinked teachers.
    teachers is a list of abbreviated teacher names"""
    
    fullNameList = [gDatabase["teacher"][t]["attributionName"] for t in teachers]
    
    return LinkTeachersInText(ItemList(fullNameList,*args,**kwargs))


def ExcerptCount(tag:str) -> int:
    return gDatabase["tag"][tag].get("excerptCount",0)

def HtmlTagListItem(listItem: dict,showSubtagCount = False,showStar = True) -> str:
    indexStr = listItem["indexNumber"] + "." if listItem["indexNumber"] else ""
    
    countItems = []
    fTagCount = listItem["tag"] and gDatabase["tag"][listItem["tag"]].get("fTagCount",0)
    if fTagCount and showStar:
        countItems.append(f'{fTagCount}{FA_STAR}')
    subtagExcerptCount = listItem.get("subtagExcerptCount",0)
    itemCount = listItem["excerptCount"]
    if itemCount or subtagExcerptCount:
        if subtagExcerptCount:
            if not listItem['tag']:
                itemCount = "-"
            countItems.append(str(itemCount))
            if showSubtagCount:
                countItems.append(str(subtagExcerptCount))
        else:
            countItems.append(str(itemCount))
    if countItems:
        countStr = f' ({"/".join(countItems)})'
    else:
        countStr = ''
    
    if listItem['tag'] and not listItem['subsumed']:
        nameStr = HtmlTagLink(listItem['tag'],True) + countStr
    else:
        nameStr = listItem['name'] + ("" if listItem["subsumed"] else countStr)
    
    if listItem['pali'] and listItem['pali'] != listItem['name']:
        paliStr = '(' + listItem['pali'] + ')'
    elif ParseCSV.TagFlag.DISPLAY_GLOSS in listItem['flags']:
        paliStr = '(' + gDatabase['tag'][listItem['tag']]['glosses'][0] + ')'
        # If specified, use paliStr to display the tag's first gloss
    else:
        paliStr = ''
    
    if listItem['subsumed']:
        seeAlsoStr = 'see ' + HtmlTagLink(listItem['tag'],False) + countStr
    else:
        seeAlsoStr = ''
    
    joinBits = [s for s in [indexStr,nameStr,paliStr,seeAlsoStr] if s]
    return ' '.join(joinBits)

def IndentedHtmlTagList(tagList:list[dict] = [],showSubtagCount = True,showStar = True) -> str:
    """Generate html for an indented list of tags.
    tagList is the list of tags to print; use the global list if not provided"""
    
    a = Airium()
    
    if not tagList:
        tagList = gDatabase["tagDisplayList"]
        
    baseIndent = tagList[0]["level"]
    with a.div(Class="listing"):
        for item in tagList:
            bookmark = Utils.slugify(item["tag"] or item["name"])
            with a.p(id = bookmark,Class = f"indent-{item['level']-baseIndent}"):
                a(HtmlTagListItem(item,showSubtagCount=showSubtagCount,showStar=showStar))
    
    return str(a)

@lru_cache(maxsize=None)
def DrilldownTemplate(showStar:bool = False) -> pyratemp.Template:
    """Return a pyratemp template for an indented list of tags which can be expanded using
    the javascript toggle-view class.
    Variables within the template:
    xTagIndexes: the set of integer tag indexes to expand
    """

    tagList = gDatabase["tagDisplayList"]
    a = Airium()
    tagCountSoFar = Counter()
    with a.div(Class="listing"):
        for index, item in enumerate(tagList):           
            bookmark = Utils.slugify(item["tag"] or item["name"])

            tagCountSoFar[item["tag"]] += 1
            if item["tag"] and gDatabase["tag"][item["tag"]]["listIndex"] != index:
                bookmark += f"-{tagCountSoFar[item['tag']]}"
                    # If this is not the primary tag, add a unique number to its bookmark.

            with a.p(id = bookmark,Class = f"indent-{item['level']-1}"):
                itemHtml = HtmlTagListItem(item,showSubtagCount=True,showStar=showStar)
                
                drilldownLink = ""
                divTag = "" # These are start and end tags for the toggle-view divisions
                if index >= len(tagList) - 1:
                    nextLevel = 1
                else:
                    nextLevel = tagList[index + 1]["level"]
                if nextLevel > item["level"]: # Can the tag be expanded?
                    tagAtPrevLevel = -1
                    for reverseIndex in range(index - 1,-1,-1):
                        if tagList[reverseIndex]["level"] < item["level"]:
                            tagAtPrevLevel = reverseIndex
                            break
                    drilldownFile = DrilldownPageFile(index)
                    drilldownID = drilldownFile.replace(".html","-d")
                    prevLevelDrilldownFile = DrilldownPageFile(tagAtPrevLevel)
                    
                    boxType = f"$!'minus' if {index} in xTagIndexes else 'plus'!$"
                        # Code to be executed by pyratemp
                    plusBox = Html.Tag("i",{"class":f"fa fa-{boxType}-square toggle-view","id":drilldownID})("")
                    drilldownLink = Html.Tag("a",{"href":f"../drilldown/$!'{prevLevelDrilldownFile}' if {index} in xTagIndexes else '{drilldownFile}'!$"})(plusBox)
                        # Add html links to the drilldown boxes that work without Javascript

                    hideCode = f"""$!'' if {index} in xTagIndexes else 'style="display: none;"'!$"""
                    divTag = f'<div id="{drilldownID + ".b"}" {hideCode}>'
                elif nextLevel < item["level"]:
                    divTag = "</div>" * (item["level"] - nextLevel)
            
                joinBits = [s for s in [drilldownLink,itemHtml] if s]
                a(' '.join(joinBits))
            a(divTag)
    
    return pyratemp.Template(str(a))

def EvaluateDrilldownTemplate(expandSpecificTags:set[int] = frozenset(),showStar:bool = False) -> str:
    """Evaluate the drilldown template to expand the given set of tags.
    expandSpecificTags is the set of tag indexes to expand.
    The default is to expand all tags."""

    template = DrilldownTemplate(showStar=showStar)
    evaluated = template(xTagIndexes = expandSpecificTags)
    return str(evaluated)


def DrilldownPageFile(tagNumberOrName: int|str,jumpToEntry:bool = False) -> str:
    """Return the name of the page that has this tag expanded.
    The tag can be specified by number in the hierarchy or by name."""

    if type(tagNumberOrName) == str:
        tagNumber = gDatabase["tag"][tagNumberOrName]["listIndex"]
    else:
        tagNumber = tagNumberOrName

    indexStr = ""
    if tagNumber >= 0:
        tagList = gDatabase["tagDisplayList"]
        ourLevel = tagList[tagNumber]["level"]
        if tagNumber + 1 >= len(tagList) or tagList[tagNumber + 1]["level"] <= ourLevel:
            # If this tag doesn't have subtags, find its parent tag
            if ourLevel > 1:
                while tagList[tagNumber]["level"] >= ourLevel:
                    tagNumber -= 1
        
        tagName = tagList[tagNumber]["tag"]
        displayName = tagName or tagList[tagNumber]["name"]
        fileName = Utils.slugify(displayName) + ".html"
        if tagName and gDatabase["tag"][tagName]["listIndex"] != tagNumber:
            # If this is not a primary tag, append an index number to it
            indexStr = "-" + str(sum(1 for n in range(tagNumber) if tagList[n]["tag"] == tagName))
            fileName = Utils.AppendToFilename(fileName,indexStr)
    else:
        fileName = "root.html"

    if jumpToEntry:
        fileName += f"#{fileName.replace('.html','')}"
    return fileName

def DrilldownIconLink(tag: str,iconWidth = 20):
    drillDownPage = "../drilldown/" + DrilldownPageFile(gDatabase["tag"][tag]["listIndex"],jumpToEntry=True)
    return Html.Tag("a",dict(href=drillDownPage,title="Show in tag hierarchy"))(HtmlIcon("text-bullet-list-tree.svg",iconClass="small-icon"))

def DrilldownTags(pageInfo: Html.PageInfo) -> Iterator[Html.PageAugmentorType]:
    """Write a series of html files to create a hierarchial drill-down list of tags."""

    tagList = gDatabase["tagDisplayList"]

    for n,tag in enumerate(tagList):
        if (n + 1 < len(tagList) and tagList[n+1]["level"] > tag["level"]) or tag["level"] == 1: # If the next tag is deeper, then we can expand this one
            tagsToExpand = {n}
            reverseIndex = n - 1
            nextLevelToExpand = tag["level"] - 1
            while reverseIndex >= 0 and nextLevelToExpand > 0:
                if tagList[reverseIndex]["level"] <= nextLevelToExpand:
                    tagsToExpand.add(reverseIndex)
                    nextLevelToExpand = tagList[reverseIndex]["level"] - 1
                reverseIndex -= 1
            
            page = Html.PageDesc(pageInfo._replace(file=Utils.PosixJoin(pageInfo.file,DrilldownPageFile(n))))
            page.keywords.append(Utils.RemoveHtmlTags(tag["name"]))
            page.AppendContent(EvaluateDrilldownTemplate(expandSpecificTags=tagsToExpand))
            page.specialJoinChar["citationTitle"] = ""
            page.AppendContent(f': {Utils.RemoveHtmlTags(tag["name"])}',section="citationTitle")
            yield page

class StrEnum(str,Enum):
    pass

class TagDescriptionFlag(StrEnum):
    PALI_FIRST = "P"
    COUNT_FIRST = "N"
    NO_PALI = "p"
    NO_COUNT = "n"
    SHOW_STAR = "S"

def TagDescription(tag: dict,fullTag:bool = False,flags: str = "",listAs: str = "",link = True,drilldownLink = False) -> str:
    "Return html code describing this tag."
    
    xCount = tag.get("excerptCount",0)
    if xCount > 0 and TagDescriptionFlag.NO_COUNT not in flags:
        if TagDescriptionFlag.SHOW_STAR in flags and tag.get("fTagCount",0):
            starStr = f'{tag["fTagCount"]}{FA_STAR}'
            if TagDescriptionFlag.COUNT_FIRST in flags:
                countStr = f'({xCount}/{starStr})'
            else:
                countStr = f'({starStr}/{xCount})'
        else:
            countStr = f'({xCount})'
    else:
        countStr = ""

    if not listAs and fullTag:
        listAs = tag["fullTag"] if fullTag else tag["tag"]
    if TagDescriptionFlag.SHOW_STAR and not TagDescriptionFlag.NO_COUNT:
        listAs += f'&nbsp;{FA_STAR}/'
    tagStr = HtmlTagLink(tag['tag'],fullTag,text = listAs,link=link)
    if TagDescriptionFlag.PALI_FIRST in flags:
        tagStr = '[' + tagStr + ']'

    paliStr = ''
    if not TagDescriptionFlag.NO_PALI in flags:
        if tag['pali'] and tag['pali'] != tag['tag']:
            paliStr = tag['fullPali'] if fullTag else tag['pali']
        elif ParseCSV.TagFlag.DISPLAY_GLOSS in tag["flags"]:
            if tag['glosses']:
                paliStr = tag['glosses'][0]
            else:
                Alert.caution(tag,"has flag g: DISPLAY_GLOSS but has no glosses.")
    if paliStr and TagDescriptionFlag.PALI_FIRST not in flags:
            paliStr = '(' + paliStr + ')'

    drillDownStr = DrilldownIconLink(tag["tag"],iconWidth = 12) if drilldownLink else ""

    if TagDescriptionFlag.COUNT_FIRST in flags:
        joinList = [drillDownStr,countStr,tagStr,paliStr]
    elif TagDescriptionFlag.PALI_FIRST in flags:
        joinList = [drillDownStr,paliStr,tagStr,countStr]
    else:
        joinList = [drillDownStr,tagStr,paliStr,countStr]
    
    return ' '.join(s for s in joinList if s)

def NumericalTagList(pageDir: str) -> Html.PageDescriptorMenuItem:
    """Write a list of numerical tags sorted by number:
    i.e. Three Refuges, Four Noble Truths, Five Faculties."""

    info = Html.PageInfo("Numerical",Utils.PosixJoin(pageDir,"NumericalTags.html"),"Tags – Numerical")
    yield info
    
    numericalTags = [tag for tag in gDatabase["tag"].values() if tag["number"]]
    numericalTags.sort(key=lambda t: int(t["number"]))

    spaceAfter = {tag1["tag"] for tag1,tag2 in itertools.pairwise(numericalTags) if tag1["number"] == tag2["number"]}
        # Tags which are followed by a tag having the same number should have a space after them

    numberNames = {3:"Threes", 4:"Fours", 5:"Fives", 6:"Sixes", 7:"Sevens", 8:"Eights",
                   9:"Nines", 10:"Tens", 12: "Twelves", 37:"Thiry-sevens"}
    def SubtagList(tag: dict) -> tuple[str,str,str]:
        number = int(tag["number"])
        numberName = numberNames[number]

        fullList = gDatabase["tagDisplayList"]
        baseIndex = tag["listIndex"]
        tagList = [fullList[baseIndex]]
        baseLevel = tagList[0]["level"]

        index = baseIndex + 1
        addedNumberedTag = False
        while index < len(fullList) and fullList[index]["level"] > baseLevel:
            curTag = fullList[index]
            if curTag["level"] == baseLevel + 1:
                if curTag["indexNumber"] or not addedNumberedTag:
                    tagList.append(curTag)
                    if curTag["indexNumber"]:
                        addedNumberedTag = True
            index += 1

        storedNumber = tagList[0]["indexNumber"]
        tagList[0]["indexNumber"] = ""    # Temporarily remove any digit before the first entry.
        content = IndentedHtmlTagList(tagList,showSubtagCount=False,showStar = False)
        tagList[0]["indexNumber"] = storedNumber

        content = content.replace('class="indent-0">','class="indent-0" style="font-weight:bold;">')
            # Apply boldface to the top line only
        content = re.sub(r"(\s+)</p>",r":\1</p>",content,count = 1)
            # Add a colon at the end of the first paragraph only.
        if tag["tag"] in spaceAfter:
            content += "\n<br>"
        return numberName,content,numberName.lower()

    pageContent = Html.ListWithHeadings(numericalTags,SubtagList,headingWrapper = Html.Tag("h2",dict(id="HEADING_ID")))

    page = Html.PageDesc(info)
    page.AppendContent(pageContent)
    page.AppendContent(HtmlIcon("tags"),section="titleIcon")
    page.AppendContent("Numerical tags",section="citationTitle")
    page.keywords = ["Tags","Numerical tags"]
    yield page 

def PrintCommonTags(tags: list[dict],countFirst:bool) -> str:
    """Return a html string listing these tags and details of how many times they are applied as fTags."""
    a = Airium()
    with a.p():
        a("""<b>Bold tags</b>: solo subtopics <i>Italic tags</i>: clustered subtopics <br> 
Key: (fTags/subtopicFTags:min-max). '/subtopicFTags' is omitted if all featured excerpts are included in all subtopics.""")
    with a.div(Class="listing"):
        for tag in tags:
            with a.p():
                code = ReviewDatabase.FTagStatusCode(gDatabase["tag"][tag])
                tagLink = HtmlTagLink(tag)
                fTagCount = gDatabase["tag"][tag].get("fTagCount",0)
                fTagCountStr = str(fTagCount)
                if tag in Database.KeyTopicTags():
                    subtopicFTagCount = gDatabase["tag"][tag].get("subtopicFTagCount",0)
                    if subtopicFTagCount < fTagCount:
                        fTagCountStr += f"/{subtopicFTagCount}"
                
                minFTag,maxFTag,diffFTag = ReviewDatabase.OptimalFTagCount(gDatabase["tag"][tag])
                
                tagStyle = Html.Wrapper()
                if tag in Database.SoloSubtopics():
                    tagStyle = Html.Tag("b")
                elif tag in Database.KeyTopicTags():
                    tagStyle = Html.Tag("i")
                
                if countFirst:
                    a(f"{ExcerptCount(tag)} {code} {tagStyle(tagLink)} ({fTagCountStr}:{minFTag}-{maxFTag})")
                else:
                    a(f"{code} {tagStyle(tagLink)} {ExcerptCount(tag)} ({fTagCountStr}:{minFTag}-{maxFTag})")
    
    return str(a)

def MostCommonTagList(pageDir: str) -> Html.PageDescriptorMenuItem:
    """Write a list of tags sorted by number of excerpts."""
    
    info = Html.PageInfo("Most common",Utils.PosixJoin(pageDir,"SortedTags.html"),"Tags – Most common")
    yield info

    a = Airium()
    # Sort descending by number of excerpts and in alphabetical order
    tagsSortedByQCount = sorted((tag for tag in gDatabase["tag"] if ExcerptCount(tag)),key = lambda tag: (-ExcerptCount(tag),tag))
    with a.div(Class="listing"):
        for tag in tagsSortedByQCount:
            with a.p():
                a(TagDescription(gDatabase["tag"][tag],fullTag=True,flags=TagDescriptionFlag.COUNT_FIRST,drilldownLink=True))
    
    page = Html.PageDesc(info)

    printableLinks = Html.Tag("a",{"href":Utils.PosixJoin("../indexes/SortedTags_print.html#noframe")})("Printable")
    if gOptions.uploadMirror == "preview":
        printableLinks += "&emsp;" + Html.Tag("a",{"href":Utils.PosixJoin("../indexes/DeficientTags_print.html#noframe")})("Deficient")
    page.AppendContent(Html.Tag("span",{"class":"floating-menu hide-thin-screen-1 noscript-show"})(printableLinks))

    page.AppendContent(str(a))
    page.AppendContent(HtmlIcon("tags"),section="titleIcon")
    page.AppendContent("Most common tags",section="citationTitle")
    page.keywords = ["Tags","Most common tags"]
    yield page

    # Now yield a printable version for tag counting purposes
    tagsSortedByQCount = sorted((tag for tag in gDatabase["tag"] if ExcerptCount(tag) >= gOptions.significantTagThreshold or "fTagCount" in gDatabase["tag"][tag]),
                                key = lambda tag: (-ExcerptCount(tag),tag))

    page = Html.PageDesc(info._replace(file = Utils.PosixJoin(pageDir,"SortedTags_print.html")))
    page.AppendContent(PrintCommonTags(tagsSortedByQCount,countFirst=True))
    page.AppendContent("Most common tags",section="citationTitle")
    page.keywords = ["Tags","Most common tags"]
    yield page

    # Make a page with only deficient tags
    if gOptions.uploadMirror == "preview":
        deficientTags = [tag for tag in tagsSortedByQCount if ReviewDatabase.FTagStatusCode(gDatabase["tag"][tag]) in ("∅","⊟")]
        page = Html.PageDesc(info._replace(file = Utils.PosixJoin(pageDir,"DeficientTags_print.html")))
        page.AppendContent(PrintCommonTags(deficientTags,countFirst=True))
        page.AppendContent("Deficient tags",section="citationTitle")
        page.keywords = ["Tags","Deficient tags"]
        yield page

    # Create another version sorted by name. This will be linked to on the alphabetical page.
    tagsSortedByQCount = sorted(tagsSortedByQCount)
    page = Html.PageDesc(info._replace(file = Utils.PosixJoin(pageDir,"AlphabeticalTags_print.html")))
    page.AppendContent(PrintCommonTags(tagsSortedByQCount,countFirst=False))
    page.AppendContent("Alphabetized common tags",section="citationTitle")
    page.keywords = ["Tags","Alphabetized common tags"]
    yield page

def ProperNounTag(tag:dict) -> bool:
    """Return true if this tag is a proper noun.
    Tag is a tag dict object."""
    return ParseCSV.TagFlag.PROPER_NOUN in tag["flags"] or (tag["supertags"] and ParseCSV.TagFlag.PROPER_NOUN_SUBTAGS in gDatabase["tag"][tag["supertags"][0]]["flags"])

class _Alphabetize(NamedTuple):
    "Helper tuple to alphabetize a list."
    sortBy: str
    html: str
def Alphabetize(sortBy: str,html: str) -> _Alphabetize:
    return _Alphabetize(Utils.RemoveDiacritics(sortBy).lower(),html)

def LanguageTag(tagString: str) -> str:
    "Return lang (lowercase, no diacritics) when tagString matches <i>LANG</i>. Otherwise return an empty string."
    tagString = Utils.RemoveDiacritics(tagString).lower()
    match = re.search(r"<i>([^<]*)</i>$",tagString)
    if match:
        return match[1]
    else:
        return ""

def RemoveLanguageTag(tagString: str) -> str:
    "Return tagString with any language tag removed."
    return re.sub(r"<i>([^<]*)</i>","",tagString).strip()

def AlphabeticalTagList(pageDir: str) -> Html.PageDescriptorMenuItem:
    """Write a list of tags sorted alphabetically."""
    
    pageInfo = Html.PageInfo("Alphabetical",Utils.PosixJoin(pageDir,"AlphabeticalTags.html"),"Tags – Alphabetical")
    yield pageInfo

    prefixes = sorted(list(gDatabase["prefix"]),key=len,reverse=True)
        # Sort prefixes so the longest prefix matches first
    prefixes = [p if p.endswith("/") else p + " " for p in prefixes]
        # Add a space to each prefix that doesn't end with "/"
    slashPrefixes = Utils.RegexMatchAny(p for p in prefixes if p.endswith("/"))
    prefixRegex = Utils.RegexMatchAny(prefixes,capturingGroup=True) + r"(.+)"
    noAlphabetize = {"alphabetize":""}

    def AlphabetizeName(string: str) -> str:
        if gDatabase["name"].get(string,noAlphabetize)["alphabetize"]:
            return gDatabase["name"][string]["alphabetize"]
        match = re.match(prefixRegex,string)
        if match:
            return match[2] + ", " + match[1].strip(" /")
        else:
            return string

    def EnglishEntry(tag: dict,tagName: str,fullTag:bool=False,drilldownLink = True) -> _Alphabetize:
        "Return an entry for an English item in the alphabetized list"
        tagName = AlphabetizeName(tagName)
        html = TagDescription(tag,fullTag=fullTag,listAs=tagName,drilldownLink=drilldownLink)
        return Alphabetize(tagName,html)

    def NonEnglishEntry(tag: dict,fullTag:bool = False,drilldownLink = True) -> _Alphabetize:
        if fullTag:
            text = tag["fullPali"]
        else:
            text = tag["pali"]
        html = TagDescription(tag,fullTag,flags=TagDescriptionFlag.PALI_FIRST,drilldownLink=drilldownLink)
        return Alphabetize(text,html)

    entries = defaultdict(list)
    for tag in gDatabase["tag"].values():
        if not tag["htmlFile"] or ParseCSV.TagFlag.HIDE in tag["flags"]:
            continue

        nonEnglish = tag["tag"] == tag["pali"]
        properNoun = ProperNounTag(tag)
        englishAlso = ParseCSV.TagFlag.ENGLISH_ALSO in tag["flags"]
        hasPali = tag["pali"] and not LanguageTag(tag["fullPali"])
            # Non-Pāli language full tags end in <i>LANGUAGE</i>

        if nonEnglish: # If this tag has no English entry, add it to the appropriate language list and go on to the next tag
            entry = EnglishEntry(tag,tag["fullPali"],fullTag=False)
            if hasPali:
                if ParseCSV.TagFlag.CAPITALIZE not in tag["flags"]:
                    entry = entry._replace(html=entry.html.lower())
                    # Pali words are in lowercase unless specifically capitalized
                entries["pali"].append(entry)
            else:
                entries["other"].append(entry)
            if properNoun:
                entries["proper"].append(entry) # Non-English proper nouns are listed here as well
            if englishAlso:
                entries["english"].append(entry)
        else:
        
            if properNoun:
                entries["proper"].append(EnglishEntry(tag,tag["fullTag"],fullTag=True))
                if englishAlso:
                    entries["english"].append(entry)
            else:
                entries["english"].append(EnglishEntry(tag,tag["fullTag"],fullTag=True))
                if not AlphabetizeName(tag["fullTag"]).startswith(AlphabetizeName(tag["tag"])):
                    entries["english"].append(EnglishEntry(tag,tag["tag"]))
                    # File the abbreviated tag separately if it's not a simple truncation
            
            if re.match(slashPrefixes,tag["fullTag"]):
                entries["english"].append(Alphabetize(tag["fullTag"],TagDescription(tag,fullTag=True)))
                # Alphabetize tags like History/Thailand under History/Thailand as well as Thailand, History

            if tag["pali"]: # Add an entry for foriegn language items
                entry = NonEnglishEntry(tag)
                if hasPali:
                    entries["pali"].append(entry)
                else:
                    entries["other"].append(entry)
                if englishAlso:
                    entries["english"].append(entry)
            if tag["fullPali"] and tag["fullPali"] != tag["pali"]: # Add an entry for the full Pāli tag
                entry = NonEnglishEntry(tag,fullTag=True)
                if hasPali:
                    entries["pali"].append(entry)
                else:
                    entries["other"].append(entry)
            
            for translation in tag["alternateTranslations"]:
                html = f"{translation} – alternative translation of {TagDescription(tag,fullTag=True,flags=TagDescriptionFlag.PALI_FIRST,drilldownLink=False)}"
                if LanguageTag(translation):
                    entries["other"].append(Alphabetize(translation,html))
                else:
                    entries["english"].append(Alphabetize(translation,html))
            
        for gloss in tag["glosses"]:
            gloss = AlphabetizeName(gloss)
            paliGloss = LanguageTag(gloss) == "pali"
            if not paliGloss or properNoun: # Pali is listed in lowercase
                gloss = gloss[0].capitalize() + gloss[1:]
            if paliGloss:
                gloss = RemoveLanguageTag(gloss)
                
            html = f"{gloss} – see {TagDescription(tag,fullTag=True)}"
            if paliGloss:
                entries["pali"].append(Alphabetize(gloss,html))
            elif LanguageTag(gloss):
                entries["other"].append(Alphabetize(gloss,html))
            else:
                entries["english"].append(Alphabetize(gloss,html))
            if properNoun:
                entries["proper"].append(Alphabetize(gloss,html))
    
    for subsumedTag in gDatabase["tagSubsumed"].values():
        if ParseCSV.TagFlag.HIDE in subsumedTag["flags"]:
            continue

        subsumedUnder = gDatabase["tag"][subsumedTag["subsumedUnder"]]
        referenceText = f" – see {TagDescription(subsumedUnder,fullTag=True)}"
        
        if subsumedTag["tag"] != subsumedTag["pali"]:
            entries["english"].append(Alphabetize(subsumedTag["fullTag"],TagDescription(subsumedTag,fullTag = True,link = False) + referenceText))
            if not AlphabetizeName(subsumedTag["fullTag"]).startswith(AlphabetizeName(subsumedTag["tag"])):
                # File the abbreviated tag separately if it's not a simple truncation
                entries["english"].append(Alphabetize(subsumedTag["tag"],TagDescription(subsumedTag,fullTag = False,link = False) + referenceText))
        
        hasPali = subsumedTag["pali"] and not LanguageTag(subsumedTag["fullPali"])
        if subsumedTag["pali"]:
            entry = Alphabetize(subsumedTag["pali"],f"{subsumedTag['pali']} [{subsumedTag['tag']}]{referenceText}")
            if hasPali:
                entries["pali"].append(entry)
            else:
                entries["other"].append(entry)
            
            if subsumedTag["pali"] != subsumedTag["fullPali"]:
                entry = Alphabetize(subsumedTag["fullPali"],f"{subsumedTag['fullPali']} [{subsumedTag['fullTag']}]{referenceText}")
                if hasPali:
                    entries["pali"].append(entry)
                else:
                    entries["other"].append(entry)
        
        for gloss in subsumedTag["glosses"] + subsumedTag["alternateTranslations"]:
            language = LanguageTag(gloss)
            if language:
                if language == "pali":
                    gloss = RemoveLanguageTag(gloss)
                    entries["pali"].append(Alphabetize(gloss,gloss + referenceText))
                else:
                    entries["other"].append(Alphabetize(gloss,gloss + referenceText))
            else:
                entries["english"].append(Alphabetize(gloss,gloss + referenceText))

    def Deduplicate(iterable: Iterable) -> Iterator:
        iterable = iter(iterable)
        prevItem = next(iterable)
        yield prevItem
        for item in iterable:
            if item != prevItem:
                yield item
                prevItem = item

    for e in entries.values():
        e.sort()
    allList = list(Deduplicate(sorted(itertools.chain.from_iterable(entries.values()))))

    def TagItem(line:Alphabetize) -> str:
        return line.sortBy[0].upper(),"".join(("<p>",line.html,"</p>"))

    def LenStr(items: list) -> str:
        return f" ({len(items)})"
    

    args = dict(addMenu=True,countItems=False,bodyWrapper=Html.Tag("div",{"class":"listing"}))
    subMenu = [
        [pageInfo._replace(title = "All tags"+LenStr(allList)),str(Html.ListWithHeadings(allList,TagItem,**args))],
        [pageInfo._replace(title = "English"+LenStr(entries["english"]),file=Utils.PosixJoin(pageDir,"EnglishTags.html")),
            str(Html.ListWithHeadings(entries["english"],TagItem,**args))],
        [pageInfo._replace(title = "Pāli"+LenStr(entries["pali"]),file=Utils.PosixJoin(pageDir,"PaliTags.html")),
            str(Html.ListWithHeadings(entries["pali"],TagItem,**args))],
        [pageInfo._replace(title = "Other languages"+LenStr(entries["other"]),file=Utils.PosixJoin(pageDir,"OtherTags.html")),
            str(Html.ListWithHeadings(entries["other"],TagItem,**args))],
        [pageInfo._replace(title = "People/places/traditions"+LenStr(entries["proper"]),file=Utils.PosixJoin(pageDir,"ProperTags.html")),
            str(Html.ListWithHeadings(entries["proper"],TagItem,**args))]
    ]
    if gOptions.uploadMirror == "preview":
        subMenu.append([Html.PageInfo("Printable",Utils.PosixJoin(pageDir,"AlphabeticalTags_print.html#noframe"))])

    basePage = Html.PageDesc()
    basePage.keywords = ["Tags","Alphabetical"]
    basePage.AppendContent(HtmlIcon("tags"),section="titleIcon")
    for page in basePage.AddMenuAndYieldPages(subMenu,**EXTRA_MENU_STYLE):
        titleWithoutLength = " ".join(page.info.title.split(" ")[:-1])
        page.keywords.append(titleWithoutLength)
        citation = f"Alphabetical tags: {titleWithoutLength}"

        page.AppendContent(citation,section="citationTitle")
        yield page

def PlayerTitle(item:dict) -> str:
    """Generate a title string for the audio player for an excerpt or session.
    The string will be no longer than gOptions.maxPlayerTitleLength characters."""

    sessionNumber = item.get("sessionNumber",None)
    excerptNumber = item.get("excerptNumber",None)
    titleItems = []
    if sessionNumber:
        titleItems.append(f"S{sessionNumber}")
    if excerptNumber:
        titleItems.append(f"E{excerptNumber}")
    
    lengthSoFar = len(" ".join(titleItems))
    fullEventTitle = Utils.RemoveHtmlTags(gDatabase['event'][item['event']]['title'])
    if titleItems:
        fullEventTitle += ","
    titleItems.insert(0,Utils.EllideText(fullEventTitle,gOptions.maxPlayerTitleLength - lengthSoFar - 1))
    return " ".join(titleItems)
    

def AudioIcon(hyperlink: str,title: str,titleLink:str = "",dataDuration:str = "",downloadAs:str = "") -> str:
    "Return an audio icon with the given hyperlink"
    filename = title + ".mp3"

    a = Airium(source_minify=True)
    dataDict = {}
    if titleLink:
        dataDict["data-title-link"] = titleLink
    if dataDuration:
        dataDict["data-duration"] = str(Mp3DirectCut.ToTimeDelta(dataDuration).seconds)
    if downloadAs:
        dataDict["download-as"] = downloadAs
    with a.get_tag_('audio-chip')(src = hyperlink, title = title, **dataDict):
        with a.a(href = hyperlink,download=filename):
            a(f"Download audio")
        a(f" ({dataDuration})")
	
    return str(a)

def Mp3ExcerptLink(excerpt: dict) -> str:
    """Return an html-formatted audio icon linking to a given excerpt."""
    
    excerptLink = f"events/{excerpt['event']}.html#{Database.ItemCode(Database.FragmentSource(excerpt))}"
    return AudioIcon(Database.Mp3Link(excerpt),title=PlayerTitle(excerpt),titleLink=excerptLink,dataDuration = excerpt["duration"])
    
def Mp3SessionLink(session: dict) -> str:
    """Return an html-formatted audio icon linking to a given session."""
    
    sessionLink = f"events/{session['event']}.html#{Database.ItemCode(session)}"
    return AudioIcon(Database.Mp3Link(session),
                     title=PlayerTitle(session),
                     titleLink = sessionLink,
                     dataDuration = session["duration"],
                     downloadAs = session["filename"])
    
def TeacherLink(teacher:str) -> str:
    "Return a link to a given teacher page. Return an empty string if the teacher doesn't have a page."
    directory = "../teachers/"

    htmlFile = gDatabase["teacher"][teacher]["htmlFile"]
    if htmlFile:
        return f"{directory}{htmlFile}"
    else:
        return ""
    
def EventDateStr(event: dict) -> str:
    "Return a string describing when the event occured"
    
    dateStr = Utils.ReformatDate(event["startDate"])
    if event["endDate"] and event["endDate"] != event["startDate"]:
        dateStr += " to " + Utils.ReformatDate(event["endDate"])
    return dateStr

def EventSeriesAndDateStr(event: dict) -> str:
    "Return a string describing the event series and date"
    joinItems = []
    series = event["series"][0]
    if series != "Other":
        if series == "Other retreats":
            series = "Retreat"
        if series != "Q&ampA sessions" or event["sessions"] == 1: # Don't remove the s for multiple Q&A sessions
            if series.endswith("ies"):
                series = re.sub(r'ies$','y',series)
            else:
                series = re.sub(r's$','',series)
        joinItems.append(series)
    joinItems.append(EventDateStr(event))
    return ", ".join(joinItems)

def EventVenueStr(event: dict) -> str:
    "Return a string describing the event venue"
    if event["venue"] == "None":
        if event["format"] == "Interview":
            return "Online interview" if event["medium"] == "Online" else "Interview"
        if event["medium"] == "Online":
            return "Online"
        else:
            Alert.caution(event,": only online events should specify venue = None.")
            return ""
    
    venueStr = event['venue']
    if gDatabase['venue'][event['venue']]['location']:
        venueStr += f" in {gDatabase['venue'][event['venue']]['location']}"
    if event["medium"] == "Online":
        venueStr = "Online from " + venueStr
    elif event["medium"] == "Hybrid":
        venueStr += " and online"
    return venueStr

def ExcerptDurationStr(excerpts: List[dict],countEvents = True,countSessions = True,countSessionExcerpts = False,sessionExcerptDuration = True) -> str:
    "Return a string describing the duration of the excerpts we were passed."
    
    if not excerpts:
        return "No excerpts"
    
    events = set(x["event"] for x in excerpts)
    sessions = set((x["event"],x["sessionNumber"]) for x in excerpts) # Use sets to count unique elements

    duration = timedelta()
    for _,sessionExcerpts in itertools.groupby(excerpts,lambda x: (x["event"],x["sessionNumber"])):
        sessionExcerpts = list(sessionExcerpts)
        duration += sum((Mp3DirectCut.ToTimeDelta(x["duration"]) for x in Database.RemoveFragments(sessionExcerpts) if x["fileNumber"] or (sessionExcerptDuration and len(sessionExcerpts) == 1)),start = timedelta())
            # Don't sum session excerpts (fileNumber = 0) unless the session excerpt is the only excerpt in the list
            # This prevents confusing results due to double counting times
    
    strItems = []
    
    if len(events) > 1 and countEvents:
        strItems.append(f"{len(events)} events,")
    
    if len(sessions) > 1 and countSessions:
        strItems.append(f"{len(sessions)} sessions,")
    
    excerptCount = Database.CountExcerpts(excerpts,countSessionExcerpts)
    if excerptCount > 1:
        strItems.append(f"{excerptCount} excerpts,")
    else:
        strItems.append(f"{excerptCount} excerpt,")
    
    strItems.append(f"{Mp3DirectCut.TimeDeltaToStr(duration)} total duration")
    
    return ' '.join(strItems)

class Formatter: 
    """A class that formats lists of events, sessions, and excerpts into html"""
    
    def __init__(self):        
        self.excerptNumbers = True # Display excerpt numbers?
        self.excerptDefaultTeacher = set() # Don't print the list of teachers if it matches the items in this list / set
        self.excerptOmitTags = set() # Don't display these tags in excerpt description
        self.excerptBoldTags = set() # Display these tags in boldface
        self.excerptOmitSessionTags = True # Omit tags already mentioned by the session heading
        self.excerptPreferStartTime = False # Display the excerpt start time instead of duration when available
        self.excerptAttributeSource = False # Add a line after each excerpt linking to its source?
            # Best used with showHeading = False
        self.excerptShowFragmentPlayers = True # Include fragment annotation bodies in html?
        self.showFTagOrder = () # Display {fTagOrder} before each excerpt
            # Helps to sort featured excerpts in the preview edition
        
        self.showHeading = True # Show headings at all?
        self.headingShowEvent = True # Show the event name in headings?
        self.headingShowSessionTitle = False # Show the session title in headings?
        self.headingLinks = True # Link to the event page in our website?
        self.headingShowTeacher = True # Include the teacher name in headings?
        self.headingAudio = False # Link to original session audio?
        self.headingShowTags = True # List tags in the session heading
    
    def SetHeaderlessFormat(self,headerless: bool = True) -> None:
        "Switch to the headerless excerpt format."
        self.excerptOmitSessionTags = not headerless
        self.showHeading = not headerless
        self.headingShowTeacher = not headerless
        self.excerptNumbers = not headerless
        self.excerptAttributeSource = headerless

    def FormatExcerpt(self,excerpt:dict) -> str:
        "Return excerpt formatted in html according to our stored settings."
        
        a = Airium(source_minify=True)
        
        a(Mp3ExcerptLink(excerpt))
        a.br()
        a(' ')
        if self.excerptNumbers:
            if excerpt['excerptNumber']:
                with a.span(Class="excerpt-number"):
                    a(f"{excerpt['excerptNumber']}.")
            else:
                a(f"[{Html.Tag('span',{'class':'session-excerpt-header'})('Session')}]")
        if self.showFTagOrder and set(excerpt["fTags"]) & set(self.showFTagOrder):
            a(" {" + str(Database.FTagAndOrder(excerpt,self.showFTagOrder)[3]) + "}")

        a(" ")
        if self.excerptPreferStartTime and excerpt['excerptNumber'] and (excerpt["clips"][0].file == "$" or excerpt.get("startTimeInSession",None)):
            a(f'[{excerpt.get("startTimeInSession",None) or excerpt["clips"][0].start}] ')

        def ListAttributionKeys() -> Generator[Tuple[str,str]]:
            for num in range(1,10):
                numStr = str(num) if num > 1 else ""
                yield ("attribution" + numStr, "teachers" + numStr)

        bodyWithAttributions = excerpt["body"]
        for attrKey,teacherKey in ListAttributionKeys():
            if attrKey not in excerpt:
                break

            if set(excerpt[teacherKey]) != set(self.excerptDefaultTeacher) or ParseCSV.ExcerptFlag.ATTRIBUTE in excerpt["flags"]: # Compare items irrespective of order
                teacherList = [gDatabase["teacher"][t]["attributionName"] for t in excerpt[teacherKey]]
            else:
                teacherList = []

            if teacherList or gOptions.attributeAll:
                attribution = excerpt[attrKey]
            else:
                attribution = ""
            
            bodyWithAttributions = bodyWithAttributions.replace("{"+ attrKey + "}",attribution)
        
        if ParseCSV.ExcerptFlag.END_COLON in excerpt["flags"]:
            bodyWithAttributions = re.sub(r"[,:.;]?\s*$",": ",bodyWithAttributions,count=1)
                # count=1 is required because the regex otherwise matches the text it has just substituted

        a(bodyWithAttributions + ' ')
        
        tagStrings = []
        for n,tag in enumerate(excerpt["tags"]):
            if self.excerptOmitSessionTags:
                omitTags = set.union(self.excerptOmitTags,set(Database.FindSession(gDatabase["sessions"],excerpt["event"],excerpt["sessionNumber"])["tags"]))
            else:
                omitTags = set(self.excerptOmitTags)
            omitTags -= set(excerpt["fTags"]) # Always show fTags
            omitTags -= set(excerpt.get("fragmentFTags",()))

            if n and n == excerpt["qTagCount"]:
                tagStrings.append("//") # Separate QTags and ATags with the symbol //

            text = tag
            if tag in excerpt["fTags"] or tag in excerpt.get("fragmentFTags",()):
                text += f'&nbsp;{FA_STAR}'
                text += "?" * min(Database.FTagOrder(excerpt,[tag]) - 1000,10 if gOptions.draftFTags in ("mark","number") else 0)
                    # Add ? to uncertain fTags; "?" * -N = ""
            if tag in self.excerptBoldTags: # Always print boldface tags
                tagStrings.append(f'<b>[{HtmlTagLink(tag,text=text)}]</b>')
            elif tag not in omitTags: # Don't print tags which should be omitted
                tagStrings.append(f'[{HtmlTagLink(tag,text=text)}]')
            
        a(' '.join(tagStrings))

        return str(a)
    
    def FormatAnnotation(self,excerpt: dict,annotation: dict,tagsAlreadyPrinted: set) -> str:
        "Return annotation formatted in html according to our stored settings. Don't print tags that have appeared earlier in this excerpt"
        
        a = Airium(source_minify=True)

        body = annotation["body"]
        if ParseCSV.ExcerptFlag.END_COLON in annotation["flags"]:
            body = re.sub(r"[,:.;]?\s*$",":",body,count=1)
                # count=1 is required because the regex otherwise matches the text it has just substituted
        a(body + " ")
        
        tagStrings = []
        for n,tag in enumerate(annotation.get("tags",())):
            omitTags = tagsAlreadyPrinted.union(self.excerptOmitTags) - set(excerpt.get("fragmentFTags",())) # - set(excerpt["fTags"]) 
            
            text = tag
            if tag in excerpt["fTags"] or tag in excerpt.get("fragmentFTags",()):
                text += f'&nbsp;{FA_STAR}'
                text += "?" * min(Database.FTagOrder(excerpt,[tag]) - 1000,10 if gOptions.draftFTags in ("mark","number") else 0)
            if tag in self.excerptBoldTags: # Always print boldface tags
                tagStrings.append(f'<b>[{HtmlTagLink(tag,text=text)}]</b>')
            elif tag not in omitTags: # Don't print tags which should be omitted
                tagStrings.append(f'[{HtmlTagLink(tag,text=text)}]')
            
        a(' '.join(tagStrings))
        
        return str(a)
        
    def FormatSessionHeading(self,session:dict,linkSessionAudio = None,horizontalRule = True) -> str:
        "Return an html string representing the heading for this section"
        
        if linkSessionAudio is None:
            linkSessionAudio = self.headingAudio

        a = Airium(source_minify=True)
        event = gDatabase["event"][session["event"]]

        bookmark = Database.ItemCode(session)
        with a.div(Class = "title",id = bookmark):
            if self.headingShowEvent: 
                if self.headingLinks:
                    with (a.a(href = Database.EventLink(session["event"]))):
                        a(event["title"])
                else:
                    a(event["title"])
                if session["sessionNumber"] > 0:
                    a(", ")
            
            teachersToList = session["teachers"]
            if session["sessionNumber"] > 0:
                sessionTitle = f'Session {session["sessionNumber"]}'
                if self.headingShowSessionTitle and session["sessionTitle"]:
                    sessionName = session["sessionTitle"]
                    teachersToList = [t for t in teachersToList if
                                      gDatabase["teacher"][t]["attributionName"] not in sessionName and 
                                      gDatabase["teacher"][t]["fullName"] not in sessionName]
                        # Don't duplicate teacher names mentioned in the session title.
                    sessionName = LinkTeachersInText(sessionName,session["teachers"])
                    sessionTitle += ': ' + sessionName
            else:
                sessionTitle = ""
            
            if self.headingLinks:
                with a.a(href = Database.EventLink(session["event"],session["sessionNumber"])):
                    a(sessionTitle)
            else:
                a(sessionTitle)
            
            itemsToJoin = []
            if self.headingShowEvent or sessionTitle:
                itemsToJoin.append("") # add an initial - if we've already printed part of the heading
            
            teacherList = ListLinkedTeachers(teachersToList,lastJoinStr = " and ")
            
            if teacherList and self.headingShowTeacher:
                itemsToJoin.append(teacherList)
            
            itemsToJoin.append(Utils.ReformatDate(session['date']))

            a(' – '.join(itemsToJoin))

            if self.headingShowTags:
                a.br()
                tagStrings = []
                for tag in session["tags"]:
                    tagStrings.append('[' + HtmlTagLink(tag) + ']')
                a(' '.join(tagStrings))

            if linkSessionAudio and session['filename']:
                audioLink = Mp3SessionLink(session)
                a(audioLink) 
        
        return str(a)
    
    def HtmlExcerptList(self,excerpts: List[dict]) -> str:
        """Return a html list of the excerpts."""
        
        a = Airium()
        prevEvent = None
        prevSession = None
        if excerpts:
            lastExcerpt = excerpts[-1]
        else:
            lastExcerpt = None
        
        localFormatter = copy.deepcopy(self) # Make a copy in case the formatter object is reused
        for count,x in enumerate(excerpts):
            if localFormatter.showHeading and (x["event"] != prevEvent or x["sessionNumber"] != prevSession):
                session = Database.FindSession(gDatabase["sessions"],x["event"],x["sessionNumber"])

                linkSessionAudio = self.headingAudio and x["fileNumber"]
                    # Omit link to the session audio if the first excerpt is a session excerpt with a body that will include it
                hr = x["fileNumber"] or x["body"]
                    # Omit the horzional rule if the first excerpt is a session excerpt with no body
                    
                a(localFormatter.FormatSessionHeading(session,linkSessionAudio,hr))
                prevEvent = x["event"]
                prevSession = x["sessionNumber"]
                if localFormatter.headingShowTeacher and len(session["teachers"]) == 1: 
                        # If there's only one teacher who is mentioned in the session heading, don't mention him/her in the excerpts
                    localFormatter.excerptDefaultTeacher = set(session["teachers"])
                else:
                    localFormatter.excerptDefaultTeacher = self.excerptDefaultTeacher
                
            hasMultipleAnnotations = sum(len(a["body"]) > 0 for a in x["annotations"]) > 1
            if x["body"] or (not x["fileNumber"] and hasMultipleAnnotations):
                """ Render blank session excerpts which have more than one annotation as [Session].
                    If a blank session excerpt has only one annotation, [Session] will be added below."""
                with a.p(id = Database.ItemCode(x)):
                    a(localFormatter.FormatExcerpt(x))
            
            tagsAlreadyPrinted = set(x["tags"])
            for annotation in x["annotations"]:
                if annotation["body"] and not (annotation["kind"] == "Fragment" and not self.excerptShowFragmentPlayers):
                    indentLevel = annotation['indentLevel']
                    if not x["fileNumber"] and not x["body"] and not hasMultipleAnnotations:
                        # If a single annotation follows a blank session excerpt, don't indent and add [Session] in front of it
                        indentLevel = 0
                    if ParseCSV.ExcerptFlag.ZERO_MARGIN in annotation['flags']:
                        indentLevel = 0

                    with a.p(Class = f"indent-{indentLevel}"):
                        if not indentLevel and not ParseCSV.ExcerptFlag.ZERO_MARGIN in annotation['flags']:
                            a(f"[{Html.Tag('span',{'class':'session-excerpt-header'})('Session')}]")
                        a(localFormatter.FormatAnnotation(x,annotation,tagsAlreadyPrinted))
                    tagsAlreadyPrinted.update(annotation.get("tags",()))
            
            if self.excerptAttributeSource:
                with a.p(Class="x-cite"):
                    a(Database.ItemCitation(x))

            if x is not lastExcerpt:
                a.hr()
            
        return str(a)

def MultiPageExcerptList(basePage: Html.PageDesc,excerpts: List[dict],formatter: Formatter,itemLimit:int = 0) -> Iterator[Html.PageAugmentorType]:
    """Split an excerpt list into multiple pages, yielding a series of PageAugmentorType objects
        basePage: Content of the page above the menu and excerpt list. Later pages add "-N" to the file name.
        excerpts, formatter: As in HtmlExcerptList
        itemLimit: Limit lists to roughly this many items, but break pages only at session boundaries."""

    pageNumber = 1
    menuItems = []
    excerptsInThisPage = []
    prevSession = None
    if itemLimit == 0:
        itemLimit = gOptions.excerptsPerPage
    
    def PageHtml() -> Html.PageAugmentorType:
        if pageNumber > 1:
            fileName = Utils.AppendToFilename(basePage.info.file,f"-{pageNumber}")
        else:
            fileName = basePage.info.file
        menuItem = Html.PageInfo(str(pageNumber),fileName,basePage.info.titleInBody)
        if gOptions.buildOnlyFirstPage and pageNumber > 1:
            pageHtml = ""
        else:
            pageHtml = formatter.HtmlExcerptList(excerptsInThisPage)

        return menuItem,(basePage.info._replace(file=fileName),pageHtml)

    for x in Database.RemoveFragments(excerpts):
        thisSession = (x["event"],x["sessionNumber"])
        if prevSession != thisSession:
            if itemLimit and len(excerptsInThisPage) >= itemLimit:
                menuItems.append(PageHtml())
                pageNumber += 1
                excerptsInThisPage = []

        excerptsInThisPage.append(x)
        prevSession = thisSession
    
    if excerptsInThisPage or not menuItems:
        menuItems.append(PageHtml())

    if len(menuItems) > 1:
        # Figure out which section in page contains the Menu object and copy it to the end of the page
        menuSection = basePage.numberedSections # The Menu object will be placed in the next available numbered section
        if not basePage.section[menuSection - 1]:
            menuSection -= 1 # unless the last section is blank.
        
        for page in basePage.AddMenuAndYieldPages(menuItems,wrapper=Html.Wrapper('<p class="page-list">Page: &emsp; ',"</p>\n"),highlight={"class":"active"}):
            page.AppendContent("<hr>")
            bottomMenu = copy.deepcopy(basePage.section[menuSection])
            bottomMenu.menu_keepScroll = False
            page.AppendContent(bottomMenu) # Duplicate the page menu at the bottom of the page
            yield page
            if gOptions.buildOnlyFirstPage:
                return
    else:
        clone = basePage.Clone()
        clone.AppendContent(menuItems[0][1][1])
        yield clone

def ShowDuration(page: Html.PageDesc,filteredExcerpts: list[dict]) -> None:
    durationStr = ExcerptDurationStr(filteredExcerpts,countSessionExcerpts=True,sessionExcerptDuration=False)
    page.AppendContent(Html.Tag("p")(durationStr))

def AddSearchCategory(category: str) -> Callable[[Html.PageDesc,list[dict]],None]:
    """Return a function that customizes a PageDesc object by adding a search category (e.g. Stories)"""
    def _AddSearchCategory(page: Html.PageDesc,_: list[dict],newCategory = category):
        if newCategory:
            page.keywords.append(newCategory)
        page.specialJoinChar["citationTitle"] = " "
        page.AppendContent(f"({newCategory})",section="citationTitle")


    return _AddSearchCategory

def FilteredExcerptsMenuItem(excerpts:Iterable[dict], filter:Filter.Filter, formatter:Formatter, mainPageInfo:Html.PageInfo, menuTitle:str, fileExt:str = "", pageAugmentor:Callable[[Html.PageDesc,list[dict]],None] = lambda page,excerpts:None) -> Html.PageDescriptorMenuItem:
    """Describes a menu item generated by applying a filter to a list of excerpts.
    excerpts: an iterable of the excerpts.
    filter: the filter to apply.
    formatter: the formatter object to pass to HtmlExcerptList.
    mainPageInfo: description of the main page
    menuTitle: the title in the menu.
    fileExt: the extension to add to the main page file for the filtered page.
    pageAugmentor: a function which modifies the base page """
    filteredExcerpts = list(filter.Apply(excerpts))

    if not filteredExcerpts:
        return []

    if fileExt:
        pageInfo = mainPageInfo._replace(file = Utils.AppendToFilename(mainPageInfo.file,"-" + fileExt))
    else:
        pageInfo = mainPageInfo
    menuItem = pageInfo._replace(title=f"{menuTitle} ({Database.CountExcerpts(filteredExcerpts,countSessionExcerpts=True)})")


    blankPage = Html.PageDesc(pageInfo)
    pageAugmentor(blankPage,filteredExcerpts)

    return itertools.chain([menuItem],MultiPageExcerptList(blankPage,filteredExcerpts,formatter))

def FilteredEventsMenuItem(filter:Filter.Filter, mainPageInfo:Html.PageInfo, fileExt: str = "") -> Html.PageDescriptorMenuItem:
    """Describes a menu item generated by applying a filter to the events and sessions in the database.
    filter: the filter to apply.
    mainPageInfo: description of the main page.
    menutitle: the title in the menu.
    fileExt: the extension to add to the main page file for the filtered page."""

    filteredEvents = list(filter.Apply(gDatabase["event"].values()))

    filteredSessions = Filter.And(filter,Filter.Event(e["code"] for e in filteredEvents).Not())(gDatabase["sessions"])
    filteredSessions = [s for s in filteredSessions if s["sessionTitle"]]
        # Find titled sessions not in these events that match filter

    if not filteredEvents and not filteredSessions:
        return []

    htmlBits = []
    if filteredEvents:
        if len(filteredEvents) <= 3 and not filteredSessions: # Provide full details if there are few events
            htmlBits.append(ListDetailedEvents(filteredEvents,showTags=False))
        else:
            if filteredSessions:
                htmlBits.append(Html.Tag("h3")(f"Events ({len(filteredEvents)})"))
            eventList = "\n".join(EventDescription(e,showMonth=True,excerptCount=False) for e in filteredEvents)
            htmlBits.append(Html.Tag("div",{"class":"listing"})(eventList))

    if filteredSessions:
        fromOtherEvents = ""
        if filteredEvents:
            htmlBits.append("<br>\n")
            fromOtherEvents = " from other events"
        htmlBits.append(Html.Tag("h3")(f"Sessions{fromOtherEvents} ({len(filteredSessions)})"))

        sessionLinks = []
        for s in filteredSessions:
            titleLink = Html.Tag("a",{"href":Database.EventLink(s["event"],s["sessionNumber"])})(str(s['sessionTitle']))
            titleLink += f' – {Utils.ReformatDate(s["date"])}'
            htmlBits.append(Html.Tag("p")(titleLink))
        sessionList = "\n".join(sessionLinks)
        htmlBits.append(Html.Tag("div",{"class":"listing"})(sessionList))

    if fileExt:
        pageInfo = mainPageInfo._replace(file = Utils.AppendToFilename(mainPageInfo.file,"-" + fileExt))
    else:
        pageInfo = mainPageInfo

    menuItem = pageInfo._replace(title=(f"Events ({len(filteredEvents)})" if filteredEvents else f"Sessions ({len(filteredSessions)})"))

    return menuItem,"".join(htmlBits)

def AllExcerpts(pageDir: str) -> Html.PageDescriptorMenuItem:
    """Generate a single page containing all excerpts."""

    pageInfo = Html.PageInfo("All excerpts",Utils.PosixJoin(pageDir,"AllExcerpts.html"))
    yield pageInfo

    formatter = Formatter()
    formatter.headingShowSessionTitle = True
    formatter.excerptOmitSessionTags = False
    formatter.headingShowTags = False
    formatter.headingShowTeacher = False

    def SimpleDuration(page: Html.PageDesc,excerpts: list[dict]):
        "Append the number of excerpts and duration to page."
        durationStr = ExcerptDurationStr(excerpts,countEvents=False,countSessions=False,sessionExcerptDuration=False)
        page.AppendContent(Html.Tag("p")(durationStr))

    def FilteredItem(filter:Filter.Filter,name:str) -> Html.PageDescriptorMenuItem:
        newTitle = "All " + name.lower()
        singular = Utils.Singular(name).lower()
        
        return FilteredExcerptsMenuItem(excerpts,filter,formatter,pageInfo._replace(title=newTitle),name,singular,pageAugmentor= lambda p,x: MostCommonTags(p,x,filter,name))

    def MostCommonTags(page: Html.PageDesc,excerpts: list[dict],filter:Filter.Filter = Filter.PassAll, kind: str = "") -> None:
        "Append a list of the most common tags to the beginning of each section"
        ShowDuration(page,excerpts)
        if len(excerpts) < gOptions.minSubsearchExcerpts * 3:
            return
        if kind not in {"","Questions","Stories","Quotes","Readings","Texts","References"}:
            return
        
        tagCount = Counter()
        for x in excerpts:
            tags = set()
            if kind == "Questions":
                tags.update(x["tags"][0:x["qTagCount"]])
            else:
                for item in Filter.AllSingularItems(x):
                    if filter.Match(item):
                        tags.update(item.get("tags",()))
            
            for tag in tags:
                tagCount[tag] += 1
        
        commonTags = sorted(((count,tag) for tag,count in tagCount.items()),key=lambda item:(-item[0],item[1]))
        
        a = Airium()
        with a.p():
            with a.span(style="text-decoration: underline;"):
                a(f"Most common {'topics' if kind else 'tags'}:")
            a.br()
            for count,tag in commonTags[:10]:
                pageToLink = f"tags/{gDatabase['tag'][tag]['htmlFile']}"

                # Link to subpages only if there are enough excerpts that we have generated them
                if gDatabase["tag"][tag]["excerptCount"] >= gOptions.minSubsearchExcerpts:
                    if kind == "Questions":
                        pageToLink = Utils.AppendToFilename(pageToLink,"-qtag")
                    elif kind:
                        pageToLink = Utils.AppendToFilename(pageToLink,"-" + Utils.Singular(kind).lower())

                with a.a(href = f"../{pageToLink}"):
                    a(tag)
                a(f" ({count})&emsp; ")

        page.AppendContent(str(a))

    excerpts = gDatabase["excerpts"]
    filterMenu = [
        FilteredExcerptsMenuItem(excerpts,Filter.PassAll,formatter,pageInfo,"All excerpts",pageAugmentor=MostCommonTags),
        FilteredExcerptsMenuItem(excerpts,Filter.FTag(Filter.All),formatter,
                                 Html.PageInfo("Featured",Utils.PosixJoin(pageDir,"AllExcerpts.html"),"All featured excerpts"),
                                 "Featured","featured",pageAugmentor=SimpleDuration),
        FilteredItem(Filter.Category("Questions"),"Questions"),
        FilteredItem(Filter.Category("Stories"),"Stories"),
        FilteredItem(Filter.Category("Quotes"),"Quotes"),
        FilteredItem(Filter.Category("Meditations"),"Meditations"),
        FilteredItem(Filter.Category("Teachings"),"Teachings"),
        FilteredItem(Filter.Category("Readings"),"Readings"),
        FilteredItem(Filter.Kind({"Sutta","Vinaya","Commentary"}),"Texts"),
        FilteredItem(Filter.Kind("Reference"),"References")
    ]

    filterMenu = [f for f in filterMenu if f] # Remove blank menu items

    basePage = Html.PageDesc(pageInfo)
    basePage.AppendContent(HtmlIcon("All.png"),section="titleIcon")
    pageIterator = basePage.AddMenuAndYieldPages(filterMenu,**LONG_SUBMENU_STYLE)
    if gOptions.skipSubsearchPages:
        pageIterator = Utils.SingleItemIterator(pageIterator,0)
    yield from pageIterator

def ListDetailedEvents(events: Iterable[dict],showTags = True) -> str:
    """Generate html containing a detailed list of all events."""
    
    a = Airium()
    
    firstEvent = True
    for e in events:
        eventCode = e["code"]
        if not firstEvent:
            a.hr()
        firstEvent = False
        with a.h3():
            with a.a(href = Database.EventLink(eventCode)):
                a(e["title"])            
        with a.p():
            a(f'{ListLinkedTeachers(e["teachers"],lastJoinStr = " and ",capitalize = True)}')
            a.br()
            if showTags and e["tags"]:
                bits = list(f"[{HtmlTagLink(t)}]" for t in e["tags"])
                a(" ".join(bits))
                a.br()
            a(EventSeriesAndDateStr(e))
            a.br()
            venueStr = EventVenueStr(e)
            if venueStr:
                a(venueStr)
                a.br()
            eventExcerpts = [x for x in gDatabase["excerpts"] if x["event"] == eventCode]
            a(ExcerptDurationStr(eventExcerpts))
                
    return str(a)

def EventDescription(event: dict,showMonth = False,excerptCount = True) -> str:
    href = Html.Wrapper(f"<a href = {Database.EventLink(event['code'])}>","</a>")
    if showMonth:
        startDate = Utils.ParseDate(event["startDate"])
        monthStr = f'{startDate.strftime("%B")} {int(startDate.year)}'
        if event["endDate"]:
            endDate = Utils.ParseDate(event["endDate"])
            endMonthStr = f'{endDate.strftime("%B")} {int(endDate.year)}'
            if endMonthStr != monthStr:
                if startDate.year == endDate.year:
                    monthStr = f'{startDate.strftime("%B")} to {endMonthStr}'
                else:
                    monthStr = f'{monthStr} to {endMonthStr}'
        monthStr = ' – ' + monthStr

    else:
        monthStr = ""
    excerptCountStr = f"({event['excerpts']})" if excerptCount else ""
    return f"<p>{href.Wrap(event['title'])} {excerptCountStr}{monthStr}</p>"

def ListEventsBySubject(events: list[dict]) -> str:
    """Return html code listing these events by series."""
    
    eventsByTag:dict[str,list[str]] = defaultdict(list) # tag:list[event["code"]]
    for e in events:
        for tags in e["tags"]:
            eventsByTag[tags].append(e["code"])

    # Combine tags with identical event lists
    tagsByEvent:dict[tuple[str],list[str]] = defaultdict(list) # tuple[event codes]:list[tag]
    for tags,eventList in eventsByTag.items():
        tagsByEvent[tuple(eventList)].append(tags)

    # Switch keys and values
    eventsByMultiTags = {tuple(tags):eventList for eventList,tags in tagsByEvent.items()}

    def TagOrderKey(tagList: tuple[str]) -> tuple[int,int]:
        "Sort the tag groups by decreasing event frequency and by index in the tag list"
        return (-len(eventsByMultiTags[tagList]),gDatabase["tag"][tagList[0]]["listIndex"])

    eventListByTags:list[tuple[tuple[str],str]] = []
    for tags in sorted(eventsByMultiTags,key=TagOrderKey):
        for e in eventsByMultiTags[tags]:
            listItem = (ListLinkedTags("",tags,lastJoinStr = " and "),
                        Html.Tag("p")(Database.ItemCitation(gDatabase["event"][e])),
                        "-".join(tags),
                        (" and ".join(tags) if len(tags) <= 2 else tags[0] + ", etc.").replace(" ","&nbsp;"))
            eventListByTags.append(listItem)
            
    
    return str(Html.ListWithHeadings(eventListByTags,lambda t:t,countItems=False))

def ListEventsBySeries(events: list[dict]) -> str:
    """Return html code listing these events by series."""

    prevSeries = None
    seriesList = list(gDatabase["series"])

    def SeriesIndex(eventWithSeries: tuple[str,dict[str]]) -> int:
        "Return the index of the series of this event for sorting purposes"
        return seriesList.index(eventWithSeries[0])
    
    def LinkToAboutSeries(eventWithSeries: tuple[str,dict[str]]) -> tuple[str,str,str]:
        htmlHeading = eventWithSeries[0]
        
        nonlocal prevSeries
        description = ""
        if eventWithSeries[0] != prevSeries:
            description = gDatabase["series"][eventWithSeries[0]]["description"]
            if description:
                description = Html.Tag("p",{"class":"smaller"})(description)
            prevSeries = eventWithSeries[0]
            
        return htmlHeading,description + EventDescription(eventWithSeries[1],showMonth=True),eventWithSeries[0]

    eventsWithSeries: list[tuple[str,dict[str]]] = []
    for e in events:
        for s in e["series"]:
            eventsWithSeries.append((s,e))
    eventsWithSeries = sorted(eventsWithSeries,key=SeriesIndex)
    return str(Html.ListWithHeadings(eventsWithSeries,LinkToAboutSeries))

def ListEventsByYear(events: list[dict]) -> str:
    """Return html code listing these events by series."""
    
    return str(Html.ListWithHeadings(events,lambda e: (str(Utils.ParseDate(e["startDate"]).year),EventDescription(e)),countItems=False))

def EventsMenu(indexDir: str) -> Html.PageDescriptorMenuItem:
    """Create the Events menu item and its associated submenus."""

    subjectInfo = Html.PageInfo("By subject",Utils.PosixJoin(indexDir,"EventsBySubject.html"),"Events – By subject")
    seriesInfo = Html.PageInfo("Series",Utils.PosixJoin(indexDir,"EventsBySeries.html"),"Events – By series")
    chronologicalInfo = Html.PageInfo("Chronological",Utils.PosixJoin(indexDir,"EventsChronological.html"),"Events – Chronological")
    detailInfo = Html.PageInfo("Detailed",Utils.PosixJoin(indexDir,"EventDetails.html"),"Events – Detailed view")

    yield subjectInfo._replace(title="Events")

    listing = Html.Tag("div",{"class":"listing"})
    eventMenu = [
        [seriesInfo,listing(ListEventsBySeries(gDatabase["event"].values()))],
        [subjectInfo,listing(ListEventsBySubject(gDatabase["event"].values()))],
        [chronologicalInfo,listing(ListEventsByYear(gDatabase["event"].values()))],
        [detailInfo,listing(ListDetailedEvents(gDatabase["event"].values()))],
        [Html.PageInfo("About event series","about/Event-series.html")],
        EventPages("events")
    ]

    basePage = Html.PageDesc()
    basePage.AppendContent("calendar",section="titleIcon")
    for page in basePage.AddMenuAndYieldPages(eventMenu,**SUBMENU_STYLE):
        if page.info.titleInBody.startswith("Events – "):
            _,subSection = page.info.titleInBody.split(" – ")
            page.AppendContent(f"Events: {subSection}",section="citationTitle")
            page.keywords = ["Events",subSection]
        yield page

def LinkToPeoplePages(page: Html.PageDesc) -> Html.PageDesc:
    "Add links to corresponding teacher, tag, and author pages of this page."

    directory = Utils.PosixSplit(page.info.file)[0]
    outputLinks = []

    teacher = Database.TeacherLookup(page.info.title)
    if teacher:
        link = TeacherLink(teacher)
        if link and directory != "teachers":
            outputLinks.append(Html.Tag("a",{"href":link})(f'→ Teachings by {gDatabase["teacher"][teacher]["attributionName"]}'))
        
        link = BuildReferences.ReferenceLink("author",teacher)
        if link and directory != "books":
            outputLinks.append(Html.Tag("a",{"href":link})(f'→ Books by {gDatabase["teacher"][teacher]["attributionName"]}'))
        
    tag = Database.TagLookup(page.info.title)
    if tag and directory != "tags":
        outputLinks.append(HtmlTagLink(tag,text = f'→ Tag [{tag}]'))

    if outputLinks:
        page.AppendContent("&emsp;".join(outputLinks),"smallTitle")
    return page


def TagSubsearchPages(tags: str|Iterable[str],tagExcerpts: list[dict],basePage: Html.PageDesc,cluster:str = "") -> Iterator[Html.PageAugmentorType]:
    """Generate a list of pages obtained by running a series of tag subsearches.
    tags: The tag or tags to search for.
    tagExcerpts: The excerpts to search. Should already have passed Filter.Tag(tags).
    basePage: The base page to append our pages to.
    cluster: The tag cluster represented by tags."""

    def FilteredTagMenuItem(excerpts: Iterable[dict],filter: Filter.Filter,menuTitle: str,fileExt:str = "") -> Html.PageDescriptorMenuItem:
        if not fileExt:
            fileExt = Utils.Singular(menuTitle).lower()
        
        return FilteredExcerptsMenuItem(excerpts=excerpts,filter=filter,formatter=formatter,mainPageInfo=basePage.info,menuTitle=menuTitle,fileExt=fileExt,pageAugmentor=AddSearchCategory(menuTitle))

    def HoistFTags(pageGenerator: Html.PageDescriptorMenuItem,excerpts: Iterable[dict],tags: list[str],skipSections:int = 0):
        """Insert featured excerpts at the top of the first page.
        skipSections allows inserting the featured excerpts between blocks of text."""
        
        menuItemAndPages = iter(pageGenerator)
        firstPage = next(menuItemAndPages,None)
        if not firstPage:
            return []
        if type(firstPage) == Html.PageInfo:
            yield firstPage # First yield the menu item descriptor, if any
            firstPage = next(menuItemAndPages)

        if cluster:
            featuredExcerpts = Filter.ClusterFTag(cluster).Apply(excerpts)
        else:
            featuredExcerpts = Filter.FTag(tags).Apply(excerpts)
        featuredExcerpts = list(Database.RemoveFragments(featuredExcerpts))
        if featuredExcerpts:
            featuredExcerpts.sort(key = lambda x: Database.FTagOrder(x,tags))

            headerHtml = []
            headerStr = "Featured excerpt"
            if len(featuredExcerpts) > 1:
                headerStr += f's ({len(featuredExcerpts)}) — Play all <button id="playFeatured"></button>'
            headerHtml.append('<div class="featured">' + Html.Tag("div",{"class":"title","id":"featured"})(headerStr))

            featuredFormatter = copy.copy(formatter)
            featuredFormatter.SetHeaderlessFormat()
            featuredFormatter.excerptShowFragmentPlayers = False
            if gOptions.draftFTags == "number":
                featuredFormatter.showFTagOrder = tags

            headerHtml.append(featuredFormatter.HtmlExcerptList(featuredExcerpts))
            headerHtml.append("</div>\n<hr>\n")

            firstTextSection = 0 # The first section could be a menu, in which case we skip it
            while type(firstPage.section[firstTextSection]) != str:
                firstTextSection += 1
            firstTextSection += skipSections

            if firstTextSection in firstPage.section:
                firstPage.section[firstTextSection] = "\n".join(headerHtml + [firstPage.section[firstTextSection]])
            else:
                firstPage.AppendContent("\n".join(headerHtml))
                                                            
        yield firstPage
        yield from menuItemAndPages

    formatter = Formatter()
    formatter.excerptBoldTags = Filter.FrozenSet(tags)
    formatter.headingShowTags = False
    formatter.excerptOmitSessionTags = False
    formatter.headingShowTeacher = False

    if type(tags) == str:
        tags = [tags]

    if len(tagExcerpts) >= gOptions.minSubsearchExcerpts:
        questions = Filter.Category("Questions")(tagExcerpts)
        qTags,aTags = Filter.QTag(tags).Partition(questions)
        mostRelevant = Filter.MostRelevant(tags)(tagExcerpts)

        filterMenu = [
            FilteredEventsMenuItem(Filter.Tag(tags),basePage.info,"events"),
            HoistFTags(FilteredExcerptsMenuItem(tagExcerpts,Filter.PassAll,formatter,basePage.info,"All excerpts"),tagExcerpts,tags),
            HoistFTags(FilteredTagMenuItem(mostRelevant,Filter.PassAll,"Most relevant","relevant"),mostRelevant,tags),
            FilteredTagMenuItem(qTags,Filter.PassAll,"Questions about","qtag"),
            FilteredTagMenuItem(aTags,Filter.PassAll,"Answers involving","atag"),
            FilteredTagMenuItem(tagExcerpts,Filter.SingleItemMatch(Filter.Tag(tags),Filter.Category("Stories")),"Stories"),
            FilteredTagMenuItem(tagExcerpts,Filter.SingleItemMatch(Filter.Tag(tags),Filter.Category("Quotes")),"Quotes"),
            FilteredTagMenuItem(tagExcerpts,Filter.SingleItemMatch(Filter.Tag(tags),Filter.Category("Readings")),"Readings"),
            FilteredTagMenuItem(tagExcerpts,Filter.SingleItemMatch(Filter.Tag(tags),Filter.Kind({"Sutta","Vinaya","Commentary"})),"Texts"),
            FilteredTagMenuItem(tagExcerpts,Filter.SingleItemMatch(Filter.Tag(tags),Filter.Kind("Reference")),"References")
        ]

        hasEventsPage = bool(filterMenu[0])
        filterMenu = [f for f in filterMenu if f] # Remove blank menu items
        if len(filterMenu) > 1:
            pageIterator = basePage.AddMenuAndYieldPages(filterMenu,**EXTRA_MENU_STYLE)
            if gOptions.skipSubsearchPages: # Write only the main page if this is the case
                pageIterator = Utils.SingleItemIterator(pageIterator,1 if hasEventsPage else 0)
            yield from map(LinkToPeoplePages,pageIterator)
            return
    
    basePage.AppendContent("",newSection=True)
    yield from map(LinkToPeoplePages,HoistFTags(MultiPageExcerptList(basePage,tagExcerpts,formatter),tagExcerpts,tags,skipSections=1))

def TagBreadCrumbs(tagInfo: dict) -> tuple[str,list[str]]:
    "Return a hyperlinked string of the form: 'grandparent / parent / tag'"
    
    tagHierarchy = gDatabase["tagDisplayList"]
    listIndex = tagInfo["listIndex"]
    prevLevel = tagHierarchy[listIndex]["level"]
    
    parents = []
    while (listIndex >= 0 and prevLevel > 1):
        currentLevel = tagHierarchy[listIndex]["level"]
        if currentLevel < prevLevel:
            thisItem = tagHierarchy[listIndex]
            parents.append(HtmlTagLink(thisItem["tag"] or thisItem["virtualTag"],fullTag = True))
            """if thisItem["tag"]:
                parents.append(HtmlTagLink(thisItem["tag"],fullTag = True)) #TagDescription(gDatabase["tag"][thisItem["tag"]],listAs=thisItem["name"],fullTag=True,flags=TagDescriptionFlag.NO_COUNT + TagDescriptionFlag.NO_PALI))
            elif thisItem["name"] in gDatabase["tagSubsumed"]:
                parents.append(HtmlTagLink(thisItem["name"]),fullTag = True)
            else:
                parents.append(thisItem["name"])"""
            prevLevel = currentLevel
        listIndex -= 1
    
    parents.reverse()
    return " / ".join(parents + [tagInfo["fullTag"]]) + "&nbsp; " + DrilldownIconLink(tagInfo["tag"],iconWidth = 16) + "\n<br>\n"


def TagPages(tagPageDir: str) -> Iterator[Html.PageAugmentorType]:
    """Write a html file for each tag in the database"""
    
    if gOptions.buildOnlyIndexes or not "tags" in gOptions.buildOnly:
        return
    
    def SubsumedTagDescription(tagData:dict) -> str:
        """Return a string describing this subsumed tag."""
        additionalBits = []
        if tagData["fullPali"]:
            additionalBits.append(tagData["fullPali"])
        additionalBits += tagData["alternateTranslations"]
        additionalBits += tagData["glosses"]
        if additionalBits:
            return tagData["fullTag"] + f" ({', '.join(additionalBits)})"
        else:
            return tagData["fullTag"]

    subsumesTags = Database.SubsumesTags()
    for tag,tagInfo in gDatabase["tag"].items():
        if not tagInfo["htmlFile"]:
            continue

        relevantExcerpts = Filter.Tag(tag)(gDatabase["excerpts"])

        a = Airium()
        
        with a.strong():
            a(TagBreadCrumbs(tagInfo))
            for subtopic in gDatabase["tag"][tag].get("partOfSubtopics",()):
                if len(gDatabase["subtopic"][subtopic]["subtags"]) > 0:
                    a(f"Part of tag cluster {HtmlSubtopicLink(subtopic)} in key topic {HtmlKeyTopicLink(gDatabase['subtopic'][subtopic]['topicCode'])}")
                else:
                    a(f"Part of key topic {HtmlKeyTopicLink(gDatabase['subtopic'][subtopic]['topicCode'])}")
                a.br()
            if tag in subsumesTags:
                a(TitledList("Subsumes",[SubsumedTagDescription(t) for t in subsumesTags[tag]],plural=""))
            a(TitledList("Alternative translations",tagInfo['alternateTranslations'],plural = ""))
            if ProperNounTag(tagInfo):
                a(TitledList("Other names",[RemoveLanguageTag(name) for name in tagInfo['glosses']],plural = ""))
            else:
                a(TitledList("Glosses",tagInfo['glosses'],plural = ""))
            mainParent = Database.ParentTagListEntry(tagInfo["listIndex"])
            mainParent = mainParent and (mainParent["tag"] or mainParent["virtualTag"]) # Prevent error if mainParent == None
            a(ListLinkedTags("Also a subtag of",
                             (t for t in tagInfo['supertags'] if Database.TagLookup(t) != mainParent),
                             plural="",lastJoinStr=" and ",titleEnd=" "))
            subsumedTags = [t["tag"] for t in subsumesTags.get(tag,())]
            a(ListLinkedTags("Subtag",[t for t in tagInfo['subtags'] if t not in subsumedTags]))
            a(ListLinkedTags("See also",tagInfo['related'],plural = ""))
            a(ExcerptDurationStr(relevantExcerpts,countEvents=False,countSessions=False))
        
        if "note" in tagInfo:
            with a.p():
                a(tagInfo["note"])
        
        # Truncate lines in the header, then add the rest of the page
        header = str(a)
        headerChars = Html.CountChars(header,firstNLines=2)
        header = Html.TruncateHtmlText(str(a),alwaysShow = 2 if headerChars < 120 else 1,
                                       morePrompt="details",hideWidth=1)
        a = Airium()
        a(header)
        a.hr()
        
        tagWithoutHtml = Utils.RemoveHtmlTags(tagInfo["fullTag"])
        tagPlusPali = TagDescription(tagInfo,fullTag=True,flags=TagDescriptionFlag.NO_COUNT,link = False)
        pageInfo = Html.PageInfo(tag,Utils.PosixJoin(tagPageDir,tagInfo["htmlFile"]),tagPlusPali)
        basePage = Html.PageDesc(pageInfo)
        basePage.AppendContent(HtmlIcon("tag"),section="titleIcon")
        basePage.AppendContent(str(a))
        basePage.keywords = ["Tag",tagWithoutHtml]
        if tagInfo["fullPali"]:
            basePage.keywords.append(Utils.RemoveHtmlTags(tagInfo["fullPali"]))
        basePage.AppendContent(f"Tag: {tagWithoutHtml}",section="citationTitle")

        yield from TagSubsearchPages(tag,relevantExcerpts,basePage)


def TeacherPages(teacherPageDir: str) -> Html.PageDescriptorMenuItem:
    """Yield a page for each individual teacher"""
    
    if gOptions.buildOnlyIndexes:
        return
    xDB = gDatabase["excerpts"]
    teacherDB = gDatabase["teacher"]

    for t,tInfo in teacherDB.items():
        if not tInfo["htmlFile"]:
            continue

        relevantExcerpts = Filter.Teacher(t)(xDB)
    
        a = Airium()
        
        excerptInfo = ExcerptDurationStr(relevantExcerpts,countEvents=False,countSessions=False,countSessionExcerpts=True)
        a(excerptInfo)
        a.hr()

        formatter = Formatter()
        formatter.headingShowTags = False
        formatter.headingShowTeacher = False
        formatter.excerptOmitSessionTags = False
        formatter.excerptDefaultTeacher = set([t])

        pageInfo = Html.PageInfo(tInfo["fullName"],Utils.PosixJoin(teacherPageDir,tInfo["htmlFile"]))
        basePage = Html.PageDesc(pageInfo)
        basePage.AppendContent(str(a))
        basePage.AppendContent(f"Teacher: {tInfo['fullName']}",section="citationTitle")
        basePage.keywords = ["Teacher",tInfo["fullName"]]

        def FilteredTeacherMenuItem(excerpts: Iterable[dict],filter: Filter.Filter,menuTitle: str,fileExt:str = "") -> Html.PageDescriptorMenuItem:
            if not fileExt:
                fileExt = Utils.Singular(menuTitle).lower()
            
            return FilteredExcerptsMenuItem(excerpts=excerpts,filter=filter,formatter=formatter,mainPageInfo=pageInfo,menuTitle=menuTitle,fileExt=fileExt,pageAugmentor=AddSearchCategory(menuTitle))


        if len(relevantExcerpts) >= gOptions.minSubsearchExcerpts:

            filterMenu = [
                FilteredExcerptsMenuItem(relevantExcerpts,Filter.PassAll,formatter,pageInfo,"All excerpts"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.FTag(Filter.All),"Featured"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t),Filter.Category("Questions")),"Questions"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t),Filter.Category("Stories")),"Stories"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t),Filter.Kind("Quote")),"Direct quotes","d-quote"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t,quotedBy=False),Filter.Kind("Indirect quote")),"Quotes others","i-quote"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t,quotesOthers=False),Filter.Kind("Indirect quote")),"Quoted by others","quoted-by"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t),Filter.Category("Meditations")),"Meditations"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t),Filter.Category("Teachings")),"Teachings"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t),Filter.Category("Readings")),"Readings from","read-from"),
                FilteredTeacherMenuItem(relevantExcerpts,Filter.SingleItemMatch(Filter.Teacher(t),Filter.Kind("Read by")),"Readings by","read-by")
            ]

            filterMenu = [f for f in filterMenu if f] # Remove blank menu items
            pageIterator = basePage.AddMenuAndYieldPages(filterMenu,**EXTRA_MENU_STYLE)
            if gOptions.skipSubsearchPages:
                pageIterator = Utils.SingleItemIterator(pageIterator,0)
            yield from map(LinkToPeoplePages,pageIterator)
        else:
            yield from map(LinkToPeoplePages,MultiPageExcerptList(basePage,relevantExcerpts,formatter))

def TeacherDescription(teacher: dict,nameStr: str = "") -> str:
    href = Html.Tag("a",{"href":TeacherLink(teacher['teacher'])})
    if not nameStr:
        nameStr = teacher['fullName']
    return f"<p> {href.Wrap(nameStr)} ({teacher['excerptCount']}) </p>"

def AlphabetizedTeachers(teachers: list[dict]) -> list[str,dict]:
    """Sort these teachers alphabetically by name. Return a list of tuples (alphabetizedName,teacherDict)"""
    
    prefixes = sorted(list(p for p in gDatabase["prefix"] if not p.endswith("/")),key=len,reverse=True)
        # Sort prefixes so the longest prefix matches first, and eliminate prefixes ending in / which don't apply to names
    prefixRegex = Utils.RegexMatchAny(prefixes,capturingGroup=True) + r" (.+)"
    
    noAlphabetize = {"alphabetize":""}
    def AlphabetizeName(string: str) -> str:
        if gDatabase["name"].get(string,noAlphabetize)["alphabetize"]:
            return gDatabase["name"][string]["alphabetize"]
        match = re.match(prefixRegex,string)
        if match:
            return match[2] + ", " + match[1]
        else:
            return string

    alphabetized = [(AlphabetizeName(t["fullName"]),t) for t in teachers]
    alphabetized.sort(key = lambda a:Utils.RemoveDiacritics(a[0]))
    return alphabetized

def ListTeachersAlphabetical(teachers: list[dict]) -> str:
    """Return html code listing teachers alphabetically."""
    return "\n".join(TeacherDescription(t,name) for name,t in AlphabetizedTeachers(teachers))

def TeacherDate(teacher:dict) -> float:
    "Return a teacher's date for sorting purposes."
    try:
        return float(gDatabase["name"][teacher["fullName"]]["sortBy"])
    except (KeyError,ValueError):
        return 9999

def ListTeachersChronological(teachers: list[dict]) -> str:
    """Return html code listing these teachers by group and chronologically."""
    
    teachersWithoutDate = [t["attributionName"] for t in teachers if TeacherDate(t) > 3000]
    if teachersWithoutDate:
        Alert.caution(len(teachersWithoutDate),"teacher(s) do not have dates and will be sorted last.")
        Alert.extra("Teachers without dates:",teachersWithoutDate)
    chronological = sorted(teachers,key=TeacherDate)

    groups = list(gDatabase["group"])
    groups.append("") # Prevent an error if group is blank
    chronological.sort(key=lambda t: groups.index(t["group"]))
    return str(Html.ListWithHeadings(chronological,lambda t: (t["group"],TeacherDescription(t)) ))

def ListTeachersLineage(teachers: list[dict]) -> str:
    """Return html code listing teachers by lineage."""
    
    lineages = list(gDatabase["lineage"])
    lineages.append("") # Prevent an error if group is blank
    hasLineage = [t for t in teachers if t["lineage"] and t["group"] == "Monastics"]
    hasLineage.sort(key=TeacherDate)
    hasLineage.sort(key=lambda t: lineages.index(t["lineage"]))
    return str(Html.ListWithHeadings(hasLineage,lambda t: (t["lineage"],TeacherDescription(t)) ))

def ListTeachersByExcerpts(teachers: list[dict]) -> str:
    """Return html code listing teachers by number of excerpts."""
    
    sortedByExcerpts = sorted(teachers,key=lambda t: t["excerptCount"],reverse=True)
    return "\n".join(TeacherDescription(t) for t in sortedByExcerpts)

def TeacherMenu(indexDir: str) -> Html.PageDescriptorMenuItem:
    """Create the Teacher menu item and its associated submenus."""

    alphabeticalInfo = Html.PageInfo("Alphabetical",Utils.PosixJoin(indexDir,"TeachersAlphabetical.html"),"Teachers – Alphabetical")
    chronologicalInfo = Html.PageInfo("Chronological",Utils.PosixJoin(indexDir,"TeachersChronological.html"),"Teachers – Chronological")
    lineageInfo = Html.PageInfo("Lineage",Utils.PosixJoin(indexDir,"TeachersLineage.html"),"Teachers – Monastics by lineage")
    excerptInfo = Html.PageInfo("Number of teachings",Utils.PosixJoin(indexDir,"TeachersByExcerpts.html"),"Teachers – By number of teachings")

    yield alphabeticalInfo._replace(title="Teachers")

    teachersInUse = [t for t in gDatabase["teacher"].values() if t["htmlFile"]]

    listing = Html.Tag("div",{"class":"listing"})
    teacherMenu = [
        [lineageInfo,listing(ListTeachersLineage(teachersInUse))],
        [excerptInfo,listing(ListTeachersByExcerpts(teachersInUse))],
        [alphabeticalInfo,listing(ListTeachersAlphabetical(teachersInUse))],
        [chronologicalInfo,listing(ListTeachersChronological(teachersInUse))],
        TeacherPages("teachers")
    ]

    basePage = Html.PageDesc()
    basePage.AppendContent(HtmlIcon("user"),section="titleIcon")
    for page in basePage.AddMenuAndYieldPages(teacherMenu,**SUBMENU_STYLE):
        if "Teachers" in page.info.file: # Index files use the plural icon
            page.section["titleIcon"] = HtmlIcon("users")
        if page.info.titleInBody.startswith("Teachers – "):
            _,subSection = page.info.titleInBody.split(" – ")
            page.AppendContent(f"Teachers: {subSection}",section="citationTitle")
            page.keywords = ["Teachers",subSection]
        yield page


def SearchMenu(searchDir: str) -> Html.PageDescriptorMenuItem:
    """Create the Search menu item and its associated submenus."""

    searchPageName = "Text-search.html"
    searchTemplate = Utils.PosixJoin(gOptions.pagesDir,"templates",searchPageName)
    searchPage = Utils.ReadFile(searchTemplate)
    
    pageInfo = Html.PageInfo("Search",Utils.PosixJoin(searchDir,searchPageName),titleIB="Search")
    yield pageInfo

    featuredPageName = "Featured.html"
    featuredExcerptPageInfo = Html.PageInfo("Daily featured excerpts",Utils.PosixJoin(searchDir,featuredPageName),titleIB="Featured excerpts")
    featuredPage = Utils.ReadFile(Utils.PosixJoin(gOptions.pagesDir,"templates",featuredPageName))

    searchMenu = [
        (pageInfo, searchPage),
        (featuredExcerptPageInfo,featuredPage)
    ]
    
    basePage = Html.PageDesc()
    for page in basePage.AddMenuAndYieldPages(searchMenu,**SUBMENU_STYLE):
        yield page


def AddTableOfContents(sessions: list[dict],a: Airium) -> None:
    """Add a table of contents to the event which is being built."""
    tocPath = Utils.PosixJoin(gOptions.documentationDir,"tableOfContents",sessions[0]["event"] + ".md")
    if os.path.isfile(tocPath):
        template = pyratemp.Template(Utils.ReadFile(tocPath))
        
        markdownText = template(gOptions = gOptions,gDatabase = gDatabase,Database = Database)

        def ApplyToMarkdownFile(transform: Callable[[str],Tuple[str,int]]) -> int:
            nonlocal markdownText
            markdownText,changeCount = transform(markdownText)
            return changeCount
        
        with Alert.extra.Supress():
            Render.LinkSubpages(ApplyToMarkdownFile)
            Render.LinkKnownReferences(ApplyToMarkdownFile)
            Render.LinkSuttas(ApplyToMarkdownFile)
        
        html = markdown.markdown(markdownText,extensions = ["sane_lists",NewTabRemoteExtension()])
        a.hr()
        with a.h2():
            a.a(href="#").i(Class="fa fa-plus-square toggle-view noscript-hide",id="TOC")
            a("Table of Contents")
        with a.div(Class="listing javascript-hide",id="TOC.b"):
            a(html)
        return

    if len(sessions) > 1:
        if all(s["sessionTitle"] for s in sessions):
            # If all sessions have a title, list sessions by title
            a.hr()
            with a.div(Class="listing"):
                lines = []
                for s in sessions:
                    titleLink = Html.Tag("a",{"href":f"#{Database.ItemCode(s)}"})(str(s['sessionTitle']))
                    lines.append(Html.Tag("p")(f"Session {s['sessionNumber']}: {titleLink}"))

                a(Html.TruncatedList(lines,alwaysShow=3,morePrompt="Show all sessions"))
        else:
            squish = Airium(source_minify = True) # Temporarily eliminate whitespace in html code to fix minor glitches
            squish("Sessions:")
            for s in sessions:
                squish(" &emsp;")
                with squish.a(href = f"#{Database.ItemCode(s)}"):
                    squish(str(s['sessionNumber']))
            
            a(str(squish))


def EventPages(eventPageDir: str) -> Iterator[Html.PageAugmentorType]:
    """Generate html for each event in the database"""
    if gOptions.buildOnlyIndexes:
        return

    for eventCode,eventInfo in gDatabase["event"].items():
        sessions = [s for s in gDatabase["sessions"] if s["event"] == eventCode]
        excerpts = [x for x in gDatabase["excerpts"] if x["event"] == eventCode]
        featuredExcerpts = Filter.FTag(Filter.All)(excerpts)
        a = Airium()
        
        with a.strong():
            a(ListLinkedTeachers(eventInfo["teachers"],lastJoinStr = " and ",capitalize = True))
        a.br()

        a(EventSeriesAndDateStr(eventInfo))
        a.br()
        
        venueInfo = EventVenueStr(eventInfo)
        if venueInfo:
            a(venueInfo)
            a.br()
        
        a(ExcerptDurationStr(excerpts))
        a.br()

        if featuredExcerpts:
            with a.a(href=SearchLink(f"@{eventCode} +")):
                a(f"Show featured excerpt{'s' if len(featuredExcerpts) > 1 else ''}")
            a(f"({len(featuredExcerpts)})")
            a.br()
        
        if eventInfo["description"]:
            with a.p(Class="smaller"):
                a(eventInfo["description"])
        
        if eventInfo["website"]:
            with a.a(href = eventInfo["website"],target="_blank"):
                a("External website")
            a.br()
        
        AddTableOfContents(sessions,a)
        
        a.hr()
        
        formatter = Formatter()
        formatter.headingShowEvent = False
        formatter.headingShowSessionTitle = True
        formatter.headingLinks = False
        formatter.headingAudio = True
        formatter.excerptPreferStartTime = True
        a(formatter.HtmlExcerptList(list(Database.RemoveFragments(excerpts))))
        
        titleInBody = eventInfo["title"]
        if eventInfo["subtitle"]:
            titleInBody += " – " + eventInfo["subtitle"]

        titleWithoutTags = Utils.RemoveHtmlTags(eventInfo["title"])
        page = Html.PageDesc(Html.PageInfo(titleWithoutTags,Utils.PosixJoin(eventPageDir,eventCode+'.html'),titleInBody))
        page.AppendContent(str(a))
        page.keywords = ["Event",titleWithoutTags]
        page.AppendContent(f"Event: {titleWithoutTags}",section="citationTitle")
        yield page
        
def ExtractHtmlBody(fileName: str) -> str:
    """Extract the body text from a html page"""
    
    htmlPage = Utils.ReadFile(fileName)
    
    bodyStart = re.search(r'<body[^>]*>',htmlPage)
    bodyEnd = re.search(r'</body',htmlPage)
    
    if not bodyStart:
        raise ValueError("Cannot find <body> tag in " + fileName)
    if not bodyEnd:
        raise ValueError("Cannot find </body> tag in " + fileName)
    
    return htmlPage[bodyStart.span()[1]:bodyEnd.span()[0]]

def DocumentationMenu(directory: str,makeMenu = True,
                      specialFirstItem:Html.PageInfo|None = None, menuTitle:str|None = None,
                      menuStyle: dict = {},
                      extraItems:Iterator[Iterator[Html.PageDescriptorMenuItem]] = []) -> Html.PageDescriptorMenuItem:
    """Read markdown pages from documentation/directory, convert them to html, 
    write them in pages/about, and create a menu out of them.
    specialFirstItem optionally designates the PageInfo for the first item.
    menuTitle is the title of this menu itself; it defaults to the first item."""

    @Alert.extra.Supress()
    def QuietRender() -> Iterator[Html.PageDesc]:
        return Document.RenderDocumentationFiles(directory,"about",html = True)

    aboutMenu = []
    for page in QuietRender():
        if makeMenu:
            if not aboutMenu:
                if specialFirstItem:
                    if not specialFirstItem.file:
                        specialFirstItem = specialFirstItem._replace(file=page.info.file)
                    page.info = specialFirstItem
                if menuTitle:
                    yield page.info._replace(title=menuTitle)
                else:
                    yield page.info
        page.keywords = ["About","Ajahn Pasanno","Question","Story","Archive"]
        citation = "About"
        if page.info.title != "About":
            page.keywords.append(page.info.title)
            citation += f": {page.info.title}"

        page.AppendContent(citation,section="citationTitle")
        page.AppendContent("text",section="titleIcon")
        aboutMenu.append([page.info,page])
        
    for item in extraItems:
        aboutMenu.append(item)

    if makeMenu:
        basePage = Html.PageDesc()
        yield from basePage.AddMenuAndYieldPages(aboutMenu,**menuStyle)
    else:
        yield from aboutMenu

def KeyTopicExcerptLists(indexDir: str, topicDir: str):
    """Yield one page for each key topic listing all featured excerpts."""
    if gOptions.buildOnlyIndexes or "topics" not in gOptions.buildOnly:
        return

    formatter = Formatter()
    formatter.SetHeaderlessFormat()

    topicList = list(gDatabase["keyTopic"])
    for topicNumber,topic in enumerate(gDatabase["keyTopic"].values()):
        info = Html.PageInfo(topic["topic"],Utils.PosixJoin(topicDir,topic["listFile"]),f"{topic['topic']}: Featured excerpts ({topic['fTagCount']})")
        page = Html.PageDesc(info)
        page.AppendContent(Utils.PosixJoin("topics",topic["code"] + ".png"),section="titleIcon")
        page.AppendContent("Featured excerpts about " + topic["topic"],section="citationTitle")
        page.keywords = ["Key topics",topic["topic"]]

        if topicNumber > 0:
            page.AppendContent(HtmlKeyTopicLink(topicList[topicNumber - 1],
                                                text=f"<< {gDatabase['keyTopic'][topicList[topicNumber - 1]]['topic']}") + "\n")
        if topicNumber < len(topicList) - 1:
            page.AppendContent(Html.Tag("span",{"class":"floating-menu"})(HtmlKeyTopicLink(topicList[topicNumber + 1],
                                                text=f"{gDatabase['keyTopic'][topicList[topicNumber + 1]]['topic']} >>" + "\n")))
        page.AppendContent("<br>")

        if topic["longNote"]:
            page.AppendContent("<br>\n" + topic["longNote"])
        page.AppendContent("<hr>\n")
        
        excerptsByTopic:dict[str:list[str]] = {}
        for cluster in topic["subtopics"]:
            def SortKey(x) -> int:
                return Database.FTagOrder(x,searchTags)

            searchTags = [cluster] + list(gDatabase["subtopic"][cluster]["subtags"].keys())
            excerptsByTopic[cluster] = sorted(Database.RemoveFragments(Filter.ClusterFTag(cluster).Apply(gDatabase["excerpts"])),key=SortKey)

        def FeaturedExcerptList(item: tuple[dict,str,bool,bool]) -> tuple[str,str,str,str]:
            excerpt,tag,firstExcerpt,lastExcerpt = item

            clusterInfo = gDatabase["subtopic"][tag]
            excerptHtml = ""

            if firstExcerpt:
                lines = []
                if clusterInfo["subtags"]:
                    lines.append("Cluster includes: " + HtmlSubtopicTagList(clusterInfo,summarize=5))
                relatedEvents = list(Filter.Tag([clusterInfo["tag"]] + list(clusterInfo["subtags"]))(gDatabase["event"].values()))
                if relatedEvents:
                    lines.append("Related events: " + ", ".join(Database.ItemCitation(e) for e in relatedEvents))

                if lines:
                    lines.append("")
                    excerptHtml += "<br>\n".join(lines)

            if gOptions.draftFTags == "number":
                formatter.showFTagOrder = list(Database.SubtagIterator(gDatabase["subtopic"][tag]))
            if excerpt:
                excerptHtml += formatter.HtmlExcerptList([excerpt])
            else:
                excerptHtml += Html.ITEM_NO_COUNT

            if excerpt and not lastExcerpt:
                excerptHtml += "\n<hr>"

            isCluster = bool(clusterInfo["subtags"])
            heading = HtmlIcon("Cluster.png") if isCluster else HtmlIcon("tag")
            heading += " "
            text = clusterInfo["displayAs"] if isCluster else tag
            heading += HtmlSubtopicLink(tag,text=text).replace(".html","-relevant.html")
            pali = clusterInfo["pali"]
            if not isCluster and clusterInfo["displayAs"] != tag:
                if pali:
                    heading = f"{clusterInfo['displayAs']} ({pali}) {heading}"
                else:
                    heading = f"{clusterInfo['displayAs']} {heading}"
            elif pali:
                heading += f" ({pali})"
            return heading,excerptHtml,gDatabase["tag"][tag]["htmlFile"].replace(".html",""),clusterInfo["displayAs"]

        def PairExcerptsWithTopic() -> Generator[tuple[dict,str]]:
            for tag,excerpts in excerptsByTopic.items():
                if excerpts:
                    if len(excerpts) == 1:
                        yield excerpts[0],tag,True,True
                    else:
                        yield excerpts[0],tag,True,False
                        for x in excerpts[1:-1]:
                            yield x,tag,False,False
                        yield excerpts[-1],tag,False,True
                else:
                    yield None,tag,True,True

        title = Html.Tag("div",{"class":"title","id":"HEADING_ID"})
        pageContent = Html.ListWithHeadings(PairExcerptsWithTopic(),FeaturedExcerptList,
                                            headingWrapper=title)
        page.AppendContent(pageContent)
        yield page

def TagClusterPages(topicDir: str):
    """Generate a series of pages for each tag cluster."""
    if gOptions.buildOnlyIndexes or "clusters" not in gOptions.buildOnly:
        return
    
    for cluster,clusterInfo in gDatabase["subtopic"].items():
        if not clusterInfo["subtags"]:
            continue

        tags = [cluster] + list(clusterInfo["subtags"].keys())
        relevantExcerpts = Filter.Tag(tags)(gDatabase["excerpts"])

        a = Airium()
        
        with a.strong():
            a(f"Part of key topic {HtmlKeyTopicLink(clusterInfo['topicCode'])}")
            a.br()
            a(ListLinkedTags("Includes tag",tags))
            relatedClusters = [HtmlSubtopicLink(c) for c in clusterInfo["related"]]
            a(TitledList("See also",relatedClusters,plural=""))
        
        if "clusterNote" in clusterInfo:
            with a.p():
                a(clusterInfo["clusterNote"])
        a.hr()

        pageTitle = titleInBody = clusterInfo["displayAs"]
        if clusterInfo["pali"]:
            titleInBody += f" ({clusterInfo['pali']})"
        pageInfo = Html.PageInfo(pageTitle,clusterInfo["htmlPath"],titleInBody)
        basePage = Html.PageDesc(pageInfo)
        basePage.AppendContent("Cluster.png",section="titleIcon")
        basePage.AppendContent(str(a))
        basePage.keywords = ["Tag cluster",clusterInfo["displayAs"]]
        basePage.AppendContent(f"Tag cluster: {clusterInfo['displayAs']}",section="citationTitle")

        yield from TagSubsearchPages(tags,relevantExcerpts,basePage,cluster=cluster)

def AddTopicButtons(page: Html.PageDesc) -> None:
    """Add buttons to show and hide subtopics."""

    page.AppendContent('<div class="hide-thin-screen-1 noscript-show">')
    page.AppendContent(Html.Tag("button",{"type":"button",
                                          "onclick":Utils.JavascriptLink(page.info.AddQuery("showAll").file + "#keep_scroll"),
                                          "class":"noscript-hide"})("Expand all"))
    page.AppendContent(Html.Tag("button",{"type":"button",
                                          "onclick":Utils.JavascriptLink(page.info.AddQuery("hideAll").file + "#keep_scroll"),
                                          "class":"noscript-hide"})("Contract all"))
    
    printableLinks = Html.Tag("a",{"href":Utils.PosixJoin("../indexes/KeyTopicDetail_print.html#noframe")})("Printable")
    if gOptions.uploadMirror == "preview":
        printableLinks += "&emsp;" + Html.Tag("a",{"href":Utils.PosixJoin("../indexes/KeyTopicMemos_print.html#noframe")})("Printable with memos")

    page.AppendContent(Html.Tag("span",{"class":"floating-menu"})(printableLinks))
    page.AppendContent(2*'<br>')

    page.AppendContent('</div>')


def CompactKeyTopics(indexDir: str,topicDir: str) -> Html.PageDescriptorMenuItem:
    "Yield a page listing all topic headings."

    menuItem = Html.PageInfo("Compact",Utils.PosixJoin(indexDir,"KeyTopics.html"),"Key topics")
    yield menuItem.AddQuery("hideAll")

    a = Airium()
    with a.div(Class='explore-content'):
        with a.div(Class='exploration-paths'):
            for topic in gDatabase["keyTopic"].values():
                with a.div(Class='path-card'):
                    a.a(Class='path-overlay',href=Utils.PosixJoin("../",topicDir,topic["listFile"]))

                    with a.h3():
                        a(HtmlIcon(Utils.PosixJoin("topics",
                                topic["code"] + ".png")))
                        a(topic["topic"])
                
                    with a.p():
                        clusterLinks = []
                        for tag in topic["subtopics"]:
                            if gOptions.keyTopicsLinkToTags:
                                link = Utils.PosixJoin("../",Utils.AppendToFilename(gDatabase["subtopic"][tag]["htmlPath"],"-relevant"))
                            else:
                                link = Utils.PosixJoin("../",topicDir,topic["listFile"]) + "#" + gDatabase["tag"][tag]["htmlFile"].replace(".html","")
                            text = gDatabase["subtopic"][tag]["displayAs"]
                            clusterLinks.append(Html.Tag("a",{"href":link})(text))
                        
                        clusterList = " &emsp; ".join(clusterLinks)
                        a(Html.HiddenBlock(clusterList,"subtopics",blockID=topic["code"],blockTag="p"))

    page = Html.PageDesc(menuItem._replace(title="Key topics"))
    page.AppendContent(str(a))
    page.AppendContent(HtmlIcon("Key.png"),section="titleIcon")

    page.keywords = ["Key topics"]
    page.AppendContent(f"Key topics",section="citationTitle")

    yield page

def DetailedKeyTopics(indexDir: str,topicDir: str,printPage = False,progressMemos = False) -> Html.PageDescriptorMenuItem:
    "Yield a page listing all topic headings."

    menuItem = Html.PageInfo("In detail",Utils.PosixJoin(indexDir,"KeyTopicDetail.html"),"Key topics")
    yield menuItem.AddQuery("hideAll")

    a = Airium()
    a("Number of featured excerpts for each topic appears in parentheses.<br><br>")
    with a.div(Class="listing"):
        for topicCode,topic in gDatabase["keyTopic"].items():
            with a.p(id=topicCode):
                if not printPage:
                    with a.a().i(Class = "fa fa-minus-square toggle-view",id=topicCode):
                        pass
                    a("&nbsp;" + HtmlIcon(Utils.PosixJoin("topics",topicCode + ".png")))
                with a.span(style="text-decoration: underline;" if printPage else ""):
                    a(HtmlKeyTopicLink(topicCode,count=True))
            with a.div(id=topicCode + ".b"):
                for subtopic in topic["subtopics"]:
                    with a.p(Class="indent-1"):
                        subtags = list(Database.SubtagIterator(gDatabase["subtopic"][subtopic]))
                        fTagCount = gDatabase['subtopic'][subtopic].get('fTagCount',0)
                        minFTag,maxFTag,diffFTag = ReviewDatabase.OptimalFTagCount(gDatabase["subtopic"][subtopic])
                        
                        prefixChar = ReviewDatabase.FTagStatusCode(gDatabase["subtopic"][subtopic])
                        
                        if prefixChar and printPage:
                            a(f"{prefixChar} ")
                        with a.strong() if len(subtags) > 1 else nullcontext(0):
                            a(HtmlSubtopicLink(subtopic).replace(".html","-relevant.html"))
                        
                        parenthetical = str(fTagCount)
                        if printPage:
                            parenthetical += f":{minFTag}-{maxFTag}/{gDatabase['subtopic'][subtopic].get('excerptCount',0)}"
                        if parenthetical != "0":
                            a(f" ({parenthetical})")

                        bitsAfterDash = []
                        if len(subtags) > 1:
                            subtagStrs = []
                            subtopicExcerpts = Filter.ClusterFTag(subtopic)(gDatabase['excerpts'])
                            for tag in subtags:
                                if tag in ReviewDatabase.SignificantSubtagsWithoutFTags():
                                    tagCount = "<b>∅</b>"
                                else:
                                    tagCount = str(Filter.FTag(tag).Count(subtopicExcerpts))
                                tagCount += f"/{gDatabase['tag'][tag].get('excerptCount',0)}"
                                subtagStrs.append(HtmlTagLink(tag) + (f" ({tagCount})" if printPage else ""))
                            bitsAfterDash.append(f"Cluster includes: {', '.join(subtagStrs)}")
                        if printPage and gDatabase["subtopic"][subtopic]["related"]:
                            bitsAfterDash.append(ListLinkedTags("Related",gDatabase["subtopic"][subtopic]["related"],plural="",endStr=""))
                        if bitsAfterDash:
                            a(" – " + "; ".join(bitsAfterDash))
                        if printPage and progressMemos:
                            with a.p(Class="indent-2"):
                                a(gDatabase['subtopic'][subtopic]["progressMemo"] or ".")

                if topic["shortNote"] and not printPage:
                    with a.p(Class="indent-1"):
                        a(topic["shortNote"])


    page = Html.PageDesc(menuItem._replace(title="Key topics"))
    
    if not printPage:
        AddTopicButtons(page)

    page.AppendContent(str(a))
    page.AppendContent(HtmlIcon("Key.png"),section="titleIcon")

    page.keywords = ["Key topics"]
    page.AppendContent(f"Key topics in detail",section="citationTitle")

    yield page

def PrintTopics(indexDir: str,topicDir: str,progressMemos:bool = False,yieldMenuItem:bool = True) -> Html.PageDescriptorMenuItem:
    "Yield a printable listing of all topic headings."
    menuEntry = "Printable"
    filename = "KeyTopicDetail_print.html"
    if progressMemos:
        filename = "KeyTopicMemos_print.html"
        menuEntry += " with memos"
    menuItem = Html.PageInfo(menuEntry,Utils.PosixJoin(indexDir,filename),"Key topics")
    if yieldMenuItem:
        yield menuItem

    topicList = DetailedKeyTopics(indexDir,topicDir,printPage=True,progressMemos=progressMemos)
    _ = next(topicList)
    page = next(topicList)
    page.info = menuItem._replace(title="Key topics")
    yield page

def KeyTopicMenu(indexDir: str) -> Html.PageDescriptorMenuItem:
    """Display a list of key topics and corresponding key tags.
    Also generate one page containing a list of all featured excepts for each key topic."""

    topicDir = "topics"
    menuItem = next(CompactKeyTopics(indexDir,topicDir))
    menuItem = menuItem.AddQuery("hideAll")._replace(title="Key topics",titleIB="Key topics")
    yield menuItem
    
    basePage = Html.PageDesc(menuItem)

    keyTopicMenu = [
        CompactKeyTopics(indexDir,topicDir),
        DetailedKeyTopics(indexDir,topicDir),
        [Html.PageInfo("About key topics","about/Overview.html#key-topics-and-tag-clusters")],
        PrintTopics(indexDir,topicDir,yieldMenuItem=False),
        PrintTopics(indexDir,topicDir,progressMemos=True,yieldMenuItem=False),
        TagClusterPages("clusters"),
        KeyTopicExcerptLists(indexDir,topicDir)
    ]

    for page in basePage.AddMenuAndYieldPages(keyTopicMenu,**SUBMENU_STYLE):
        filename = page.info.file.split("/")[-1]
        # Modify the pages after they are generated such that switching betweeen these two files does not close
        # open topic tabs.
        if filename in ("KeyTopics.html,KeyTopicDetail.html"):
            for n,menuItem in enumerate(page.section["subMenu"].items):
                if menuItem.file.endswith("?hideAll"):
                    page.section["subMenu"].items[n] = menuItem._replace(file=menuItem.file.replace("hideAll","_keep_query"))

        yield page

def TagHierarchyMenu(indexDir:str, drilldownDir: str) -> Html.PageDescriptorMenuItem:
    """Create a submentu for the tag drilldown pages."""
    
    drilldownItem = Html.PageInfo("Hierarchy",drilldownDir,"Tags – Hierarchical")
    contractAllItem = drilldownItem._replace(file=Utils.PosixJoin(drilldownDir,DrilldownPageFile(-1)))
    printableItem = drilldownItem._replace(file=Utils.PosixJoin(indexDir,"Tags_print.html"))

    yield contractAllItem

    basePage = Html.PageDesc()
    basePage.AppendContent("Hierarchical tags",section="citationTitle")
    basePage.keywords = ["Tags","Tag hierarchy"]
    
    def TagsWithPrimarySubtags():
        tagSet = set()
        tagList = gDatabase["tagDisplayList"]
        for parent,children in ParseCSV.WalkTags(tagList,returnIndices=True):
            for n in children:
                tag = tagList[n]["tag"]
                if n in tagSet or (tag and gDatabase["tag"][tag]["listIndex"] == n): # If this is a primary tag
                    tagSet.add(parent) # Then expand the parent tag
        return tagSet

    def Pages() -> Generator[Html.PageDesc]:
        printPage = Html.PageDesc(printableItem)
        tagsExpanded = EvaluateDrilldownTemplate(expandSpecificTags = TagsWithPrimarySubtags(),showStar=True)
        noToggle = re.sub(r'<i class="[^"]*?toggle[^"]*"[^>]*>*.?</i>',"",tagsExpanded)
        printPage.AppendContent(noToggle)
        yield printPage

        # Hack: Add buttons to basePage after yielding printPage so that all subsequent pages have buttons at the top.
        basePage.AppendContent('<div class="hide-thin-screen-1 noscript-show">')
        basePage.AppendContent(Html.Tag("button",{"type":"button",
                                                  "onclick":Utils.JavascriptLink(contractAllItem.AddQuery("showAll").file + "#keep_scroll")
                                                  })("Expand all"))
        basePage.AppendContent(Html.Tag("button",{"type":"button",
                                                  "onclick":Utils.JavascriptLink(contractAllItem.file + "#keep_scroll"),
                                                  })("Contract all"))
        basePage.AppendContent(Html.Tag("span",{"class":"floating-menu"})(Html.Tag("a",{"href":Utils.PosixJoin("../",printableItem.file + "#noframe")})("Printable")))
        basePage.AppendContent(2*'<br>')
        basePage.AppendContent('</div>')

        basePage.AppendContent(f"Numbers in parentheses: (Excerpts tagged/excerpts tagged with this tag or its subtags).<br><br>")
        basePage.AppendContent(HtmlIcon("tags"),section="titleIcon")

        rootPage = Html.PageDesc(contractAllItem)
        rootPage.AppendContent(EvaluateDrilldownTemplate())
        yield rootPage

        if "drilldown" in gOptions.buildOnly and not gOptions.buildOnlyIndexes:
            yield from DrilldownTags(drilldownItem)

    for page in Pages():
        newPage = basePage.Clone()
        newPage.Merge(page)
        yield newPage


def TagMenu(indexDir: str) -> Html.PageDescriptorMenuItem:
    """Create the Tags menu item and its associated submenus.
    Also write a page for each tag."""

    drilldownDir = "drilldown"
    yield next(TagHierarchyMenu(indexDir,drilldownDir))._replace(title="Tags")

    tagMenu = [
        TagHierarchyMenu(indexDir,drilldownDir),
        NumericalTagList(indexDir),
        MostCommonTagList(indexDir),
        AlphabeticalTagList(indexDir),
        [Html.PageInfo("About tags","about/Tags.html")],
        TagPages("tags")
    ]

    baseTagPage = Html.PageDesc()
    yield from baseTagPage.AddMenuAndYieldPages(tagMenu,**SUBMENU_STYLE)

def Homepage():
    """Return a single menu item for the homepage."""

    homepageName = "homepage.html"
    template = pyratemp.Template(filename=Utils.PosixJoin(gOptions.pagesDir,"templates",homepageName))

    try:
        defaultExcerpt = Database.FindExcerpt(gOptions.homepageDefaultExcerpt)
        excerptHtml = SetupFeatured.ExcerptEntry(defaultExcerpt)["shortHtml"]
    except (KeyError,ValueError):
        Alert.error(f"Unable to parse or find excerpt code {repr(gOptions.homepageDefaultExcerpt)} specified by --homepageDefaultExcerpt.")
        excerptHtml = ""

    exploreMainContent = next(iter(DispatchIterator())).Render()

    html = str(template(noscriptExcerptHtml=excerptHtml,exploreContent=exploreMainContent))

    pageInfo = Html.PageInfo("Home",homepageName,"")
    yield pageInfo

    pageDesc = Html.PageDesc(pageInfo)
    pageDesc.AppendContent(html)
    pageDesc.AppendContent("Yes",section="customLayout")
    yield pageDesc

def DispatchIterator():
    """Return a series of pages that link to subcategories of tags, teachers, and events.
    Created from gDatabase["dispatch"]; does not yield a menu item."""

    groupedByPage:dict[str,list[dict[str,str]]] = defaultdict(list)
    for link in gDatabase["dispatch"].values():
        groupedByPage[link["category"]].append(link)
    
    for pageName,pageLinks in groupedByPage.items():
        title = f"Explore {pageName.lower()}"
        pageInfo = Html.PageInfo(title,Utils.PosixJoin("dispatch",pageName+".html"))

        prompt = "the Archive" if pageName == "main" else f"{pageName.lower()} by..."
        a = Airium()
        with a.div(Class='explore-content'):
            a.h2(_t=f'Explore {prompt}')
            with a.div(Class='exploration-paths'):
                for link in pageLinks:
                    with a.a(Class='path-card', href=Utils.PosixJoin("../",link["link"])):
                        with a.h3():
                            if link["icon"]:
                                a(HtmlIcon(link["icon"]))
                            a(link["title"])
                        a.p(_t=link["description"])
        
        pageDesc = Html.PageDesc(pageInfo)
        pageDesc.AppendContent(str(a))
        pageDesc.keywords = [pageName]
        yield pageDesc

def DispatchPages():
    pages = iter(DispatchIterator())
    next(pages) # Discard the first page corresponding to the items on the homepage
    yield from pages

SUBPAGE_SUFFIXES = {"qtag","atag","quote","text","reading","story","reference","from","by","meditation","teaching"}

def WriteSitemapURL(pagePath:str,xml:Airium) -> None:
    "Write the URL of the page at pagePath into an xml sitemap."
    
    if not pagePath.endswith(".html"):
        return

    priority = 1.0
    pathParts = pagePath.split("/")
    directory = pathParts[0]
    if pagePath == "homepage.html":
        pagePath = "index.html"
    elif directory == "about":
        if re.match("[0-9]+_",pathParts[-1]):
            return
        if pathParts[-1] == "Page-Not-Found.html":
            return
    elif directory == "events":
        priority = 0.9
    else:
        return

    with xml.url():
        with xml.loc():
            xml(f"{gOptions.info.cannonicalURL}{pagePath}")
        with xml.lastmod():
            xml(Utils.ModificationDate(Utils.PosixJoin(gOptions.pagesDir,pagePath)).strftime("%Y-%m-%d"))
        with xml.changefreq():
            xml("weekly")
        with xml.priority():
            xml(priority)

def XmlSitemap(siteFiles: FileRegister.HashWriter) -> str:
    """Look through the html files we've written and create an xml sitemap."""

    xml = Airium()
    with xml.urlset(xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"):
        for pagePath in sorted(siteFiles.record):
            WriteSitemapURL(pagePath,xml)
    
    return str(xml)

class HtmlSiteMap:
    """Builds an html site map based on the menus of the pages that we pass it."""
    pageHtml:Airium = Airium() # Html of the page we have built so far
    menusAdded:set[str] = set() # The main menu items we have already added to the site map

    def __init__(self):
        pass

    def RegisterPage(self,page: Html.PageDesc) -> None:
        """Read the menus of this page in order to (possibly) add it to the site map."""
        if not page.HasSection("mainMenu") or page.section["mainMenu"].menu_highlightedItem is None:
            return # Exit if there is no highlighted item in the main menu
        
        highlightedItem:Html.PageInfo = page.section["mainMenu"].items[page.section["mainMenu"].menu_highlightedItem]
        if highlightedItem.title in self.menusAdded:
            return # Exit if we have already seen this item
        
        self.menusAdded.add(highlightedItem.title)

        otherMenus = []
        for s in itertools.chain(("subMenu","customSubMenu"),range(page.numberedSections)):
            if isinstance(page.section.get(s,None),Html.Menu):
                otherMenus.append(page.section[s])

        if otherMenus:
            with self.pageHtml.p():
                with self.pageHtml.b():
                    self.pageHtml(highlightedItem.title)
                for item in otherMenus[0].items:
                    with self.pageHtml.p(Class="indent-1").a(href=item.file):
                        self.pageHtml(item.title)
        else:
            with self.pageHtml.p().b().a(href=highlightedItem.file):
                self.pageHtml(highlightedItem.title)

    def Build(self) -> Html.PageDesc:
        "Return a page description object containing the site map."
        page = Html.PageDesc(Html.PageInfo("Site map",Utils.PosixJoin("sitemap.html")))
        page.AppendContent(f'<div class="listing">\n{str(self.pageHtml)}</div>\n')
        return page

def DesignateCannonical(htmlPage: str,cannonicalURL: str) -> str:
    """Add a rel="cannonical" link to htmlPage."""

    return htmlPage.replace('</head>',f'<link rel="canonical" href="{cannonicalURL}">\n</head>')

def WriteIndexPages(writer: FileRegister.HashWriter):
    """Copy the contents of homepage.html into the body of pages/index.html and index.html."""

    homepageBody = ExtractHtmlBody(Utils.PosixJoin(gOptions.pagesDir,"homepage.html"))

    indexTemplate = Utils.ReadFile(Utils.PosixJoin(gOptions.pagesDir,"templates","index.html"))

    # Remove the homepage redirect code from pages/index.html (the cannonical index page)
    homepageBodyNoRedirect = re.sub(r"<script>.*?</script>","",homepageBody,flags=re.DOTALL)
    indexHtml = pyratemp.Template(indexTemplate)(bodyHtml = homepageBodyNoRedirect,gOptions = gOptions)
    writer.WriteTextFile("index.html",indexHtml)

    # Keep the redirect code in the root index.html 
    indexHtml = pyratemp.Template(indexTemplate)(bodyHtml = homepageBody,gOptions = gOptions)
    # Adjust for the change in directory
    indexHtml = re.sub(r'href="(?![^"]*://)',f'href="{gOptions.pagesDir}/',indexHtml,flags=re.IGNORECASE)
    indexHtml = re.sub(r'src="(?![^"]*://)',f'src="{gOptions.pagesDir}/',indexHtml,flags=re.IGNORECASE)
    indexHtml,replaceCount = re.subn(r'location.replace\("index.html#homepage.html"',
                                     f'location.replace("{gOptions.pagesDir}/index.html"',
                                     indexHtml,flags=re.IGNORECASE)
    if replaceCount != 1:
        Alert.error("Unable to replace redirect code in pages/templates/index.html")

    indexHtml = DesignateCannonical(indexHtml,Utils.PosixJoin(gOptions.info.cannonicalURL,"index.html"))
    writer.WriteTextFile("../index.html",indexHtml)


def WriteRedirectPages(writer: FileRegister.HashWriter):
    hardRedirect = pyratemp.Template(Utils.ReadFile("pages/templates/Redirect.html"))

    dirsToWrite = DirectoriesToDeleteFrom()
    for redirect in gDatabase["redirect"].values():
        path,fileName = Utils.PosixSplit(redirect["oldPage"])
        if path not in dirsToWrite:
            continue

        if not os.path.isfile(Utils.PosixJoin(gOptions.pagesDir,redirect["newPage"])):
            Alert.error("Redirect",redirect,"points to non-existant file",redirect["newPage"])
        if redirect["type"] == "Soft":
            newPageHtml = Utils.ReadFile(Utils.PosixJoin(gOptions.pagesDir,redirect["newPage"]))
            cannonicalURL = Utils.PosixJoin(gOptions.info.cannonicalURL,gOptions.pagesDir,redirect["newPage"])
            newPageHtml = DesignateCannonical(newPageHtml,cannonicalURL)
        elif redirect["type"] == "Hard":
            oldDir,oldFile = Utils.PosixSplit(redirect["oldPage"])
            newDir,newFile = Utils.PosixSplit(redirect["newPage"])
            newPageHtml = hardRedirect(newPage = Utils.PosixJoin(Utils.PosixRelpath(newDir,oldDir),newFile))
        else:
            Alert.error("Unknown redirect type",redirect["type"])
            continue

        writer.WriteTextFile(redirect["oldPage"],newPageHtml)

def AddArguments(parser):
    "Add command-line arguments used by this module"
    
    parser.add_argument('--pagesDir',type=str,default='pages',help='Write html files to this directory; Default: ./pages')
    parser.add_argument('--globalTemplate',type=str,default='templates/Global.html',help='Template for all pages relative to pagesDir; Default: templates/Global.html')
    parser.add_argument('--homepageDefaultExcerpt',type=str,default="WR2018-2_S03_F01",help="Item code of exerpt to embed in homepage.html.")

    parser.add_argument('--buildOnly',type=str,default='',help='Build only specified sections. Set of topics,tags,clusters,drilldown,events,teachers,search,allexcerpts.')
    parser.add_argument('--buildOnlyIndexes',**Utils.STORE_TRUE,help="Build only index pages")
    parser.add_argument('--buildOnlyFirstPage',**Utils.STORE_TRUE,help="Build only the first page of multi-page lists")
    parser.add_argument('--skipSubsearchPages',**Utils.STORE_TRUE,help="Don't build subsearch pages")
    parser.add_argument('--quickBuild',**Utils.STORE_TRUE,help="Shortcut for --buildOnlyFirstPage and --skipSubsearchPages")

    parser.add_argument('--excerptsPerPage',type=int,default=100,help='Maximum excerpts per page')
    parser.add_argument('--minSubsearchExcerpts',type=int,default=10,help='Create subsearch pages for pages with at least this many excerpts.')
    parser.add_argument('--attributeAll',**Utils.STORE_TRUE,help="Attribute all excerpts; mostly for debugging")
    parser.add_argument('--keyTopicsLinkToTags',**Utils.STORE_TRUE,help="Tags listed in the Key topics page link to tags instead of topics.")
    
    parser.add_argument('--documentationDir',type=str,default='documentation',help='Read and write documentation files here; Default: ./documenation')
    parser.add_argument('--info',type=str,action="append",default=[],help="Specify infomation about this build. Format key:value")
    
    parser.add_argument('--maxPlayerTitleLength',type=int,default = 30,help="Maximum length of title tag for chip audio player.")
    parser.add_argument('--blockRobots',**Utils.STORE_TRUE,help="Use <meta name robots> to prevent crawling staging sites.")
    parser.add_argument('--urlList',type=str,default='',help='Write a list of URLs to this file.')
    parser.add_argument('--keepOldHtmlFiles',**Utils.STORE_TRUE,help="Keep old html files from previous runs; otherwise delete them.")
    
gAllSections = {"about","dispatch","topics","tags","clusters","drilldown","events","teachers","texts","books","search","allexcerpts"}
def ParseArguments():
    if gOptions.buildOnly == "":
        if gOptions.buildOnlyIndexes:
            gOptions.buildOnly = {"topics","tags","clusters","events","teachers"}
        else:
            gOptions.buildOnly = gAllSections
    elif gOptions.buildOnly.lower() == "none":
        gOptions.buildOnly = set()
    else:
        gOptions.buildOnly = set(section.strip().lower() for section in gOptions.buildOnly.split(','))
        unknownSections = gOptions.buildOnly.difference(gAllSections)
        if unknownSections:
            Alert.warning(f"--buildOnly: Unrecognized section(s) {unknownSections} will be ignored.")
            gOptions.buildOnly = gOptions.buildOnly.difference(unknownSections)
    
    # Parse gOptions.info
    class NameSpace:
        pass
    infoObject = NameSpace()
    for item in gOptions.info:
        split = item.split(":",maxsplit=1)
        if len(split) > 1:
            value = split[1]
        else:
            value = True
        setattr(infoObject,split[0],value)
    gOptions.info = infoObject

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

def YieldAllIf(iterator:Iterator,yieldAll:bool) -> Iterator:
    "Yield all of iterator if yieldAll, otherwise yield only the first element."
    if yieldAll:
        yield from iterator
    else:
        yield next(iter(iterator))

def main():
    if not os.path.exists(gOptions.pagesDir):
        os.makedirs(gOptions.pagesDir)
    
    if gOptions.buildOnly != gAllSections:
        if gOptions.buildOnly:
            Alert.warning(f"Building only section(s) --buildOnly {gOptions.buildOnly}. This should be used only for testing and debugging purposes.")
        else:
            Alert.warning(f"No sections built due to --buildOnly none. This should be used only for testing and debugging purposes.")
    
    if gOptions.quickBuild:
        gOptions.buildOnlyFirstPage = gOptions.skipSubsearchPages = True
    limitedBuild = [opt for opt in ["buildOnlyIndexes","buildOnlyFirstPage","skipSubsearchPages"]
                    if getattr(gOptions,opt)]
    if limitedBuild:
        Alert.warning("Limited build options",limitedBuild,". This should only be used for testing and debugging purposes.")

    basePage = Html.PageDesc()

    indexDir ="indexes"
    sitemapMenu = []
    sitemapMenu.append(Homepage())

    sitemapMenu.append(YieldAllIf(KeyTopicMenu(indexDir),{"topics","clusters"} | gOptions.buildOnly))
    sitemapMenu.append(YieldAllIf(TagMenu(indexDir),{"tags","drilldown"} | gOptions.buildOnly))
    sitemapMenu.append(YieldAllIf(EventsMenu(indexDir),"events" in gOptions.buildOnly))
    sitemapMenu.append(YieldAllIf(TeacherMenu("teachers"),"teachers" in gOptions.buildOnly))
    sitemapMenu.append(BuildReferences.ReferencesMenu())
    sitemapMenu.append(YieldAllIf(SearchMenu("search"),"search" in gOptions.buildOnly))
    
    if "about" in gOptions.buildOnly:
        technicalMenu = DocumentationMenu("technical",menuTitle="Technical",
                                          menuStyle=LONG_SUBMENU_STYLE | dict(menuSection="customSubMenu2"))
        sitemapMenu.append(DocumentationMenu("about", menuTitle="About",
                                         menuStyle=LONG_SUBMENU_STYLE,extraItems=[technicalMenu]))
        sitemapMenu.append(DocumentationMenu("misc",makeMenu=False))
    else:
        sitemapMenu.append([Html.PageInfo("About","about/Introduction.html")])

    sitemapMenu.append(YieldAllIf(AllExcerpts(indexDir),"allexcerpts" in gOptions.buildOnly))
    
    if "dispatch" in gOptions.buildOnly:
        sitemapMenu.append(DispatchPages())

    with (open(gOptions.urlList if gOptions.urlList else os.devnull,"w") as urlListFile,
            FileRegister.HashWriter(gOptions.pagesDir,"assets/HashCache.json",exactDates=True) as writer):
        
        startTime = time.perf_counter()
        pageWriteTime = 0.0
        sitemap = HtmlSiteMap()
        for newPage in basePage.AddMenuAndYieldPages(sitemapMenu,**MAIN_MENU_STYLE):
            pageWriteStart = time.perf_counter()
            WritePage(newPage,writer)
            sitemap.RegisterPage(newPage)
            pageWriteTime += time.perf_counter() - pageWriteStart
            print(f"{gOptions.info.cannonicalURL}{newPage.info.file}",file=urlListFile)

        if gOptions.buildOnly == gAllSections:
            WritePage(sitemap.Build(),writer) # The site map is only complete when all pages are built

        Alert.extra(f"Build main loop took {time.perf_counter() - startTime:.3f} seconds.")
        Alert.extra(f"File writing time: {pageWriteTime:.3f} seconds.")

        writer.WriteTextFile("sitemap.xml",XmlSitemap(writer))
        WriteIndexPages(writer)
        WriteRedirectPages(writer)
        Alert.extra("html files:",writer.StatusSummary())
        if not limitedBuild:
            if gOptions.buildOnly == gAllSections and writer.Count(FileRegister.Status.STALE):
                Alert.extra("stale files:",writer.FilesWithStatus(FileRegister.Status.STALE))
            if not gOptions.keepOldHtmlFiles:
                DeleteUnwrittenHtmlFiles(writer)
        
    if "texts" in gOptions.buildOnly and "books" in gOptions.buildOnly:
        BuildReferences.WriteReferenceDatabase()
    