"""Download csv files from Google sheet WR2025 readings and parse them into AP QS Archive excerpt format."""

import sys, os, re
import argparse
import unicodedata
from typing import TypedDict,DefaultDict
from csv import DictReader,writer

scriptDir,_ = os.path.split(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(scriptDir,'../../../python/modules'))
sys.path.append(os.path.join(scriptDir,'../../../python/utils'))
import DownloadCSV, Utils

os.chdir("audio/sessionsNoUpload/WR2025")

class ConcordanceEntry(TypedDict):
    "Corresponds to a row in Processed.csv"
    chapter: int
    passage: int
    rawCitation: str
    editedCitation: str
    reference: str
    rawSutta: str
    sutta: str

class SessionEntry(TypedDict):
    "Corresponds to a row in Sessions.csv "
    session: int
    teacher: str
    chapter: int
    pageRange: str
    firstPassage: int
    lastPassage: int
    extraReading: bool

    @staticmethod
    def fromDict(d:dict) -> "SessionEntry":
        return {key:(value if key in ("pageRange","teacher") 
                     else (value.startswith("Yes") if key == "extraReading" 
                           else int(value))) for key,value in d.items()}
        

def ExcerptLineDict(session:int,kind:str = "",flags:str = "",startTime:str = "",text:str = "",teachers:str = ""):
    """Return a dict describing the first rows of the AP QS Archive excerpt sheet"""
    return {
        "Session #": str(session),
        "Kind": kind,
        "Flags": flags,
        "Start time": startTime,
        "End time": "",
        "Text": text,
        "Teachers": teachers
    }

def DownloadSheets():
    DownloadCSV.gOptions = Utils.gOptions = options
    DownloadCSV.ParseArguments()

    sheets = {
        "Processed": 21026486,
        "Sessions": 609110514
    }
    DownloadCSV.DownloadSheets(sheets,None)

def ReadConcordance() -> dict[int,dict[int,ConcordanceEntry]]:
    concordance:dict[int,dict[int,ConcordanceEntry]] = DefaultDict(lambda: DefaultDict(dict))
    with open("Processed.csv",encoding='utf8') as file:
        for line in DictReader(file):
            chapter = line["chapter"] = int(line["chapter"])
            passage = line["passage"] = int(line["passage"])
            concordance[chapter][passage] = line
    return concordance

def WriteExcerptCSV(concordance: dict[int,dict[int,ConcordanceEntry]]):
    "Write the excerpts.csv file based on the content of Sessions.csv and concordance."
    with (open("Sessions.csv",encoding='utf8') as sessionFile,
          open("excerpts.csv","w",encoding='utf8', newline='',) as outputFile):
        outputCSV = writer(outputFile,delimiter="\t")
        outputCSV.writerow(ExcerptLineDict(0).keys())
        for session in DictReader(sessionFile):
            session = SessionEntry.fromDict(session)
            
            indent = ""
            firstPage = session["pageRange"].split("-")[0]
            islandReading = ExcerptLineDict(
                session = session["session"],
                kind = "Reading",
                flags = "s:" if session["lastPassage"] - session["firstPassage"] > 0 else ":",
                startTime = "Session",
                text = f"[The Island](), Chapter {session['chapter']}, pp. [{session['pageRange']}](The Island p. {firstPage})."
            )

            if session["extraReading"]:
                # If there are additional readings, the Island reading becomes an annotation to a Reading group session excerpt
                outputCSV.writerow(ExcerptLineDict(
                    session = session["session"],
                    kind = "Reading group",
                    startTime = "Session",
                    text = ""
                ).values())
                islandReading["Start time"] = ""
                islandReading["Flags"] += "2"
                indent = "-"
            else:
                islandReading["Text"] = "from " + islandReading["Text"]

            outputCSV.writerow(islandReading.values())

            readings:dict[str|int,list] = DefaultDict(list)
            for passageNumber in range(session["firstPassage"],session["lastPassage"] + 1):
                passage = concordance[session["chapter"]][passageNumber]
                if passage["reference"]: # Each reference gets its own line
                    refText = re.sub(r"‘([^’]*)’(?!.*‘)",r"_\1_",passage["reference"])
                    refText = refText.replace(",_","_,")
                    readings[len(readings)] = [refText]
                elif passage["sutta"]: # Concatenate suttas and vinaya texts
                    readings["Vinaya" if "Mv" in passage["sutta"] else "Sutta"].append(passage["sutta"])
            
            for kind,texts in readings.items():
                if type(kind) == int:
                    outputCSV.writerow(ExcerptLineDict(
                        session = session["session"],
                        kind = "Reading",
                        flags = "2" + indent,
                        text = texts[0] + "."
                    ).values())
                else:
                    outputCSV.writerow(ExcerptLineDict(
                        session = session["session"],
                        kind = kind,
                        flags = ("s" if kind == "Sutta" and len(texts) > 1 else "") + indent,
                        text = "; ".join(texts) + "."
                    ).values())
            
            if session["extraReading"]:
                # Add a template additional reading
                outputCSV.writerow(ExcerptLineDict(
                    session = session["session"],
                    kind = "Reading",
                    flags = "2",
                    text = "xxxxx"
                ).values())


parser = argparse.ArgumentParser(description="""Download csv files from Google sheet WR2025 readings and parse them into AP QS Archive excerpt format.""")
parser.add_argument('--spreadsheet',type=str, default = 'https://docs.google.com/spreadsheets/d/1ikMYrcw-Ro0NIr3X462ZOr-ZOIrHW9ZJ-Jxf3m26YuY/', help='URL of the WR2025 Google Sheet')
parser.add_argument('--multithread',**Utils.STORE_TRUE,help="Multithread some operations")
parser.add_argument('--noDownload',**Utils.STORE_TRUE,help="Skip the download step")

options = parser.parse_args(sys.argv[1:])

if not options.noDownload:
    DownloadSheets()

concordance = ReadConcordance()

WriteExcerptCSV(concordance)
