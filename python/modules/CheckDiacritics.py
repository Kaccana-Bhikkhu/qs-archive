"""Flag multiple variants of words with diacritics, e.g. Pāli and Pali.
Write the following files to documentation/diacritics:
DiacriticFrequency.json: The frequency of different forms of each word
CorrectDiacritics.csv: Initially lists all forms of each word. Remove incorrect forms from the file.
DiacriticEdits.txt: Instructions to change incorrect diacritcs to correct diacritics
"""

from __future__ import annotations

import os, re, json
import Utils, Alert, Link, FileRegister
from typing import Iterable
from collections import Counter,defaultdict
import Render

def ReadCorrectForms() -> None:
    """Read CorrectDiacritics.csv into gCorrectDiacritics."""

    try:
        with open("documentation/diacritics/CorrectDiacritics.csv",encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                words = line.split(",")
                if not words or not words[0]:
                    continue
                words = [w.strip("*") for w in words]
                gCorrectDiacritics[Utils.RemoveDiacritics(words[0])] = words
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
            if word not in gCorrectDiacritics[plain]:
                Alert.caution(item,"has incorrect form",repr(word))

    return None # Don't change anything

def TagAndTeacherWords() -> dict[str,set[str]]:
    """Return a dict of words used in tag and teacher names. We assume these use diacritics correctly.
    For example, words['dhamma'] = {'dhamma','dhammā'}"""

    words:dict[str,set[str]] = defaultdict(set)

    def AddWords(text: str,item: dict) -> None:
        """Add these words to the"""
        text = Utils.RemoveHtmlTags(text)
        for word in re.findall(r"\b\w+\b",text):
            word = word.lower()
            plain = Utils.RemoveDiacritics(word)
            if not plain:
                continue
            words[plain].add(word)
            """if len(plainWords[plain]) > 1:
                Alert.notice(item,"has a differnt form",plainWords[plain])"""

    for tag in gDatabase["tag"].values():
        for key in ("tag","fullTag","pali","fullPali"):
            AddWords(tag[key],tag)
    for teacher in gDatabase["teacher"].values():
            for key in ("fullName","attributionName"):
                AddWords(teacher[key],teacher)

    """for plain,allForms in plainWords.items():
        if len(allForms) > 1:
            Alert.notice("Multiple forms in tag/teacher names:",allForms)"""

    return words

def UpdateCorrectDiacritics(sortedFrequency: dict[str,dict[str,int]]) -> None:
    """Write or update CorrectDiacritics.csv based on the diacritics we have found in the database"""
    tagAndTeacherForms = TagAndTeacherWords()

    with open("documentation/diacritics/CorrectDiacritics.csv", 'w', encoding='utf-8') as file:
        for plainWord,forms in sortedFrequency.items():
            cannonicalForms = [f for f in forms if f in tagAndTeacherForms[plainWord]]
            if len(cannonicalForms) in (0,len(forms)):
                print(",".join(sortedFrequency[plainWord]),file = file)
            else: # Add "*" after potentially suspicious forms
                cannonicalStr = ",".join(cannonicalForms)
                nonCannonicalStr = "*,".join(f for f in forms if f not in cannonicalForms)
                print(f"{cannonicalStr},{nonCannonicalStr}*",file=file)

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--updateCorrectDiacritics',**Utils.STORE_TRUE,help="Add new words at the end of CorrectDiacritics.csv")
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

gCorrectDiacritics:dict[str,list[str]] = {}

def main() -> None:
    ReadCorrectForms()
    Render.ApplyToBodyText(BuildDiacriticDatabase)

    sortedFrequency = {word:freq for word,freq in sorted(gDiacriticFrequency.items())}
    os.makedirs("documentation/diacritics",exist_ok=True)
    with open("documentation/diacritics/DiacriticFrequency.json", 'w', encoding='utf-8') as file:
        json.dump(sortedFrequency, file, ensure_ascii=False, indent=2)

    if gOptions.updateCorrectDiacritics:
        UpdateCorrectDiacritics(sortedFrequency)


    