import re

lowercaseWords = "a by and of the in as ".split(" ")
with open("Chapters.txt") as file:
    for n,line in enumerate(file,start=1):
        parts = re.match(r"CH\. [XVI]+ ([^.]+)[. ]+([0-9 ]+)$",line)
        if parts:
            chapterName = parts[1].strip()
            pageNumber = parts[2].replace(" ","")
            chapterName = chapterName.title()
            words = chapterName.split(" ")
            lowercased = [w.lower() if w.lower() in lowercaseWords else w for w in words[1:]]
            words[1:] = lowercased
            chapterName = " ".join(words)
            print(f"{pageNumber}\tChapter {n}: {chapterName}")
        else:
            print("Cannot parse",line)
