"""Flag multiple variants of words with diacritics, e.g. Pāli and Pali.
Write the following files to documentation/diacritics:
DiacriticFrequency.json: The frequency of different forms of each word
CorrectDiacritics.csv: Initially lists all forms of each word. Remove incorrect forms from the file.
DiacriticEdits.txt: Instructions to change incorrect diacritcs to correct diacritics
"""

from __future__ import annotations

import os, re, json
import Utils, Alert, Link, FileRegister
from typing import Callable
from collections import Counter,defaultdict
import Render

def ReadCorrectForms() -> None:
    """Read CorrectDiacritics.csv gCorrectDiacritics and gCannonicalDiacritics."""

    try:
        with open(Utils.PosixJoin(gOptions.diacriticsDir,"CorrectDiacritics.csv"),encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                words = line.split(",")
                if not words or not words[0]:
                    continue
                plainForm = Utils.RemoveDiacritics(words[0].strip("*"))

                cannonicalWords = [w for w in words if not w.endswith("*")]
                gCannonicalDiacritics[plainForm] = cannonicalWords

                words = [w.strip("*") for w in words]
                gCorrectDiacritics[plainForm] = words
    except FileNotFoundError:
        pass


def BuildDiacriticDatabase(text:str,item:dict) -> str:
    """Add the text from a single item to the diacritic databases."""

    text = Utils.RemoveHtmlTags(text)
    for word in re.findall(r"\b\w+\b",text):
        word = word.lower()
        plain = Utils.RemoveDiacritics(word)
        if not plain:
            continue
        if plain in gDiacriticFrequency or word != plain:
            if plain not in gDiacriticFrequency and plain in gPlainWords:
                gDiacriticFrequency[plain][plain] = gPlainWords[plain]
            gDiacriticFrequency[plain][word] += 1
        else:
            gPlainWords[word] += 1

        if plain in gCorrectDiacritics:
            correctForms = gCorrectDiacritics[plain]
            if word not in correctForms:
                Alert.caution(item,"has incorrect form",repr(word),"->",correctForms[0] if len(correctForms) == 1 else correctForms)
                if len(correctForms) == 1:
                    gCorrections[word] = correctForms[0]
        elif word != plain and not gOptions.newCorrectDiacritics:
            Alert.notice(item,"has new diacritic form",repr(word))

    return None # Don't change the text

def ApplyToTags(transform: Callable[...,tuple[str,int]|str]) -> None:
    for tag in gDatabase["tag"].values():
        for key in ("tag","fullTag","pali","fullPali"):
            transform(tag[key],tag)
    for teacher in gDatabase["teacher"].values():
        for key in ("fullName","attributionName"):
            transform(teacher[key],teacher)
    for ref in gDatabase["reference"].values():
        transform(ref["title"].replace("_",""),ref)
        transform(ref["attribution"],ref)

def ApplyToDocumentation(transform: Callable[...,tuple[str,int]|str]) -> None:
    documentationDirs = ("aboutSources","technicalSources","miscSources","tableOfContents")
    for dir in documentationDirs:
        for filename in sorted(os.listdir(Utils.PosixJoin(gOptions.documentationDir,dir))):
            if not filename.endswith(".md"):
                continue
            with open(Utils.PosixJoin(gOptions.documentationDir,dir,filename),encoding="utf-8") as file:
                for n,line in enumerate(file,start=1):
                    line = Utils.RemoveMarkdownHyperlinks(line)
                    line = re.sub(r"`[^`]*`","",line) # Remove code blocks
                    transform(line,f"{filename} line {n}: '{Utils.EllideText(line)}'")
                    

def UpdateCorrectDiacritics(sortedFrequency: dict[str,dict[str,int]]) -> None:
    """Write or update CorrectDiacritics.csv based on the diacritics we have found in the database"""
    with open(Utils.PosixJoin(gOptions.diacriticsDir,"CorrectDiacritics.csv"), 'w', encoding='utf-8') as file:
        for plainWord,forms in sortedFrequency.items():
            if plainWord in gCorrectDiacritics and not gOptions.newCorrectDiacritics:
                forms = gCorrectDiacritics[plainWord]
                cannonicalForms = gCannonicalDiacritics[plainWord]
            else:
                cannonicalForms = [f for f in forms if f in gTagAndTeacherForms[plainWord]]
            if len(cannonicalForms) in (0,len(forms)):
                print(",".join(sortedFrequency[plainWord]),file = file)
            else: # Add "*" after potentially suspicious forms
                cannonicalStr = ",".join(cannonicalForms)
                nonCannonicalStr = "*,".join(f for f in forms if f not in cannonicalForms)
                print(f"{cannonicalStr},{nonCannonicalStr}*",file=file)

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--newCorrectDiacritics',**Utils.STORE_TRUE,help="Overwrite CorrectDiacritics.csv")
    parser.add_argument('--updateCorrectDiacritics',**Utils.STORE_TRUE,help="Add new words to CorrectDiacritics.csv")
    pass

def ParseArguments() -> None:
    pass
    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy

# Counts how many of each form of a diacritic there are, e. g.
# {'pali': {'pāli': 8,'pali': 1}} indicates that 'pāli' appears 8 times and 'pali' once.
gDiacriticFrequency:dict[str,dict[str,int]] = defaultdict(Counter)

# Counts plain words not yet incorporated into gDiacriticFrequency
gPlainWords = Counter()

# A dictionary read from CorrectDiacritics.csv indicating the allowable forms
gCorrectDiacritics:dict[str,list[str]] = {}

# Forms found in teacher, tag, and book names
gTagAndTeacherForms: dict[str,set[str]] = {}
# The forms in gCorrectDiacritics that are found in gTagAndTeacherForms
gCannonicalDiacritics:dict[str,list[str]] = {}

# gCorrections[incorrectForm] = correctForm
gCorrections:dict[str,str] = {}

def main() -> None:
    gOptions.diacriticsDir = Utils.PosixJoin(gOptions.documentationDir,"diacritics")

    ReadCorrectForms()
    if not gCorrectDiacritics:
        Alert.info("CorrectDiacritics.csv not found. Will remake this file.")
        gOptions.newCorrectDiacritics = True
    
    cautionCount = Alert.caution.count
    noticeCount = Alert.notice.count
    ApplyToTags(BuildDiacriticDatabase)

    global gTagAndTeacherForms
    gTagAndTeacherForms = {plain:set(forms) for plain,forms in gDiacriticFrequency.items()}

    Render.ApplyToBodyText(BuildDiacriticDatabase)
    ApplyToDocumentation(BuildDiacriticDatabase)
    Alert.info(Alert.caution.count - cautionCount,"mismatched diacritic(s) found.")
    Alert.info(Alert.notice.count - noticeCount,"new diacritic form(s) found.")

    sortedFrequency = {word:freq for word,freq in sorted(gDiacriticFrequency.items())}
    os.makedirs(gOptions.diacriticsDir,exist_ok=True)
    with open(Utils.PosixJoin(gOptions.diacriticsDir,"DiacriticFrequency.json"), 'w', encoding='utf-8') as file:
        json.dump(sortedFrequency, file, ensure_ascii=False, indent=2)

    if gOptions.newCorrectDiacritics or gOptions.updateCorrectDiacritics:
        if gOptions.updateCorrectDiacritics:
            for plainWord,forms in gCorrectDiacritics.items():
                sortedFrequency[plainWord] = dict.fromkeys(forms,0) | (sortedFrequency.get(plainWord) or {})
            sortedFrequency = {word:freq for word,freq in sorted(sortedFrequency.items())}
        UpdateCorrectDiacritics(sortedFrequency)
        Alert.info("CorrectDiacritics.csv updated.")

    with open(Utils.PosixJoin(gOptions.diacriticsDir,"CorrectionRegexps.tsv"), 'w', encoding='utf-8') as file:
        for findWord,replaceWord in sorted(gCorrections.items()):
            if findWord[0] == replaceWord[0]:
                findRegexp = f"([{findWord[0]}{findWord[0].upper()}]){findWord[1:]}"
                replaceRegexp = f"$1{replaceWord[1:]}"
                print("\t".join((Utils.WholeWordRegexp(findRegexp),replaceRegexp)),file=file)
            else:
                print("\t".join((Utils.WholeWordRegexp(findWord),replaceWord)),file=file)
                print("\t".join((Utils.WholeWordRegexp(Utils.CapitalizeFirst(findWord)),
                                 Utils.CapitalizeFirst(replaceWord))),file=file)


    