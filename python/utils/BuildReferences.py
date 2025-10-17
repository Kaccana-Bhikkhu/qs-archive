"""Functions that build pages/texts and pages/references.
These could logically be included within Build.py, but this file is already unweildy due to length."""

from collections.abc import Iterable, Iterator, Hashable
from collections import defaultdict
from typing import NamedTuple
from dataclasses import dataclass
from itertools import chain, groupby
from airium import Airium
from enum import Enum
import re
import Html2 as Html
import Suttaplex
import Utils
import Database
import Render
import Build
import Alert
from functools import lru_cache

gOptions = None
gDatabase:dict[str] = {} # These will be set later by QSarchive.py

@lru_cache(maxsize=None)
def TextSortOrder() -> dict[str,int]:
    """Return the sort order of the texts."""
    return {text:n for n,text in enumerate(gDatabase["text"])}

@lru_cache(maxsize=None)
def TextGroupSet(which: str) -> set[str]:
    """Return a set of the texts in this group."""
    return set(gDatabase["textGroup"][which])

class TextReference(NamedTuple):
    text: str           # The name of the text, e.g. 'Dhp'
    n0: int = 0         # The three possible index numbers; 0 means an index is omitted
    n1: int = 0
    n2: int = 0

    @staticmethod
    def FromString(reference: str) -> "TextReference":
        """Create this object from a sutta reference string."""
        suttaMatch = r"(\w+)\s+([0-9]+)?(?:[.:]([0-9]+))?(?:[.:]([0-9]+))?"
        """ Sutta reference pattern: uid [n0[.n1[.n2]]]
            Matching groups:
            1: uid: SuttaCentral text uid
            2-4: n0-n2: section numbers"""
        matchObject = re.match(suttaMatch,reference)
        numbers = [int(n) for n in (matchObject[2],matchObject[3],matchObject[4]) if n]
        text = "Kd" if matchObject[1] == "Mv" else matchObject[1] # Mv is equivalent to Kd

        # For texts referenced by PTS verse, convert 
        if len(numbers) == 1 and text in ("Snp","Thag","Thig"):
            pageUid = Render.SCIndex(text.lower(),numbers[0]).uid
            newNumbers = re.search("[0-9.]+",pageUid)[0]
            if newNumbers:
                newNumbers = newNumbers.split(".")
                numbers = (newNumbers + [numbers[0]])[0:3]
                numbers = [int(n) for n in numbers]

        return TextReference(text,*numbers)

    def Truncate(self,level:int) -> "TextReference":
        """Replace all elements with index >= level with 0 or ''."""
        keep = self[0:level]
        return TextReference(*keep,*[0 if type(self[index]) == int else "" for index in range(level,len(self))])

    def Numbers(self) -> tuple[int,int,int]:
        """Return a tuple of the reference numbers"""
        return tuple(int(n) for n in self[1:] if n)

    def SortKey(self) -> tuple:
        """Return a tuple to sort these texts by."""
        return (TextSortOrder()[self.text],) + self.Numbers()

    def __str__(self) -> str:
        return f"{self.text} {'.'.join(map(str,self.Numbers()))}"
    
    def BaseUid(self) -> str:
        if self.text == "Kd":
            return "pli-tv-kd"
        elif self.text.startswith("Bu"):
            return f"pli-tv-bu-vb-{self.text[2:4].lower()}"
        elif self.text.startswith("Bi"):
            return f"pli-tv-bi-vb-{self.text[2:4].lower()}"
        else:
            return self.text.lower()
    
    def Uid(self) -> str:
        """Return a good guess for the SuttaCentral uid"""
        return f"{self.BaseUid()}{'.'.join(map(str,self.Numbers()))}"

    def GroupUid(self) -> str:
        """Return the uid of the sutta group this belongs to, e.g. an1.1-10.
        Returns '' if the sutta doesn't belong to a group."""
        return "" # Currently not implemented
        if self.text not in ("SN","AN"):
            return ""
        return Suttaplex.InterpolatedSuttaDict(self.BaseUid()).get(self.Uid(),"")

    def SuttaCentralLink(self) -> str:
        """Return the SuttaCentral link for this text."""
        if self.n0 == 0:
            if self.text:
                return f"https://suttacentral.net/{self.BaseUid()}"
            else:
                return ""
        mockMatch = [str(self),self.text] + [str(n) if n else "" for n in self[1:4]] + [""]
            # ApplySuttaMatchRules usually takes a match, but anything with indices will do.
        return Render.ApplySuttaMatchRules(mockMatch)
    
    def ReadingFaithfullyLink(self) -> str:
        """Return the ReadingFaithfully link for this text."""
        if self.text not in TextGroupSet("readFaith"):
            return ""
        query = self.text + ".".join(str(n) for n in self.Numbers())
        return f"https://sutta.readingfaithfully.org/?q={query}"

    def FullName(self) -> str:
        """Return the full text name of this reference."""
        numbers = self.Numbers()
        fullName = gDatabase["text"][self.text]["name"]
        return f"{fullName} {'.'.join(map(str,numbers))}"
    
    def BreadCrumbs(self) -> str:
        """Returns an html string like 'Sutta / MN / MN 10' that goes at the top of reference pages."""

        if not self.text:
            return ""
        numbers = self.Numbers()
        pageInfo = [ReferencePageInfo(self,level) for level in range(0,len(numbers) + 2)]
        bits = [info.title for info in pageInfo[0:2]]
        bits.extend(str(self.Truncate(level)) + ": " + 
                    Suttaplex.Title(self.Truncate(level).Uid(),translated=False) for level in range(2,len(numbers) + 2))
        for level in range(len(numbers) + 1):
            bits[level] = Html.Tag("a",{"href":f"../{pageInfo[level].file}"})(bits[level])
        
        return " / ".join(bits)
    
Reference = TextReference

@dataclass
class LinkedReference():
    reference: Reference            # The refererence itself
    items: list[dict[str]]          # A list of events and excerpts that reference it

def TotalItems(references: Iterable[LinkedReference]) -> int:
    """Return the nubmer of items in references."""
    return sum(len(group.items) for group in references)

def GroupBySutta(references: Iterable[TextReference]) -> Iterable[list[LinkedReference]]:
    """Group references by sutta and yield a list of each group."""

    for key,group1 in groupby(references,key = lambda ref:ref[0:2]):
        group1 = list(group1)
        if group1[0].text in TextGroupSet("doubleRef"):
            for key,group2 in groupby(group1,key = lambda ref:ref[0:3]):
                yield list(group2)
        else:
            yield group1

def CollateReferences(referenceKind: str) -> list[LinkedReference]:
    """Read the references stored in gDatabase and return a sorted list of LinkedReference objects.
    referenceKind is either 'texts' or 'books'."""

    referenceDict:dict[Reference,list[dict[str]]] = defaultdict(list)

    for event in gDatabase["event"].values():
        for ref in event.get(referenceKind,()):
            referenceDict[TextReference.FromString(ref)].append(event)
    for excerpt in gDatabase["excerpts"]:
        references = [TextReference.FromString(ref) for ref in excerpt.get(referenceKind,())]
        if not references:
            continue
        references.sort(key=TextReference.SortKey)
        for group in GroupBySutta(references): # Only one excerpt per sutta
            referenceDict[group[0]].append(excerpt)

    collated:list[LinkedReference] = []
    for ref,items in referenceDict.items():
        collated.append(LinkedReference(ref,items))

    collated.sort(key = lambda r:r.reference.SortKey())
    return collated

def WriteReferences(references:list[LinkedReference],filename:str) -> None:
    """Write a list of these references for debugging purposes."""
    with open(filename,"w",encoding='utf8') as file:
        for ref in references:
            print(ref.reference,file=file)
            for item in ref.items:
                print("   ",Database.ItemRepr(item),file=file)


class ReferencePageMaker:
    """A class to create html pages from lists of LinkedReference.
    Can be used in two ways:
    1) Whole page mode - Call __init__ with a list of references and call FinishPage to return a PageDesc object.
    2) Subpage mode - Call __init__without references, then call AppendReferences and YieldHtml repeatedly to produce subpage content."""

    wholePage: bool = False             # Are we rendering a whole page?
    level: int                          # The reference level we are working at
    references: list[LinkedReference]   # The list of references to render
    page: Html.PageDesc                 # The page we have rendered so far
    footerHtml: str = ""                # Store html that will go at the end of the page

    def __init__(self,level: int,references: list[LinkedReference] = None):
        self.level = level
        self.page = Html.PageDesc()
        if references:
            self.references = references
            self.wholePage = True
            self.SetPageInfo(references[0].reference)
            self.page.AppendContent(self.HeaderHtml())
            self.footerHtml = self.FooterHtml()
        else:
            self.references = []

    def SetPageInfo(self,fromReference: Reference) -> None:
        """Set the page information for this object; usually fromReference is the first reference in the list.
        Calls the general dispatch function below."""
        self.page.info = ReferencePageInfo(fromReference,self.level)

    def HeaderHtml(self) -> str:
        """Returns html that goes a the top of the page in whole page mode."""
        if self.level > 0:
            reference = self.references[0].reference.Truncate(self.level)
            bits = [reference.BreadCrumbs()]
            scLink = reference.SuttaCentralLink()
            if scLink:
                bits.append("&nbsp;" + Html.Tag("a",{"href":scLink,"title":"Read on SuttaCentral","target":"_blank"})
                            (Build.HtmlIcon("SuttaCentral.png","small-icon")))
            rfLink = reference.ReadingFaithfullyLink()
            if scLink:
                bits.append("&nbsp;" + Html.Tag("a",{"href":rfLink,"title":"Browse translations on Reading Faithfully","target":"_blank"})
                            (Build.HtmlIcon("ReadingFaithfully.png","small-icon")))
            bits.append("<hr>")
            return "\n".join(bits)
        else:
            return self.page.info.title + "\n<hr>"
    
    def FooterHtml(self) -> str:
        """Returns html that goes a the bottom of the page in whole page mode."""
        return ""

    def RenderAndYieldSubpages(self) -> Iterator[Html.PageDesc]:
        """Append the html description of self.references to the page under construction.
        Yield PageDesc objects describing any subpages created in the process.
        Then clear the reference list and page to start anew."""
        self.references = [] # Base class implementation simply clears the reference list
        return ()
    
    def FinishPage(self) -> Html.PageDesc:
        """Return the page generated so far and clear the page for future use."""
        self.page.AppendContent(self.footerHtml)
        returnValue = self.page
        self.page = Html.PageDesc(self.page.info)
        return returnValue

    def AllPages(self) -> Iterator[Html.PageDesc]:
        """Yield all pages and subpages."""
        yield from self.RenderAndYieldSubpages()
        yield self.FinishPage()
    
    def AppendReferences(self,references: Iterable[LinkedReference]) -> None:
        """Append these references to the list waiting to be rendered."""
        if not self.references:
            self.SetPageInfo(references[0].reference)
        self.references.extend(references)

    def YieldHtml(self) -> str:
        """Return the html generated so far and clear the in-progress page."""
        html = str(self.page)
        self.page = Html.PageDesc(self.page.info)
        return html

class YieldSubpages(ReferencePageMaker):
    """Generate no body html, but link to the page indicated by the references.
    Should be used only in subpage mode."""

    def __init__(self, level):
        super().__init__(level)
    
    def RenderAndYieldSubpages(self):
        pageGenerator = ReferencePageDispatch(self.references,self.level + 1)
        yield from pageGenerator.AllPages()
        yield from super().RenderAndYieldSubpages()

def BoldfaceTextReferences(html: str,text: TextReference) -> str:
    """Return html with each reference to text in boldface."""

    textDB = gDatabase["text"]
    if text.text == "Kd":
        textName = f"({textDB["Kd"]["name"]}|{textDB["Mv"]["name"]})" # Kd also matches Mv
    else:
        textName = textDB[text.text]["name"] if textDB[text.text]["citeFullName"] else text.text
    
    numbers = text.Numbers()
    if numbers:
        nonOptional = "[.:]".join(str(n) for n in numbers)
    else:
        nonOptional = "[0-9]+"
    optional = (3 - min(len(numbers),1)) * "(?:[.:][0-9]+)?"
    fullRegex = r"\b" + textName + r"\s+" + f"{nonOptional}(?![0-9]){optional}(?:-[0-9]+)?"

    return Html.BoldfaceMatches(html,fullRegex)

class ExcerptListPage(ReferencePageMaker):
    """Generate a page containing the list of specified excerpts."""

    def RenderAndYieldSubpages(self) -> Iterator[Html.PageDesc]:
        a = Airium()
        formatter = Build.Formatter()
        formatter.SetHeaderlessFormat()
        firstLoop = True
        for reference in self.references:
            events,excerpts = Utils.Partition(reference.items,lambda item: "endDate" in item)
            if not firstLoop:
                a.hr()
            firstLoop = False
            a(formatter.HtmlExcerptList(excerpts))

        html = BoldfaceTextReferences(str(a),self.references[0].reference.Truncate(self.level))
        self.page.AppendContent(html)
        yield from super().RenderAndYieldSubpages()


HeadingGroupCode = Hashable
"""A code to group references together by; can be any hashable type."""
class Heading:
    """A class that groups references under headings."""
    groupCode: HeadingGroupCode             # The current heading group we are iterating over
    groupReferences: list[LinkedReference]  # The current group of references
    enclosingClass: str = ""                # Enclose the entire list headers in a div of this class

    def HeadingCode(self,reference: Reference) -> HeadingGroupCode:
        """Return the HeadingGroupCode of this reference."""
        raise NotImplementedError("Heading subclasses must implement this.")
    
    def GroupedReferences(self,references: Iterable[LinkedReference]) -> Iterator[list[LinkedReference]]:
        """Iterate over these references grouped by heading code.
        Update the Heading's members to reflect the current header."""
        for code,groupedRefs in groupby(references,lambda ref:self.HeadingCode(ref.reference)):
            self.groupCode = code
            self.groupReferences = list(groupedRefs)
            yield self.groupReferences
    
    def Html(self,headingCode: HeadingGroupCode = None) -> str | Html.Wrapper:
        """Return an html string or wrapper that renders this heading code."""
        return Html.Tag("span",{"id",self.Bookmark(headingCode or self.groupCode)})
    
    def Bookmark(self,headingCode: HeadingGroupCode = None) -> str:
        """Returns the bookmark corresponding to this heading code."""
        return Utils.slugify(str(headingCode or self.groupCode))
    

class SingleLevelHeadings(Heading):
    """A class that groups references at a specific level. 
    The base class generates headers with the name of each level."""

    level: int  # The heading level; level 0 groups by sutta (all MN together)
                # level 1 groups by sutta and the first number (all MN 2 together)

    def __init__(self,level):
        self.level = level

    def HeadingCode(self,reference: Reference) -> Reference:
        """The heading code is simply the truncated reference."""
        header = reference.Truncate(self.level + 1)
        group = header.GroupUid()
        if group:
            startingNumber = int(re.search(r"([0-9])+-[0-9]+$",group)[1])
            numbers = list(header.Numbers())
            numbers[-1] = startingNumber
            header = TextReference(header.text,*numbers)
        return header
    
    def Html(self, headingCode:Reference = None) -> str:
        headingCode = headingCode or self.groupCode
        name = headingCode.FullName()
        traslatedTitle = Suttaplex.Title(headingCode.Uid())
        if traslatedTitle:
            name += f": {traslatedTitle}"
        return Html.Tag("div",{"class":"title","id":self.Bookmark()})(name)

class LinkedHeadings(SingleLevelHeadings):
    """Generates a list of links to subpages."""
    enclosingClass = "listing"

    def Html(self, headingCode:Reference = None) -> str:
        headingCode = headingCode or self.groupCode
        subPageInfo = ReferencePageInfo(headingCode,self.level + 1)
        thisReference = headingCode.Truncate(self.level + 1)
        link = Html.Tag("a",{"href":Utils.PosixJoin("../",subPageInfo.file)})
        if self.level == 0:
            name = link(thisReference.FullName())
        else:
            name = link(str(thisReference))
            group = thisReference.GroupUid()
            if group:
                translatedTitle = Suttaplex.Title(group)
            else:
                translatedTitle = Suttaplex.Title(thisReference.Uid())
            if translatedTitle:
                name += f": {translatedTitle}"
        totalTexts = TotalItems(self.groupReferences)
        return Html.Tag("p",{"id":self.Bookmark()})(f"{name} ({totalTexts})")

class PageWithHeadings(ReferencePageMaker):
    """Split references into groups by level: (level 0 means DN, MN,...; level 1 means DN 1, DN 2,...).
    Then generate one page with headings for this level plus any pages required for sublevels."""
    
    heading: Heading                    # The heading generator for this object
    content: ReferencePageMaker         # Generates content within each heading

    def __init__(self,heading: Heading,content: ReferencePageMaker,references: list[LinkedReference]):
        super().__init__(content.level,references)
        self.heading = heading
        self.content = content

    def RenderAndYieldSubpages(self) -> Iterator[Html.PageDesc]:
        a = Airium()
        with a.div(Class=self.heading.enclosingClass):
            for referenceGroup in self.heading.GroupedReferences(self.references):
                a(self.heading.Html())
                self.content.AppendReferences(referenceGroup)
                yield from self.content.RenderAndYieldSubpages()
                a(self.content.YieldHtml())

        self.page.AppendContent(str(a))
        yield from super().RenderAndYieldSubpages()
        

def ReferencePageInfo(firstRef: Reference,level: int) -> Html.PageInfo:
    """Return the page information for a given page of references."""

    text = firstRef.text
    if level == 0:
        if text in TextGroupSet("vinaya"):
            return Html.PageInfo("Vinaya","texts/Vinaya.html","References – Vinaya")
        else:
            return Html.PageInfo("Sutta","texts/Sutta.html","References – Suttas")
    
    referenceGroup = firstRef.Truncate(level)
    directory = "texts/"
    strNumbers = '_'.join(map(str,referenceGroup.Numbers()))
    if level > 1:
        title = str(referenceGroup)
        translatedTitle = Suttaplex.Title(referenceGroup.Uid())
        if translatedTitle:
            title += f": {translatedTitle}"
    else:
        title = referenceGroup.FullName()
    return Html.PageInfo(
        title,
        f"{directory}{text}{strNumbers}.html",
        f"References – {title}"
    )

def ReferencePageDispatch(references: list[LinkedReference],level: int) -> ReferencePageMaker:
    """Return a series of pages that link references to where they occur in the Archive.
    Apply logic to determine whether to call PlainHeadingPage or ExcerptListPage.
    level 0 means DN, MN,...; level 1 means DN 1, DN 2,...)"""

    class PageType(Enum):
        LINKED_HEADINGS = 1
        EXCERPTS_WITH_HEADINGS = 2
        EXCERPTS_ONLY = 3

    def Dispatch() -> PageType:
        if level == 0:
            return PageType.LINKED_HEADINGS
        
        text = references[0].reference.text
        textLevel = 2 if text in TextGroupSet("singleRef") else 3 if text in TextGroupSet("doubleRef") else 1

        if textLevel == 1:
            return PageType.EXCERPTS_WITH_HEADINGS

        if level < textLevel and TotalItems(references) >= gOptions.minSubsearchExcerpts:
            return PageType.LINKED_HEADINGS
        else:
            if level < textLevel:
                return PageType.EXCERPTS_WITH_HEADINGS
            else:
                return PageType.EXCERPTS_ONLY
    
    pageType = Dispatch()
    if pageType == PageType.LINKED_HEADINGS:
        return PageWithHeadings(LinkedHeadings(level),YieldSubpages(level),references)
    elif pageType == PageType.EXCERPTS_WITH_HEADINGS:
        return PageWithHeadings(SingleLevelHeadings(level),ExcerptListPage(level),references)
    elif pageType == PageType.EXCERPTS_ONLY:
        return ExcerptListPage(level,references)
    Alert.error("Unknown page type",pageType)

def FirstLevelMenu(references: list[LinkedReference]) -> Html.PageDescriptorMenuItem:
    """Return the menu item and pages corresponding to references."""

    yield ReferencePageInfo(references[0].reference,0)
    pageGenerator = ReferencePageDispatch(references,0)
    yield from pageGenerator.AllPages()

def TextMenu() -> Html.PageDescriptorMenuItem:
    """Return a list containing the sutta and vinaya reference pages."""

    textReferences = CollateReferences("texts")
    vinayaRefs,suttaRefs = Utils.Partition(textReferences,lambda r:r.reference.text in TextGroupSet("vinaya"))
    # WriteReferences(vinayaRefs,"TextReferences.txt")

    return [
        Build.YieldAllIf(FirstLevelMenu(suttaRefs),"texts" in gOptions.buildOnly),
        Build.YieldAllIf(FirstLevelMenu(vinayaRefs),"texts" in gOptions.buildOnly)
    ]

def ReferencesMenu() -> Html.PageDescriptorMenuItem:
    """Create the References menu item and its associated submenus."""

    referencesMenu = TextMenu()
    yield Html.PageInfo("References","texts/Sutta.html")

    baseTagPage = Html.PageDesc()
    yield from baseTagPage.AddMenuAndYieldPages(referencesMenu,**Build.SUBMENU_STYLE)
    