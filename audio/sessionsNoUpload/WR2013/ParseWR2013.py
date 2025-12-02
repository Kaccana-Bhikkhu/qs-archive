from bs4 import BeautifulSoup
import csv, datetime
from urllib.parse import unquote
import os
import re

os.chdir("audio/sessionsNoUpload/WR2013")

abhayagiriAudioDir = "https://www.abhayagiri.org/media/discs/APasannoRetreats/2013%20Fourth%20Foundation%20of%20Mindfulness/"
teacherDict = {
    "Ajahn Karuṇadhammo": "AKd",
    "Ajahn Jotipālo": "AJoti",
    "Ajahn Pasanno": "AP"
}
def NormalizeWS(text: str) -> str:
    return re.sub(r"\s+"," ",text)

with open("WR2013-indexSimplified.html",encoding="utf-8") as file:
    soup = BeautifulSoup(file,"html.parser")

with open("Sessions.csv","w",encoding='utf-8',newline="") as sFile, open("Excerpts.csv","w",encoding='utf-8',newline="") as xFile:
    sessionCsv = csv.writer(sFile,delimiter="\t")
    sessionCsv.writerow(["Session #","Date","Filename","Duration","Teachers","Session title","Remote mp3 URL"])
    excerptCsv = csv.writer(xFile,delimiter="\t")
    excerptCsv.writerow(["Session #","Kind","Flags","Start time","End time","Text","Teachers"])

    sessionNumber = 0
    prevDate = None
    for session in soup.find_all("p","talk-titles-western"):
        headerText = NormalizeWS(session.text)
        parts = re.match(r"(.*) [–-] ([^,]*), (.*)",headerText)
        sessionTitle,teacher,dateStr = parts[1],parts[2],parts[3]
        date = datetime.datetime.strptime(dateStr,"%B %d, %Y")
        
        if date != prevDate:
            sessionNumber += 1
            prevDate = date
            link = NormalizeWS(session.a["href"])
            filename = link.replace("Audio/","")
            remoteMp3 = abhayagiriAudioDir + link

            sessionCsv.writerow([sessionNumber,date.strftime("%d/%m/%Y"),filename,"",teacherDict[teacher],sessionTitle,remoteMp3])
            print(sessionNumber,sessionTitle,teacher,date)

        sibling = session.next_sibling
        while sibling and (isinstance(sibling,str) or "talk-titles-western" not in sibling.get("class",())):
            if not isinstance(sibling,str):
                if "talk-description-western" in sibling.get("class",()):
                    talkDescription = NormalizeWS(sibling.text)
                    excerptCsv.writerow([sessionNumber,"Teaching","","Session","",talkDescription,""])
                    print(talkDescription)
                elif sibling.name == "ul": # A list of readings
                    readings = sibling.find_all("p")
                    if len(readings) > 1:
                        excerptCsv.writerow([sessionNumber,"Reading group","","Session","","",""])
                        for reading in sibling.find_all("p"):
                            readingText = NormalizeWS(reading.text)
                            excerptCsv.writerow([sessionNumber,"Reading","-","","",readingText,""])
                            print("  -",readingText)
                    else:
                        excerptCsv.writerow([sessionNumber,"Reading","","Session","",NormalizeWS(readings[0].text),""])
            sibling = sibling.next_sibling


"""
with open("Sessions.csv","w") as sFile, open("Excerpts.csv","w") as xFile:
    sessionCsv = csv.writer(sFile,delimiter="\t")
    sessionCsv.writerow(["Session #","Date","Filename","Duration","Teachers","Session title","Remote mp3 URL"])
    excerptCsv = csv.writer(xFile,delimiter="\t")
    excerptCsv.writerow(["Session #","Kind","Flags","Start time","End time","Text","Teachers"])

    sessionNumber = 0
    for sessionHtml in soup.find_all("div"):
        sessionNumber += 1
        print(sessionNumber)
        sessionTitle = sessionHtml.h2.a["title"]
        author,readBy,dateStr = sessionHtml.p.get_text().split(" – ")
        readBy = readBy.removeprefix("Read by ")
        date = datetime.datetime.strptime(dateStr,"%B %d, %Y")
        for listNumber,listHtml in enumerate(sessionHtml.find_all("ul")):
            for itemNumber,itemHtml in enumerate(listHtml.find_all("li")):
                if listNumber == 0: # The first list contains the readings
                    timeStart = f"{itemNumber}:59" if itemNumber else "Session"
                    excerptCsv.writerow([sessionNumber,"Reading","",timeStart,"",NormalizeWS(itemHtml.get_text()),""])
                    excerptCsv.writerow([sessionNumber,"Read by","","","","",readBy])
                if listNumber == 1: # The second list contains the questions
                    text = NormalizeWS(itemHtml.get_text())
                    m = re.match(r"\[([0-9:]+)\] (.+)",text)
                    timeStart = m[1]
                    questionText = m[2]
                    excerptCsv.writerow([sessionNumber,"","",timeStart,"",questionText,""])

        remoteMp3 = sessionHtml.h2.a["href"]
        print("-----")

        filename = unquote(remoteMp3.split("/")[-1])
        sessionCsv.writerow([sessionNumber,date.strftime("%d/%m/%Y"),filename,"","",sessionTitle,remoteMp3])

print(sessionNumber,"total sessions.")

"""