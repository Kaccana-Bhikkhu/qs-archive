from bs4 import BeautifulSoup
import csv, datetime
from urllib.parse import unquote
import os
import re

os.chdir("audio/sessions/WR2016")

def NormalizeWS(text: str) -> str:
    return re.sub(r"\s+"," ",text)

with open("WR2016 index simplified.html",encoding="utf-8") as file:
    soup = BeautifulSoup(file,"html.parser")

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