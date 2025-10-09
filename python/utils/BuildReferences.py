"""Functions that build pages/texts and pages/references.
These could logically be included within Build.py, but this file is already unweildy due to length."""

from collections.abc import Iterable
from collections import defaultdict
from typing import NamedTuple
from dataclasses import dataclass
from itertools import groupby
import json, re, itertools
import Html2 as Html
import Utils
import Database
import Alert
import Filter
import ParseCSV
import Link
import Build
from functools import lru_cache

gOptions = None
gDatabase:dict[str] = {} # These will be set later by QSarchive.py

@lru_cache(maxsize=None)
def TextSortOrder() -> dict[str,int]:
    """Return the sort order of the texts."""
    return {text:n for n,text in enumerate(gDatabase["text"])}

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
        numbers = (int(n) for n in (matchObject[2],matchObject[3],matchObject[4]) if n)
        text = "Kd" if matchObject[1] == "Mv" else matchObject[1] # Mv is equivalent to Kd
        return TextReference(text,*numbers)

    def Numbers(self) -> tuple[int,int,int]:
        """Return a tuple of the reference numbers"""
        return tuple(int(n) for n in self[1:] if n)

    def SortKey(self) -> tuple:
        """Return a tuple to sort these texts by."""
        return (TextSortOrder()[self.text],) + self.Numbers()

    def __str__(self):
        return f"{self.text} {'.'.join(map(str,self.Numbers()))}"
    
Reference = TextReference

@dataclass
class LinkedReference():
    reference: Reference            # The refererence itself
    items: list[dict[str]]          # A list of events and excerpts that reference it


def CollateReferences(referenceKind: str) -> list[LinkedReference]:
    """Read the references stored in gDatabase and return a sorted list of LinkedReference objects.
    referenceKind is either 'texts' or 'books'."""

    referenceDict:dict[Reference,list[dict[str]]] = defaultdict(list)

    for event in gDatabase["event"].values():
        for ref in event.get(referenceKind,()):
            referenceDict[TextReference.FromString(ref)].append(event)
    for excerpt in gDatabase["excerpts"]:
        for ref in excerpt.get(referenceKind,()):
            referenceDict[TextReference.FromString(ref)].append(excerpt)

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

def HierarchicalReferencePages(references:list[LinkedReference]) -> Html.PageDescriptorMenuItem:
    """Return a series of pages that link references to where they occur in the Archive."""

    return "This is a placeholder."

def TextMenu() -> Html.PageDescriptorMenuItem:
    """Return a list containing the sutta and vinaya reference pages."""

    textReferences = CollateReferences("texts")
    WriteReferences(textReferences,"TextReferences.txt")

    suttaInfo = Html.PageInfo("Sutta","texts/Sutta.html","References – Suttas")
    vinayaInfo = Html.PageInfo("Vinaya","texts/Vinaya.html","References – Vinaya")

    return [
        [suttaInfo,HierarchicalReferencePages([])],
        [vinayaInfo,HierarchicalReferencePages([])]
    ]

def ReferencesMenu() -> Html.PageDescriptorMenuItem:
    """Create the References menu item and its associated submenus."""

    referencesMenu = TextMenu()
    yield referencesMenu[0][0]._replace(title="References")

    baseTagPage = Html.PageDesc()
    yield from baseTagPage.AddMenuAndYieldPages(referencesMenu,**Build.SUBMENU_STYLE)
    