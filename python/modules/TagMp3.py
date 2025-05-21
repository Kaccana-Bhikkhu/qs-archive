"""Apply tags to mp3 excerpt files based on the information in RenderedDatabase.json.
We leave the session file tags untouched."""

from __future__ import annotations

import json, re, os
import Database
import Utils, Alert, Filter, Link, Build
from typing import Tuple, Type, Callable
from Mp3DirectCut import Clip
import mutagen
import mutagen.id3
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

def register_comment(desc='') -> None:
    """Register the comment tag using both UTF-16 and latin encodings.
    Tag choices based on Audacity mp3 encoder.
    Code based on https://www.extrema.is/blog/2021/08/04/comment-and-url-tags-with-mutagen."""
    frameid = ':'.join(('COMM', desc, '\x00\x00\x00'))
    frameidUTF16 = ':'.join(('COMM', desc, 'XXX'))

    def getter(id3, _key):
        frame = id3.get(frameidUTF16)
        if frame is not None:
            return list(frame)
        else:
            frame = id3.get(frame)
            if frame is not None:
                return list(frame)
            else:
                return None

    def setter(id3, _key, value):
        id3.add(mutagen.id3.COMM(
            encoding=1, lang='XXX', desc=desc, text=value))
        id3.add(mutagen.id3.COMM(
            encoding=0, lang='\x00\x00\x00', desc=desc, text=[Utils.RemoveDiacritics(t) for t in value]))

    def deleter(id3, _key):
        if frameid in id3:
            del id3[frameid]
        if frameidUTF16 in id3:
            del id3[frameidUTF16]

    def lister(id3, _key) -> list:
        if frameidUTF16 in id3 or frameid in id3:
            return ["comment"]
        else:
            return []

    EasyID3.RegisterKey('comment', getter, setter, deleter, lister)

def ReadID3(file: str) -> ID3:
    tags = ID3(file)
    return tags

def PrintID3(tags: ID3) -> None:
    print(tags)
    print('   ----')
    print(tags.pprint())
    print()

removeFromBody = "|".join([r"\{attribution[^}]*}",r"<[^>]*>"])
def ExcerptComment(excerpt:dict,session:dict,event:dict) -> str:
    "Write the comment for a given except"

    body = re.sub(removeFromBody,"",excerpt["body"]).strip()
    if not re.search(Utils.RegexMatchAny([".","?",'"',"'","”"],capturingGroup=False,literal=True) + "$",body):
        body += "."
    
    date = Utils.ReformatDate(session["date"],fullMonth=True) + ","
    
    parts = [body,date,Build.EventVenueStr(event) + "."]
    allTags = Filter.AllTagsOrdered(excerpt)
    if allTags:
        parts.append("Tag:" if len(allTags) == 1 else "Tags:")
        tagStrs = [f"[{t}]" for t in allTags]
        qTagCount = excerpt["qTagCount"]
        if 0 < qTagCount < len(tagStrs):
            tagStrs.insert(excerpt["qTagCount"],"//")
        parts += tagStrs
    
    firstClip = excerpt["clips"][0]
    source = f'Source: {firstClip.start} in file "{session["filename"] if firstClip.file == "$" else firstClip.file}"'
    parts.append(source)

    return " ".join(parts)

def ExcerptTags(excerpt: dict) -> dict:
    """Given an excerpt, return a dictionary of the id3 tags it should have."""
    event = gDatabase["event"][excerpt["event"]]
    session = Database.FindSession(gDatabase["sessions"],excerpt["event"],excerpt["sessionNumber"])

    sessionStr = f", Session {excerpt['sessionNumber']}" if excerpt['sessionNumber'] else ""
    returnValue = {
        "title": f"{event['title']}{sessionStr}, Excerpt {excerpt['excerptNumber']}",
        "albumartist": [gDatabase["teacher"][t]["attributionName"] for t in session["teachers"]],
        "artist": [gDatabase["teacher"][t]["attributionName"] for t in Filter.AllTeachers(excerpt)],
        "album": event["title"], # + sessionStr,
        "tracknumber": str(excerpt["excerptNumber"]),
        "date": str(Utils.ParseDate(session["date"]).year),
        "comment": ExcerptComment(excerpt,session,event),
        "genre": gDatabase["kind"][excerpt["kind"]]["category"],
        "copyright": f"© {gOptions.info.releaseYear} Abhayagiri Monastery; not for distribution outside the APQS Archive",
        "organization": "The Ajahn Pasanno Question and Story Achive",
        "website": f"https://abhayagiri.org/questions/events/{excerpt['event']}.html#{Database.ItemCode(excerpt)}",
    }

    if not returnValue["artist"]:
        returnValue["artist"] = ["Anonymous"]
    if not returnValue["albumartist"]:
        del returnValue["albumartist"]
    if excerpt["sessionNumber"] and excerpt["sessionNumber"] < 1000:
        returnValue["discnumber"] = str(excerpt["sessionNumber"])
    if session["sessionTitle"]:
        returnValue["discsubtitle"] = session["sessionTitle"]

    for key in list(returnValue):
        if type(returnValue[key]) == str:
            returnValue[key] = [returnValue[key]]
    
    return returnValue

def CompareTags(tagsToWrite:dict, existingTags:EasyID3) -> bool:
    "Compare tags to be written to existingTags. Return True if tags should be written to disk."

    existingTags = dict(existingTags)
    pluralKeys = ["artist","albumartist"]
    if gOptions.ID3version == 3:
        tagsToWrite.pop("discsubtitle",None) # ID3 v2.3 doesn't implement the discsubtitle tag
        for key in pluralKeys:
            if key in existingTags:
                existingTags[key] = existingTags[key][0].split("/")
    
    tagsToWriteCompare = tagsToWrite # Make a copy of tagsToWrite so we write the artists in proper order
    for key in pluralKeys: # Sort plural keys so comparison works properly.
        if key in existingTags:
            existingTags[key] = sorted(existingTags[key])
        if key in tagsToWrite:
            tagsToWriteCompare[key] = sorted(tagsToWriteCompare[key]) 

    return tagsToWriteCompare != existingTags

def TagMp3WithClips(mp3File: str,clips: list[Clip]):
    """Add an ID3 clips tag containing the contents of clips to mp3File."""
    try:
        fileTags = EasyID3(mp3File)
    except mutagen.id3.ID3NoHeaderError:
        fileTags = mutagen.File(mp3File,easy=True)
        fileTags.add_tags()

    fileTags["clips"] = json.dumps(clips)
    fileTags.save(v1=2,v2_version=gOptions.ID3version)

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument("--writeMp3Tags",type=str,default="Changed",choices=["never","changed","always"],help="Write mp3 tags under these conditions; Default: Changed.")
    parser.add_argument("--ID3version",type=int,default=3,choices=[3,4],help="Write mp3 tags as ID3 v2.X; Default: 3")

def ParseArguments() -> None:
    pass

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy
register_comment()

class CLIP(mutagen.id3.TextFrame):
    "List of clips"

mutagen.id3.Frames["CLIP"] = CLIP
EasyID3.RegisterTextKey("clips","CLIP")

def main() -> None:
    changeCount = sameCount = 0
    localMirrors = {"local",gOptions.uploadMirror}
    for x in gDatabase["excerpts"]:
        if gOptions.events != "All" and x["event"] not in gOptions.events:
            continue # Only tag mp3 files for the specifed events
        if not x["fileNumber"] or x["mirror"] not in localMirrors:
            continue # Ignore session excerpts and remote excerpts
        
        tags = ExcerptTags(x)

        path = Link.LocalFile(x)
        try:
            fileTags = EasyID3(path)
        except mutagen.id3.ID3NoHeaderError:
            fileTags = mutagen.File(path,easy=True)
            fileTags.add_tags()
            Alert.extra("Added tags to",path)

        if "clips" in fileTags: 
            tags["clips"] = fileTags["clips"]
            # The clips tag describes the audio source and is created by TagMp3.py; just let it pass through
        writeTags = CompareTags(tags,fileTags)

        if gOptions.writeMp3Tags == "never":
            if writeTags:
                Alert.extra("Would update tags in",path)
                changeCount += 1
                writeTags = False
            else:
                sameCount += 1
        elif gOptions.writeMp3Tags == "always":
            writeTags = True
        
        if writeTags:
            fileTags.delete()
            for t in tags:
                fileTags[t] = tags[t]
            fileTags.save(v1=2,v2_version=gOptions.ID3version)
            changeCount += 1
            Alert.extra("Updated tags in",path)
        else:
            sameCount += 1
    
    updateMessage = "Would update" if gOptions.writeMp3Tags == "never" else "Updated"
    Alert.info(updateMessage,"tags in",changeCount,"mp3 files;",sameCount,"files unchanged.")

