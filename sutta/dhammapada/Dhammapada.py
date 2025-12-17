"""
Read the xhtml files of Venerable Buddharakkhita's Dhammapada translation and arrange them by verse in Dhammapada.json
"""

from bs4 import BeautifulSoup
import json
from urllib.parse import unquote
import os
import re

os.chdir("sutta/dhammapada")

dhammapada:dict[str,str] = {}

with open(f"buddharakkhita/Copyright.xhtml",encoding="utf-8") as file:
    soup = BeautifulSoup(file,"html.parser")
    for number,paragraph in enumerate(soup.find_all("p"),start=1):
        dhammapada[f"info{number}"] = paragraph.get_text()

sectionNumber = 1
while (True):
    try:
        with open(f"buddharakkhita/Section{sectionNumber:04}.xhtml",encoding="utf-8") as file:
            soup = BeautifulSoup(file,"html.parser")
    except OSError:
        break

    for paragraph in soup.find_all("p"):
        link = paragraph.a
        if (link):
            allText = paragraph.get_text()
            verseNumber = re.match("[0-9]+",allText)
            if verseNumber:
                text = re.search(r"[A-Z].*",paragraph.get_text())[0] # The verse starts with an uppercase letter
                text = re.sub(r"[0-9]+$","",text) # Remove endnotes
                dhammapada[verseNumber[0]] = text
                #print(verseStr,text)

    sectionNumber += 1

with open("Dhammapada.json", 'w', encoding='utf-8') as file:
    json.dump(dhammapada, file, ensure_ascii=False, indent=2)