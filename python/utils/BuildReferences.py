"""Functions that build pages/texts and pages/references.
These could logically be included within Build.py, but this file is already unwieldy due to length."""

from collections.abc import Iterable, Iterator, Hashable
from collections import defaultdict
from typing import NamedTuple, Optional
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

    def TextLevel(self) -> int:
        """Return the number of numbers it takes to specify a specific sutta."""
        return 1 if self.text in TextGroupSet("singleRef") else 2 if self.text in TextGroupSet("doubleRef") else 0

    def Truncate(self,level:int) -> "TextReference":
        """Replace all elements with index >= level with 0 or ''."""
        if all(not self[n] for n in range(level,4)):
            return self # Return self if nothing changes
        keep = self[0:level]
        return TextReference(*keep,*[0 if type(self[index]) == int else "" for index in range(level,len(self))])

    def Numbers(self) -> tuple[int,int,int]:
        """Return a tuple of the reference numbers"""
        return tuple(int(n) for n in self[1:] if n)

    def SortKey(self) -> tuple:
        """Return a tuple to sort these texts by."""
        return (TextSortOrder()[self.text],) + self.Numbers()

    def IsCommentary(self) -> bool:
        return False
    
    def IsSubreference(self) -> bool:
        """Return true if the reference specifies a subsection within a sutta."""
        return self[self.TextLevel() + 1] != 0
        
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

    def LinkIcons(self) -> list[str]:
        """Returns a list of html icons linking to this text. Usually comes after bread crumbs."""
        returnValue = []
        scLink = self.SuttaCentralLink()
        if scLink:
            returnValue.append(Html.Tag("a",{"href":scLink,"title":"Read on SuttaCentral","target":"_blank"})
                        (Build.HtmlIcon("SuttaCentral.png","small-icon")))
        rfLink = self.ReadingFaithfullyLink()
        if rfLink:
            returnValue.append(Html.Tag("a",{"href":rfLink,"title":"Browse translations on Reading Faithfully","target":"_blank"})
                        (Build.HtmlIcon("ReadingFaithfully.png","small-icon")))
        return returnValue


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

class ConsecutiveTexts(TextReference):
    """A reference to a consecutive group of texts, e.g. SN 12.72-81."""

    @staticmethod
    def FromReference(reference: TextReference) -> Optional["ConsecutiveTexts"]:
        """Returns the group that reference belongs to; returns None if the sutta is not grouped."""
        if not isinstance(reference,TextReference) or reference.text not in ("SN","AN"):
            return None
        groupUid = Suttaplex.InterpolatedSuttaDict(reference.BaseUid()).get(reference.Uid(),"")
        if groupUid:
            startingNumber = int(re.search(r"([0-9]+)-[0-9]+$",groupUid)[1])
            numbers = list(reference.Numbers())
            numbers[-1] = startingNumber
            return ConsecutiveTexts(reference.text,*numbers)
        else:
            return None

    def Uid(self) -> str:
        """Return the SuttaCentral uid"""
        return Suttaplex.InterpolatedSuttaDict(self.BaseUid()).get(super().Uid())

    def RangeEnd(self) -> int:
        """Return the end of the range, eg. 81 for SN 12.72-81."""
        uid = self.Uid()
        m = re.search(r"[0-9]+$",uid)
        return int(m[0])

    def __str__(self) -> str:
        return f"{super().__str__()}-{self.RangeEnd()}"
    
    def FullName(self) -> str:
        return f"{super().FullName()}-{self.RangeEnd()}"


@lru_cache(maxsize=None)
def AlphabetizedTeachers() -> dict[str,tuple[int,str]]:
    """Return a dict of alphabetized teachers.
    keys: teacher code
    values: the tuple (sort order, alphabetized name)"""

    rawAlphabetized = Build.AlphabetizedTeachers(gDatabase["teacher"].values())
    return {t["teacher"]:(n,alphaName) for n,(alphaName,t) in enumerate(rawAlphabetized)}
class BookReference(NamedTuple):
    author: str                  # Teacher code; e.g. 'AP
    abbreviation: str = ""       # Title abbreviation; e.g. 'bmc 1'
    page: int = 0                # Page number; 0 means the whole book   

    @staticmethod
    def FromString(reference: str) -> "BookReference":
        """Create this object from a string of form 'Title|page'."""
        parts = reference.split("|")
        abbreviation = parts[0].lower()
        author = gDatabase["reference"][abbreviation]["author"]
        if author:
            author = author[0]
        else:
            author = "various"
        page = int(parts[1]) if len(parts) > 1 else 0
        return BookReference(author,abbreviation,page)
    
    def MultipleAuthors(self) -> list["BookReference"]:
        """Return a list of references specifying each author separately."""
        returnValue = [self]
        if not self.abbreviation:
            return returnValue
        for otherAuthor in gDatabase["reference"][self.abbreviation]["author"][1:]:
            returnValue.append(self._replace(author = otherAuthor))
        return returnValue
    
    def FirstAuthor(self) -> "BookReference":
        """Return this reference substituting the first author of the book."""
        if not self.abbreviation or len(gDatabase["reference"][self.abbreviation]["author"]) <= 1:
            return self
        return self._replace(author = gDatabase["reference"][self.abbreviation]["author"][0])

    def Truncate(self,level:int) -> "BookReference":
        """Replace all elements with index >= level with 0 or ''."""
        keep = self[0:level]
        return BookReference(*keep,*[0 if type(self[index]) == int else "" for index in range(level,len(self))])

    def Numbers(self) -> tuple[int,int,int]:
        """Return a tuple of the reference numbers"""
        if self.page:
            return (self.page,)
        else:
            return ()

    def SortKey(self) -> tuple:
        """Return a tuple to sort these texts by."""
        sortTitle = gDatabase["reference"][self.abbreviation]["title"].strip('_“')
        year = gDatabase["reference"][self.abbreviation]["year"]
        try:
            year = int(year)
        except ValueError:
            year = 9999
        if self.IsCommentary(): # Sort commentarial texts only by year
            return (year,year,sortTitle,self.page)
        if self.author:
            return (AlphabetizedTeachers()[self.author][0],year,sortTitle,self.page)
        else:
            return (9999,year,sortTitle,self.page)

    def IsCommentary(self) -> bool:
        """Return True if this reference refers to a commentarial work."""
        return self.abbreviation and gDatabase["reference"][self.abbreviation]["commentary"]

    def IsSubreference(self) -> bool:
        """Return true if the reference specifies a page number."""
        return self.page != 0

    def __str__(self) -> str:
        return f"{self.author}, {self.abbreviation}, p. {self.page}"
    
    def TextTitle(self) -> str:
        """Return the book title without markdown formatting."""
        markdown = gDatabase["reference"][self.abbreviation]["title"]
        markdown = re.sub(r"\[([^]]*)\]\([^)]*\)",r"\1",markdown) # Extract text from Markdown hyperlinks
        html,_ = Render.MarkdownFormat(markdown,self)
        return Utils.RemoveHtmlTags(html)

    def FullName(self) -> str:
        """Return the full text name of this reference."""
        if self.author and not self.abbreviation:
            return AlphabetizedTeachers()[self.author][1]
        if self.abbreviation:
            book = gDatabase["reference"][self.abbreviation]
            bits = [book["title"]]
            if self.page:
                bits.append(f"p. {self.page}")
            if book["year"] and not self.IsCommentary():
                bits.append(f"({book['year']})")
            markdown = " ".join(bits)
            markdown = re.sub(r"\[([^]]*)\]\([^)]*\)",r"\1",markdown) # Extract text from Markdown hyperlinks
            text,_ = Render.MarkdownFormat(markdown,book)
            return text
        else:
            return ""

    def BreadCrumbs(self) -> str:
        """Return an html string like 'Modern / Ajahn Pasanno / The Island'"""
        firstAuthor = self.FirstAuthor()
        bits = []
        pageInfo = None
        for level in range(3):
            if level >= 1 and not firstAuthor[level - 1]:
                break
            if firstAuthor.IsCommentary() and level == 1:
                continue # Skip the author name for commentarial works
            if pageInfo:
                bits[-1] = Html.Tag("a",{"href":"../" + pageInfo.file})(bits[-1])
            pageInfo = ReferencePageInfo(firstAuthor,level)
            bits.append(pageInfo.title)
        
        return " / ".join(bits)
    
    def LinkIcons(self) -> list[str]:
        return []
        
Reference = TextReference | BookReference

@dataclass
class LinkedReference():
    reference: Reference            # The refererence itself
    items: list[dict[str]]          # A list of events and excerpts that reference it

def TotalItems(references: Iterable[LinkedReference]) -> int:
    """Return the nubmer of items in references."""
    return sum(len(group.items) for group in references)

def GroupByBook(references: Iterable[Reference]) -> Iterable[list[LinkedReference]]:
    """Group references by sutta or book and yield a list of each group."""

    for key,group1 in groupby(references,key = lambda ref:ref[0:2]):
        group1 = list(group1)
        if isinstance(group1[0],TextReference) and group1[0].text in TextGroupSet("doubleRef"):
            for key,group2 in groupby(group1,key = lambda ref:ref[0:3]):
                yield list(group2)
        else:
            yield group1

def CollateReferences(referenceKind: str) -> list[LinkedReference]:
    """Read the references stored in gDatabase and return a sorted list of LinkedReference objects.
    referenceKind is either 'texts' or 'books'."""

    referenceDict:dict[Reference,list[dict[str]]] = defaultdict(list)
    referenceClass = TextReference if referenceKind == "texts" else BookReference

    for event in gDatabase["event"].values():
        references = [referenceClass.FromString(ref) for ref in event.get(referenceKind,())]
        if not references:
            continue
        references.sort(key = lambda r:r.SortKey())
        for group in GroupByBook(references):
            if isinstance(group[0],TextReference):
                referenceDict[group[0]].append(event) # Append only the first reference to an event.
            else:
                for authorRef in group[0].MultipleAuthors():
                    referenceDict[authorRef].append(event)
    
    for excerpt in gDatabase["excerpts"]:
        references = [referenceClass.FromString(ref) for ref in excerpt.get(referenceKind,())]
        if not references:
            continue
        references.sort(key=referenceClass.SortKey)
        for group in GroupByBook(references): # Only one excerpt per book
            if len(group) > 1 and not group[0].IsSubreference():
                mainRef = group[1]
            else:
                mainRef = group[0]
            if isinstance(mainRef,TextReference):
                referenceDict[mainRef].append(excerpt)
            else:
                for authorRef in mainRef.MultipleAuthors():
                    referenceDict[authorRef].append(excerpt)

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

    def __init__(self,level: int,references: list[LinkedReference] = None):
        self.level = level
        self.page = Html.PageDesc()
        if references:
            self.references = references
            self.wholePage = True
            self.SetPageInfo(references[0].reference)
            self.page.AppendContent(self.HeaderHtml())
        else:
            self.references = []

    def SetPageInfo(self,fromReference: Reference) -> None:
        """Set the page information for this object; usually fromReference is the first reference in the list.
        Calls the general dispatch function below."""
        self.page.info = ReferencePageInfo(fromReference,self.level)

    def HeaderHtml(self,level = None) -> str:
        """Returns html that goes a the top of the page in whole page mode."""
        if level is None:
            level = self.level
        if level > 0:
            reference = self.references[0].reference.Truncate(level)
            bits = [reference.BreadCrumbs()]
            bits.extend("&nbsp;" + icon for icon in reference.LinkIcons())
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
        self.page.AppendContent(self.FooterHtml())
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

    if isinstance(text,TextReference):
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
    else:
        return html

class ExcerptListPage(ReferencePageMaker):
    """Generate a page containing the list of specified excerpts."""

    def RenderAndYieldSubpages(self) -> Iterator[Html.PageDesc]:
        a = Airium()
        formatter = Build.Formatter()
        formatter.SetHeaderlessFormat()
        firstLoop = True
        for reference in self.references:
            events,excerpts = Utils.Partition(reference.items,lambda item: "endDate" in item)
            for event in events:
                if not firstLoop:
                    a.hr()
                firstLoop = False
                a(Build.EventDescription(event,showMonth=True).replace("<p>","<p><b>Event</b>: "))
            if excerpts:
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
        return Utils.slugify(str(headingCode or self.groupCode).replace(".","-"))
    
    def BookmarkText(self,headingCode: HeadingGroupCode = None) -> str:
        """Returns the text in the bookmark menu at the top of the page which links to this heading code."""
        return str(headingCode or self.groupCode)
    

class SingleLevelHeadings(Heading):
    """A class that groups references at a specific level. 
    The base class generates headers with the name of each level."""

    level: int              # The heading level; level 0 groups by sutta (all MN together)
                            # level 1 groups by sutta and the first number (all MN 2 together)
    topOfPage: bool = True  # Flag to mark the top of the page

    def __init__(self,level):
        self.level = level

    def HeadingCode(self,reference: Reference) -> Reference:
        """The heading code is simply the truncated reference."""
        header = reference.Truncate(self.level + 1)
        groupHeader = ConsecutiveTexts.FromReference(header)
        return groupHeader or header
    
    def Html(self, headingCode:Reference = None) -> str:
        headingCode = headingCode or self.groupCode
        name = headingCode.FullName()
        if isinstance(headingCode,TextReference):
            traslatedTitle = Suttaplex.Title(headingCode.Uid())
            if traslatedTitle:
                name += f": {traslatedTitle}"
        prefix = "" if self.topOfPage else "<hr>\n"
        self.topOfPage = False
        return prefix + Html.Tag("div",{"class":"title","id":self.Bookmark()})(name)
    
    def BookmarkText(self, headingCode = None):
        headingCode = headingCode or self.groupCode
        headingCode = headingCode.Truncate(self.level + 1)
        return headingCode.TextTitle()

class LinkedHeadings(SingleLevelHeadings):
    """Generates a list of links to subpages."""
    enclosingClass = "listing"
    
    def Html(self, headingCode:Reference = None) -> str:
        headingCode = headingCode or self.groupCode
        subPageInfo = ReferencePageInfo(headingCode,self.level + 1)
        thisReference = headingCode.Truncate(self.level + 1)
        link = Html.Tag("a",{"href":Utils.PosixJoin("../",subPageInfo.file)})
        if self.level == 0 or isinstance(headingCode,BookReference):
            name = link(thisReference.FullName())
        else:
            name = link(str(thisReference))
            if isinstance(thisReference,TextReference):
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
    bookmarkMenu: Html.Menu|None         # The bookmark menu at the top of the page

    def __init__(self,heading: Heading,content: ReferencePageMaker,references: list[LinkedReference],bookmarkLinks: bool = False):
        """If bookmarks is True, add bookmarks at the top of the page that link to the headings below."""
        super().__init__(content.level,references)
        self.heading = heading
        self.content = content
        if bookmarkLinks:
            self.bookmarkMenu = Html.Menu([],wrapper = Html.Wrapper("","<hr>"))
            self.page.AppendContent(self.bookmarkMenu)
        else:
            self.bookmarkMenu = None

    def RenderAndYieldSubpages(self) -> Iterator[Html.PageDesc]:
        a = Airium()
        with a.div(Class=self.heading.enclosingClass):
            for referenceGroup in self.heading.GroupedReferences(self.references):
                a(self.heading.Html())
                self.content.AppendReferences(referenceGroup)
                yield from self.content.RenderAndYieldSubpages()
                a(self.content.YieldHtml())

                if self.bookmarkMenu:
                    self.bookmarkMenu.items.append(Html.PageInfo(
                        self.heading.BookmarkText(),
                        "#" + self.heading.Bookmark()
                    ))

        self.page.AppendContent(str(a))
        yield from super().RenderAndYieldSubpages()
    
    def FinishPage(self):
        if self.bookmarkMenu and len(self.bookmarkMenu.items) < 2:
            self.bookmarkMenu.items = []    # Remove the bookmark menu if there is only one item in it.
            self.bookmarkMenu.menu_wrapper = Html.Wrapper()
        return super().FinishPage()
        

def ReferencePageInfo(firstRef: Reference,level: int) -> Html.PageInfo:
    """Return the page information for a given page of references."""

    if isinstance(firstRef,TextReference):
        text = firstRef.text
        if level == 0:
            if text in TextGroupSet("vinaya"):
                return Html.PageInfo("Vinaya","texts/Vinaya.html","References – Vinaya")
            else:
                return Html.PageInfo("Sutta","texts/Sutta.html","References – Suttas")
        
        referenceGroup = firstRef.Truncate(level)
        referenceGroup = ConsecutiveTexts.FromReference(referenceGroup) or referenceGroup
            # Check to see if this reference falls into a group of consecutive texts
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
    else:
        directory = "books/"
        if level == 0:
            if firstRef.IsCommentary():
                return Html.PageInfo("Commentary","books/Commentary.html","References – Commentary")
            else:
                return Html.PageInfo("Modern","books/Modern.html","References – Modern Authors")
        elif level == 1: # An author page
            author = firstRef.author
            if not author:
                author = "various"
            authorName = gDatabase["teacher"][author]["attributionName"]

            return Html.PageInfo(
                Utils.CapitalizeFirst(authorName),
                f"{directory}{author}.html",
                f"References – {authorName}"
            )
        elif level == 2: # A book page
            title = firstRef.Truncate(level).FullName()
            return Html.PageInfo(
                Utils.CapitalizeFirst(Utils.RemoveHtmlTags(title)),
                f"{directory}{Utils.slugify(firstRef.abbreviation)}.html",
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

    skipLevel = False
    bookmarkLinks = False

    def TextDispatch() -> PageType:
        if level == 0:
            return PageType.LINKED_HEADINGS
        
        textLevel = references[0].reference.TextLevel() + 1

        if textLevel == 1:
            return PageType.EXCERPTS_WITH_HEADINGS

        if level < textLevel and TotalItems(references) >= gOptions.minSubsearchExcerpts:
            return PageType.LINKED_HEADINGS
        else:
            if level < textLevel:
                return PageType.EXCERPTS_WITH_HEADINGS
            else:
                return PageType.EXCERPTS_ONLY
    
    def BookDispatch() -> PageType:
        nonlocal skipLevel,bookmarkLinks
        if level == 0:
            if references[0].reference.IsCommentary():
                skipLevel = True # Skip the list of authors for commentarial works.
            return PageType.LINKED_HEADINGS
        elif level == 1:
            if TotalItems(references) < gOptions.minSubsearchExcerpts:
                bookmarkLinks = True
                return PageType.EXCERPTS_WITH_HEADINGS
            else:
                return PageType.LINKED_HEADINGS
        else:
            return PageType.EXCERPTS_ONLY

    pageType = TextDispatch() if isinstance(references[0].reference,TextReference) else BookDispatch()
    if pageType == PageType.LINKED_HEADINGS:
        if skipLevel:
            level += 1
        pageMaker = PageWithHeadings(LinkedHeadings(level),YieldSubpages(level),references)
        if skipLevel: # If we skip a level of headings, manually remake the page header
            pageMaker.page = Html.PageDesc(ReferencePageInfo(references[0].reference,level - 1))
            pageMaker.page.AppendContent(pageMaker.HeaderHtml(level - 1))
        return pageMaker
    elif pageType == PageType.EXCERPTS_WITH_HEADINGS:
        return PageWithHeadings(SingleLevelHeadings(level),ExcerptListPage(level),references,bookmarkLinks)
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

    bookReferences = CollateReferences("books")
    commentaryRefs,modernRefs = Utils.Partition(bookReferences,lambda r:r.reference.IsCommentary())
    WriteReferences(bookReferences,"BookReferences.txt")

    return [
        Build.YieldAllIf(FirstLevelMenu(suttaRefs),"texts" in gOptions.buildOnly),
        Build.YieldAllIf(FirstLevelMenu(vinayaRefs),"texts" in gOptions.buildOnly),
        Build.YieldAllIf(FirstLevelMenu(commentaryRefs),"books" in gOptions.buildOnly),
        Build.YieldAllIf(FirstLevelMenu(modernRefs),"books" in gOptions.buildOnly)
    ]

def ReferencesMenu() -> Html.PageDescriptorMenuItem:
    """Create the References menu item and its associated submenus."""

    referencesMenu = TextMenu()
    yield Html.PageInfo("References","texts/Sutta.html")

    baseTagPage = Html.PageDesc()
    yield from baseTagPage.AddMenuAndYieldPages(referencesMenu,**Build.SUBMENU_STYLE)
    