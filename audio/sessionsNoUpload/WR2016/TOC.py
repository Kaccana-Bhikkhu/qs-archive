"""Create the table of contents for WR2016."""

import json
from airium import Airium
from contextlib import nullcontext
from collections import defaultdict

def LoadDatabase() -> dict:
    """Read the database indicated by filename"""

    with open("pages/assets/SpreadsheetDatabase.json", 'r', encoding='utf-8') as file:
        newDB = json.load(file)
    
    return newDB

database = LoadDatabase()
teacherDB = database["teacher"]
teacherDB["AKalyano"] = {
    "fullName": "Ajahn Kalyāno"
}

excerpts = [x for x in database["excerpts"] if x["event"] == "WR2016"]
readings = [x for x in excerpts if x["kind"] == "Reading"]
print(len(readings))

byTeacher = defaultdict(list)
for reading in readings:
    for teacher in reading["teachers"] or ["AKalyano"]:
        byTeacher[teacher].append(reading)
byTeacher.pop("NScott",None)

def TeacherDate(teacher: str) -> float:
    """Return the date associated with this teacher."""
    fullName = teacherDB[teacher]["fullName"]
    nameRecord = database["name"].get(fullName)
    if nameRecord:
        return float(nameRecord["sortBy"] or "9999")
    else:
        return 9999

sortedTeachers = sorted(byTeacher,key=TeacherDate)

sessionName = {s["sessionNumber"]:s["sessionTitle"] for s in database["sessions"] if s["event"] == "WR2016"}

with open("audio/sessionsNoUpload/WR2016/TOC.md", 'w', encoding='utf-8') as mdFile:
    a = Airium()
    with a.p():
        with a.span(style="text-decoration:underline"):
            a("Readings from or about")
        a("(ordered roughly by date)")

    for teacher in sortedTeachers:
        teacherLink = teacherDB[teacher].get("htmlFile")

        sessionList = sorted(set(r["sessionNumber"] for r in byTeacher[teacher]))
        linkedSessions = [f"[{s}](#WR2016_S{s:02d})" for s in sessionList]

        with a.h3():
            a.a(href="#").i(Class="fa fa-plus-square toggle-view noscript-hide",id=f"{teacher}")
            # with a.a(href="../teachers/" + teacherLink) if teacherLink else nullcontext():
            a(teacherDB[teacher]["fullName"])
            a(f"({len(sessionList)})")
        
        with a.div(Class="listing",style="display:none;",id=f"{teacher}.b"):
            for sessionNumber in sessionList:
                with a.p():
                    a(f'<a href="#WR2016_S{sessionNumber:02d}">Session {sessionNumber}</a>:')
                    a(sessionName[sessionNumber])

        # print(teacherName,f"({', '.join(linkedSessions)})",file=mdFile)
        # print(file=mdFile)
    
    print(str(a),file=mdFile)
