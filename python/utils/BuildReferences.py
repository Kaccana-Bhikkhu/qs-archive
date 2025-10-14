"""Functions that build pages/texts and pages/references.
These could logically be included within Build.py, but this file is already unweildy due to length."""

from collections.abc import Iterable, Iterator
from collections import defaultdict
from typing import NamedTuple
from dataclasses import dataclass
from itertools import chain, groupby
from airium import Airium
import re
import Html2 as Html
import Suttaplex
import Utils
import Database
import Render
import Build
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

    def Truncate(self,level) -> "TextReference":
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

    def FullName(self) -> str:
        """Return the full text name of this reference."""
        numbers = self.Numbers()
        fullName = gDatabase["text"][self.text]["name"]
        return f"{fullName} {'.'.join(map(str,numbers))}"
    
Reference = TextReference

@dataclass
class LinkedReference():
    reference: Reference            # The refererence itself
    items: list[dict[str]]          # A list of events and excerpts that reference it


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
    """A class to create html pages from lists of LinkedReference."""

    level: int                          # The reference level we are working at
    references: list[LinkedReference]   # The list of references to render
    page: Html.PageDesc                 # The page we have rendered so far

    def __init__(self,level: int,references: list[LinkedReference] = None):
        self.level = level
        self.page = Html.PageDesc()
        if references:
            self.references = references
            self.SetPageInfo(references[0].reference)
        else:
            self.references = []

    def SetPageInfo(self,fromReference: Reference) -> None:
        """Set the page information for this object; usually fromReference is the first reference in the list.
        Calls the general dispatch function below."""
        self.page.info = ReferencePageInfo(fromReference,self.level)

    def AppendReferences(self,references: Iterable[LinkedReference]) -> None:
        """Append these references to the list waiting to be rendered."""
        if not self.references:
            self.SetPageInfo(references[0].reference)
        self.references.extend(references)

    def RenderAndYieldSubpages(self) -> Iterator[Html.PageDesc]:
        """Append the html description of self.references to the page under construction.
        Yield PageDesc objects describing any subpages created in the process.
        Then clear the reference list and page to start anew."""
        self.references = [] # Base class implementation simply clears the reference list
        return ()
    
    def FinishPage(self) -> Html.PageDesc:
        """Return the page generated so far and clear the page for future use."""
        returnValue = self.page
        self.page = Html.PageDesc(self.page.info)
        return returnValue

    def AllPages(self) -> Iterator[Html.PageDesc]:
        """Yield all pages and subpages."""
        yield from self.RenderAndYieldSubpages()
        yield self.FinishPage()
    
    def YieldHtml(self) -> str:
        """Return the html generated so far and clear the in-progress page."""
        html = str(self.page)
        self.page = Html.PageDesc(self.page.info)
        return html


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


class PlainHeadingPage(ReferencePageMaker):
    """Split references into groups by level: (level 0 means DN, MN,...; level 1 means DN 1, DN 2,...).
    Then generate one page with headings for this level plus any pages required for sublevels."""

    def RenderAndYieldSubpages(self) -> Iterator[Html.PageDesc]:
        a = Airium()
        with a.div(Class="listing"):
            for key,referenceGroup in groupby(self.references,lambda r:r.reference[0:self.level + 1]):
                referenceGroup = list(referenceGroup)
                subPageInfo = ReferencePageInfo(referenceGroup[0].reference,self.level + 1)
                thisReference = referenceGroup[0].reference.Truncate(self.level + 1)
                link = Html.Tag("a",{"href":Utils.PosixJoin("../",subPageInfo.file)})
                if self.level == 0:
                    name = link(thisReference.FullName())
                else:
                    name = link(str(thisReference))
                    traslatedTitle = Suttaplex.Title(thisReference.Uid())
                    if traslatedTitle:
                        name += f": {traslatedTitle}"
                totalTexts = sum(len(group.items) for group in referenceGroup)
                with a.p():
                    a(f"{name} ({totalTexts})")
                
                pageGenerator = ReferencePageDispatch(referenceGroup,self.level + 1)
                yield from pageGenerator.AllPages()

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
        title = f"References – {str(referenceGroup)}"
        translatedTitle = Suttaplex.Title(referenceGroup.Uid())
        if translatedTitle:
            title += f": {translatedTitle}"
    else:
        title = f"References – {referenceGroup.FullName()}"
    return Html.PageInfo(
        title,
        f"{directory}{text}{strNumbers}.html"
    )

def ReferencePageDispatch(references: list[LinkedReference],level: int) -> ReferencePageMaker:
    """Return a series of pages that link references to where they occur in the Archive.
    Apply logic to determine whether to call PlainHeadingPage or ExcerptListPage.
    level 0 means DN, MN,...; level 1 means DN 1, DN 2,...)"""

    if level == 0:
        return PlainHeadingPage(level,references)
    elif len(references) < gOptions.minSubsearchExcerpts:
        return ExcerptListPage(level,references)
    
    text = references[0].reference.text
    singleRef = text in TextGroupSet("singleRef")
    doubleRef = text in TextGroupSet("doubleRef")
    
    if (singleRef and level <= 1) or (doubleRef and level <= 2):
        return PlainHeadingPage(level,references)
    else:
        return ExcerptListPage(level,references)

def FirstLevelMenu(references: list[LinkedReference]) -> Html.PageDescriptorMenuItem:
    """Return the menu item and pages corresponding to references."""

    yield ReferencePageInfo(references[0].reference,0)
    pageGenerator = ReferencePageDispatch(references,0)
    yield from pageGenerator.AllPages()

def TextMenu() -> Html.PageDescriptorMenuItem:
    """Return a list containing the sutta and vinaya reference pages."""

    textReferences = CollateReferences("texts")
    vinayaRefs,suttaRefs = Utils.Partition(textReferences,lambda r:r.reference.text in TextGroupSet("vinaya"))
    WriteReferences(vinayaRefs,"TextReferences.txt")

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
    