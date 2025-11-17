"""Create the table of contents for WR2014."""

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
teacherDB["MaeCheeKaew"] = {"fullName": "Mae Chee Kaew"}

excerpts = [x for x in database["excerpts"] if x["event"] == "WR2014"]
readings = [x for x in excerpts if x["kind"] == "Reading"]
print(len(readings))

byTeacher = defaultdict(list)
for reading in readings:
    teachers = reading["teachers"]
    if not teachers:
        if "Thate" in reading["text"]:
            teachers = ["AThate"]
        elif "Teean" in reading["text"]:
            teachers = ["ATeean"]
    if teachers[0] in ("AJaya","ATongJan","AKoon","AJundee","AToon","ABoonChoo","PBreiter"):
        teachers = ["AChah"]
    if teachers[0] == "ASilaratano":
        teachers = ["MaeCheeKaew"]
    for teacher in teachers:
        byTeacher[teacher].append(reading)
    

def TeacherDate(teacher: str) -> float:
    """Return the date associated with this teacher."""
    if teacher == "UKee": # The rough date she left home
        return 1945
    fullName = teacherDB[teacher]["fullName"]
    nameRecord = database["name"].get(fullName)
    if nameRecord:
        return float(nameRecord["sortBy"] or "9999")
    else:
        return 9999

sortedTeachers = sorted(byTeacher,key=TeacherDate)

sessionName = {s["sessionNumber"]:s["sessionTitle"] for s in database["sessions"] if s["event"] == "WR2014"}

with open("audio/sessionsNoUpload/WR2014/TOC.md", 'w', encoding='utf-8') as mdFile:
    a = Airium()
    with a.p():
        with a.span(style="text-decoration:underline"):
            a("Readings from or about")
        a("(ordered roughly by date)")

    for teacher in sortedTeachers:
        teacherLink = teacherDB[teacher].get("htmlFile")

        sessionList = sorted(set(r["sessionNumber"] for r in byTeacher[teacher]))
        linkedSessions = [f"[{s}](#WR2014_S{s:02d})" for s in sessionList]

        with a.h3():
            a.a(href="#").i(Class="fa fa-plus-square toggle-view noscript-hide",id=f"{teacher}")
            # with a.a(href="../teachers/" + teacherLink) if teacherLink else nullcontext():
            a(teacherDB[teacher]["fullName"])
            a(f"({len(sessionList)})")
        
        with a.div(Class="listing",style="display:none;",id=f"{teacher}.b"):
            for sessionNumber in sessionList:
                with a.p():
                    a(f'<a href="#WR2014_S{sessionNumber:02d}">Session {sessionNumber}</a>:')
                    a(sessionName[sessionNumber])

        # print(teacherName,f"({', '.join(linkedSessions)})",file=mdFile)
        # print(file=mdFile)
    
    print(str(a),file=mdFile)
