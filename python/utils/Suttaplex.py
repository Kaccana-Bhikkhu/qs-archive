"""Utility functions for reading SuttaCentral's .json sutta index files.
Run this module as a standalone script to process the files in sutta/suttaplex/raw into sutta/suttaplex/reduced.
Then import the module to query the reduced .json files."""

from __future__ import annotations

import os, sys, json
from collections import Counter

scriptDir,_ = os.path.split(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(scriptDir,'python/modules'))
sys.path.append(os.path.join(scriptDir,'python/utils'))
import Utils

def ReduceRawSuttaplexFiles():
    """Read the suttaplex json files in sutta/suttaplex/raw. Eliminate non-English translations and
    write the output into sutta/suttaplex/reduced."""

    rawDir = "sutta/suttaplex/raw"
    reducedDir = "sutta/suttaplex/reduced"
    os.makedirs(reducedDir,exist_ok=True)
    for filename in sorted(os.listdir(rawDir)):
        sourcePath = Utils.PosixJoin(rawDir,filename)
        if not os.path.isfile(sourcePath) or not filename.endswith(".json"):
            continue

        with open(sourcePath, 'r', encoding='utf-8') as file:
            suttaplex = json.load(file)
        
        reduced = [s for s in suttaplex if s.get("translations")]
        translationCount = Counter()

        keepKeys = {"acronym","uid","original_title","translated_title","translations","priority_author_uid","verseNo"}
        keepTranslationKeys = {"author","author_short","author_uid","id","title"}
        for sutta in reduced:
            for key in list(sutta):
                if key not in keepKeys:
                    del sutta[key]

            sutta["translations"] = [s for s in sutta["translations"] if s["lang"] == "en"]
            for translation in sutta["translations"]:
                translationCount[translation["author_uid"]] += 1
                for key in list(translation):
                    if key not in keepTranslationKeys:
                        del translation[key]

        mostCommon = sorted(translationCount.items(),key = lambda item:-item[1])
        print("Text:",filename.removesuffix(".json"),"Sutta count:",len(reduced),"Translations:",mostCommon)

        hasVerses = reduced[0]["verseNo"]
        if hasVerses:
            print("   This text has verse numbers.")

        destPath = Utils.PosixJoin(reducedDir,filename)
        with open(destPath, 'w', encoding='utf-8') as file:
            json.dump(reduced,file,ensure_ascii=False,indent=2)
            

if __name__ == "__main__":
    ReduceRawSuttaplexFiles()