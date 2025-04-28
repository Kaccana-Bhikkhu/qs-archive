"""A module that implements filters for events, sessions, excerpts, and annotations."""

from __future__ import annotations

from collections.abc import Iterable, Callable, Iterator
from typing import Any, Tuple
import Utils, ParseCSV
import copy

gDatabase:dict[str] = {} # This will be overwritten by the main program

class InverseSet:
    """A class which contains everything except the objects in self.inverse"""
    inverse: set

    def __init__(self,inverse = None):
        if inverse is None:
            self.inverse = set()
        else:
            self.inverse = inverse
    
    def __contains__(self,item):
        return item not in self.inverse
    
    def __repr__(self):
        return f"InverseSet({repr(self.inverse)})"

All = InverseSet(frozenset())

def FrozenSet(item:str|Iterable[str]) -> set[str]:
    """Intelligently converts a string or iterable a frozenset."""
    if type(item) == str:
        return {item}
    elif type(item) not in (frozenset,InverseSet):
        return frozenset(item)
    else:
        return item

def AllItems(excerpt: dict) -> Iterator[dict]:
    """If this is an excerpt, iterate over the excerpt and annotations.
    If not, iterate just this item."""

    yield excerpt
    yield from excerpt.get("annotations",())

def AllSingularItems(excerpt: dict) -> Iterator[dict]:
    """Same as AllItems, but yield the excerpt alone without its annotations, followed by the annotations."""

    if excerpt.get("annotations",None):
        temp = copy.copy(excerpt)
        temp["annotations"] = ()
        yield temp
        yield from excerpt["annotations"]
    else:
        yield excerpt

class Filter:
    """A filter for excerpts and other dicts.
    Subclasses provide the necessary details."""

    def __init__(self) -> None:
        self.negate:bool = False
    
    def Not(self) -> Filter:
        "Modify this filter to reject what it used to pass and vice-versa."
        self.negate = not self.negate
        return self

    def Match(self,item: dict) -> bool:
        "Return True if this filter passes item."
        return not self.negate
    
    def Count(self,items: Iterable[dict]) -> int:
        "Return the number of items that pass this filter"
        return sum(1 for item in items if self.Match(item))

    def Apply(self,items: Iterable[dict]) -> Iterator[dict]:
        "Return an iterator over items that pass this filter. "
        return (item for item in items if self.Match(item))
    
    def __call__(self,items: Iterable[dict]|list[dict]) -> Iterator[dict]|list[dict]:
        """Apply this filter to an iterable or list of items.
        Return an iterator or list depending on the input type."""
        filteredItems = self.Apply(items)
        if type(items) == list:
            return list(filteredItems)
        else:
            return filteredItems
    
    def Indexes(self,items: Iterable[dict]) -> Iterator[int]:
        "Return the indices of items which pass this filter."
        return (n for n,item in enumerate(items) if self.Match(item))
    
    def Partition(self,items:Iterable[dict]) -> Tuple[list[dict],list[dict]]:
        "Split items into two lists depending on the filter function."

        trueList = []
        falseList = []

        for item in items:
            (trueList if self.Match(item) else falseList).append(item)
        
        return trueList,falseList
    
    def FilterAnnotations(self,excerpt: dict[str]) -> dict[str]:
        """Return an excerpt with only annotations that pass this filter.
        Returns excerpt itself if all annotations pass."""

        newAnnotations = [a for a in excerpt["annotations"] if self.Match(a)]
        if len(newAnnotations) < len(excerpt["annotations"]):
            newExcerpt = copy.copy(excerpt)
            newExcerpt["annotations"] = newAnnotations
            return newExcerpt
        else:
            return excerpt


"Returns whether the dict matches our filter function."

PassAll = Filter()
PassNone = Filter().Not()

class Tag(Filter):
    "A filter that passes items containing a particular tag."

    def __init__(self,passTags:str|Iterable[str]) -> None:
        super().__init__()
        self.passTags = FrozenSet(passTags)
    
    def Match(self, item: dict) -> bool:
        for i in AllItems(item):
            for t in i.get("tags",()):
                if t in self.passTags:
                    return not self.negate
        
        return self.negate

class FTag(Tag):
    "A filter that passes excerpts containing particular featured tags."

    def Match(self, item: dict) -> bool:        
        for t in item.get("fTags",()):
            if t in self.passTags:
                return not self.negate
        
        return self.negate

class ClusterFTag(Filter):
    "A filter that passes excerpts that should be featured on a cluster page."

    def __init__(self,cluster:str) -> None:
        super().__init__()
        self.cluster = cluster
        self.passTags = FrozenSet([cluster] + list(gDatabase["subtopic"][cluster]["subtags"]))
    
    def Match(self, item: dict) -> bool:
        for n,t in enumerate(item.get("fTags",())):
            if t in self.passTags:
                flag = item["fTagOrderFlags"][n].upper()
                if len(self.passTags) == 1 or flag == ParseCSV.FTagOrderFlag.EVERYWHERE:
                    return not self.negate
                if flag == ParseCSV.FTagOrderFlag.PRIMARY_SUBTOPIC and not t in gDatabase["subtopic"][self.cluster].get("secondarySubtags",()):
                    return not self.negate
        
        return self.negate

class QTag(Tag):
    """A filter that passes items containing a particular qTag.
    Note that this Filter can take only a str as its argument."""
    
    def Match(self, excerpt: dict) -> bool:
        for index in range(excerpt["qTagCount"]):
            if excerpt["tags"][index] in self.passTags:
                return not self.negate

        return self.negate
    
class MaxFTagOrder(Filter):
    """A class that passes featured excerpts having fTagOrder less than a specified value."""

    def __init__(self,maxOrder:int) -> None:
        super().__init__()
        self.maxOrder = maxOrder
    
    def Match(self, excerpt: dict) -> bool:
        if not excerpt["fTags"]:
            return self.negate
        
        if min(excerpt["fTagOrder"]) > self.maxOrder:
            return self.negate
        else:
            return not self.negate
class Teacher(Filter):
    "A filter that passes items containing a particular tag."

    def __init__(self,passTeachers:str|Iterable[str],quotesOthers:bool = True,quotedBy:bool = True) -> None:
        super().__init__()
        self.passTeachers = FrozenSet(passTeachers)
        self.quotesOthers = quotesOthers
        self.quotedBy = quotedBy
    
    def Match(self, item: dict) -> bool:
        teacherNames = {gDatabase["teacher"][t]["attributionName"] for t in self.passTeachers}

        for i in AllItems(item):
            for t in i.get("teachers",()):
                if t in self.passTeachers:
                    if "kind" in i:
                        if i["kind"] != "Indirect quote" or self.quotesOthers:
                            return not self.negate
                    else:
                        return not self.negate

            if i.get("kind") == "Indirect quote" and self.quotedBy:
                if i.get("tags",None) and i["tags"][0] in teacherNames:
                    return not self.negate
                
        return self.negate

class Kind(Filter):
    "A filter that passes items of a particular kind."

    def __init__(self,passKinds:str|Iterable[str]) -> None:
        super().__init__()
        self.passKinds = FrozenSet(passKinds)
    
    def Match(self, item: dict) -> bool:
        for i in AllItems(item):
            if i["kind"] in self.passKinds:
                return not self.negate
        
        return self.negate

class Category(Filter):
    "A filter that passes excerpts of a particular category."

    def __init__(self,passCategories:str|Iterable[str]) -> None:
        super().__init__()
        self.passCategories = FrozenSet(passCategories)
    
    def Match(self, item: dict) -> bool:
        for i in AllItems(item):
            if gDatabase["kind"][i["kind"]]["category"] in self.passCategories:
                return not self.negate
        
        return self.negate

class Flags(Filter):
    """A filter that passes items which contain any of a specified list of flags.
    Does not match flags in annotations."""

    def __init__(self,passFlags:str) -> None:
        super().__init__()
        self.passFlags = passFlags
    
    def Match(self, item):
        if any(char in self.passFlags for char in item.get("flags","")):
            return not self.negate
    
        return self.negate

class FilterGroup(Filter):
    """A group of filters to operate on items using boolean operations.
    The default group passes items which match all filters e.g And."""

    def __init__(self,*subFilters:Filter):
        super().__init__()
        self.subFilters = subFilters
    
    def Match(self, item: dict) -> bool:
        for filter in self.subFilters:
            if not filter.Match(item):
                return self.negate
        
        return not self.negate
    
class And(FilterGroup):
    "Pass items which match all specified filters."
    pass

class Or(FilterGroup):
    "Pass items which match any of the specified filters."
    
    def Match(self, item: dict) -> bool:
        for filter in self.subFilters:
            if filter.Match(item):
                return not self.negate
        
        return self.negate

class SingleItemMatch(FilterGroup):
    "Pass excerpts for which the excerpt itself or a single annotation  matches all these conditions."
    
    def Match(self, item: dict) -> bool:
        for i in AllSingularItems(item):
            matchesAllFilters = True
            for filter in self.subFilters:
                if not filter.Match(i):
                    matchesAllFilters = False
        
            if matchesAllFilters:
                return not self.negate
        
        return self.negate

def MostRelevant(tags:str|Iterable[str]) -> Filter:
    "Return a filter that passes the most relevant excerpts for the given tag(s)."
    t = FrozenSet(tags)
    return Or(FTag(t),QTag(t),SingleItemMatch(Tag(t),Category(("Quotes","Stories"))))

def AllTags(item: dict) -> set:
    """Return the set of all tags in item, which is either an excerpt or an annotation."""
    allTags = set(item.get("tags",()))

    for annotation in item.get("annotations",()):
        allTags.update(annotation.get("tags",()))

    return allTags

def AllTagsOrdered(item: dict) -> list:
    """Return the set of all tags in item, which is either an excerpt or an annotation."""
    allTags = list(item["tags"])

    for annotation in item.get("annotations",()):
        Utils.ExtendUnique(allTags,annotation.get("tags",()))

    return allTags

def AllTeachers(item: dict) -> set:
    """Return the set of all teachers in item, which is either an excerpt or an annotation."""
    allTeachers = set(item.get("teachers",()))

    for annotation in item.get("annotations",()):
        allTeachers.update(annotation.get("teachers",()))

    return allTeachers