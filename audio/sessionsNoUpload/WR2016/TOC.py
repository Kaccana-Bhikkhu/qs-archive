"""Create the table of contents for WR2016."""

import json
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

for teacher in sortedTeachers:
    print(teacher,TeacherDate(teacher))

with open("audio/sessionsNoUpload/WR2016/TOC.md", 'w', encoding='utf-8') as mdFile:
    print("Readings from or about (session numbers in parentheses):",file=mdFile)
    print(file=mdFile)

    for teacher in sortedTeachers:
        teacherName = teacherDB[teacher]["fullName"]
        if teacherDB[teacher].get("htmlFile"):
            teacherName = f"[{teacherName}]({teacherDB[teacher]['htmlFile']})"

        sessionList = sorted(set(r["sessionNumber"] for r in byTeacher[teacher]))
        linkedSessions = [f"[{s}](#WR2016_S{s:02d})" for s in sessionList]

        print(teacherName,f"({', '.join(linkedSessions)})",file=mdFile)
        print(file=mdFile)
