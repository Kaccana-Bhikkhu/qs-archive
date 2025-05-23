"""Render raw documentation files in documentation/aboutSources to markdown files in documentation/about using pyratemp."""

from __future__ import annotations

import re, os, itertools
import Utils, Render, Alert, Filter, Database
import Html2 as Html
from typing import Tuple, Type, Callable, Iterable
import pyratemp, markdown
from markdown_newtab_remote import NewTabRemoteExtension
from datetime import datetime
import FileRegister

def WordCount(text: str) -> int:
    "Return the approximate number of words in text"
    words = re.split(r"\s+",text)
    if len(words) > 1:
        return len(words) - (not words[0]) - (not words[-1])
            # Check if the first and last word are empty. Note: bool True = 1
    else:
        return len(words) - (not words[0])

def RenderDocumentationFiles(aboutDir: str,destDir:str = "",pathToPages:str = "../",pathToBase = "../../",html:bool = True) -> list[Html.PageDesc]:
    """Read and render the documentation files. Return a list of PageDesc objects.
    aboutDir: the name of the directory to read from; files are read from aboutDir + "Sources".
    destDir: the destination directory; set to aboutDir if not given.
    pathToPages: path from the where the documentation will be written to the pages directory.
    pathToBase: the path to the base directory
    html: Render the file into html? - Leave in .md format if false.
    """
    global gDocumentationWordCount

    aboutDir = Utils.PosixJoin(gOptions.documentationDir,aboutDir)
    if not destDir:
        destDir = aboutDir
    sourceDir = aboutDir + "Sources"
    
    fileContents = {}
    fileModified = {}
    for fileName in sorted(os.listdir(sourceDir)):
        sourcePath = Utils.PosixJoin(sourceDir,fileName)

        if not os.path.isfile(sourcePath) or fileName.startswith("_") or not fileName.endswith(".md"):
            continue

        fileModified[fileName] = Utils.ModificationDate(sourcePath)
        template = pyratemp.Template(Utils.ReadFile(sourcePath))
        fileContents[fileName] = template(gOptions = gOptions,gDatabase = gDatabase,Database = Database,today = datetime.today().strftime("%B %d, %Y"))
        gDocumentationWordCount += WordCount(fileContents[fileName])
            
    def ApplyToText(transform: Callable[[str],Tuple[str,int]]) -> int:
        changeCount = 0
        for fileName in fileContents.keys():
            fileContents[fileName],changes = transform(fileContents[fileName])
            changeCount += changes
        
        return changeCount
            
    Render.LinkSubpages(ApplyToText,pathToPages,pathToBase)
    Render.LinkKnownReferences(ApplyToText)
    Render.LinkSuttas(ApplyToText)

    if html:
        htmlFiles = {}
        for fileName in fileContents:
            html = markdown.markdown(fileContents[fileName],extensions = ["sane_lists","footnotes","toc",NewTabRemoteExtension()])
        
            html = re.sub(r"<!--HTML(.*?)-->",r"\1",html) # Remove comments around HTML code
            htmlFiles[Utils.ReplaceExtension(fileName,".html")] = html
        fileContents = htmlFiles

    titleInPage = "The Ajahn Pasanno Question and Story Archive"
    renderedPages = []
    for fileName,fileText in fileContents.items():
        titleMatch = re.search(r"<!--TITLE:(.*?)-->",fileText)
        if titleMatch:
            title = titleMatch[1]
        else:
            m = re.match(r"[0-9]*_?([^.]*)",fileName)
            title = m[1].replace("-"," ")

        noNumbers = re.sub(r"^[0-9]+_","",fileName)
        page = Html.PageDesc(Html.PageInfo(title,Utils.PosixJoin(destDir,noNumbers if html else fileName),titleInPage))
        page.AppendContent(fileText)
        page.sourceFile = Utils.PosixJoin(sourceDir,Utils.ReplaceExtension(fileName,".md"))
        renderedPages.append(page)

    return renderedPages

def PrintWordCount() -> None:
    "Calculate the number of words in the text of the archive."

    def CountMutipleTexts(texts: Iterable[str]) -> int:
        words = 0
        for text in texts:
            words += WordCount(text)
        return words
    
    wc = {}
    wc["Excerpt"] = CountMutipleTexts(item["text"] for item in (itertools.chain.from_iterable(Filter.AllItems(x) for x in gDatabase["excerpts"])))
    wc["Event description"] = CountMutipleTexts(e["description"] for e in gDatabase["event"].values())
    wc["Documentation"] = gDocumentationWordCount
    wc["Total"] = sum(wc.values())

    for name in wc:
        Alert.info(f"{name} word count: {wc[name]}")

def AddArguments(parser) -> None:
    "Add command-line arguments used by this module"
    parser.add_argument('--documentationDir',type=str,default='documentation',help='Read and write documentation files here; Default: ./documenation')
    parser.add_argument('--info',type=str,action="append",default=[],help="Specify infomation about this build. Format key:value")
    parser.add_argument('--overwriteDocumentation',**Utils.STORE_TRUE,help='Write documentation files without checking modification dates.')

def ParseArguments() -> None:
    class NameSpace:
        pass
    infoObject = NameSpace()
    for item in gOptions.info:
        split = item.split(":",maxsplit=1)
        if len(split) > 1:
            value = split[1]
        else:
            value = True
        setattr(infoObject,split[0],value)
    gOptions.info = infoObject
    

def Initialize() -> None:
    pass

gOptions = None
gDatabase:dict[str] = {} # These globals are overwritten by QSArchive.py, but we define them to keep Pylance happy
gDocumentationWordCount = 0

def main() -> None:
    global gDocumentationWordCount
    gDocumentationWordCount = 0

    with FileRegister.HashWriter("./",Utils.PosixJoin(gOptions.documentationDir,"misc/HashCache.json"),exactDates=True) as writer:
        for directory in ['about','misc','technical']:
            for page in RenderDocumentationFiles(directory,pathToPages=Utils.PosixJoin("../../",gOptions.pagesDir),pathToBase="../../",html=False):
                status = writer.WriteTextFile(page.info.file,str(page),
                        mode=FileRegister.Write.DESTINATION_CHANGED if gOptions.overwriteDocumentation else FileRegister.Write.DESTINATION_UNCHANGED)

                if status == FileRegister.Status.BLOCKED:
                        # If the destination file has been modified, check to see if the source file is newer.
                        # If so, overwrite. Otherwise generate a warning.
                    sourcePath = Utils.PosixJoin(gOptions.documentationDir,directory + "Sources",Utils.PosixSplit(page.info.file)[1])
                    if Utils.DependenciesModified(page.info.file,[sourcePath]):
                        writer.WriteTextFile(page.info.file,str(page))
                    else:
                        Alert.warning("Did not overwrite",page.info.file,"because this file has a later modification date than its source,",sourcePath)


        Alert.extra()
        Alert.extra("Documentation files:",writer.StatusSummary())
        deleteCount = writer.DeleteUnregisteredFiles("documentation/about",r".*\.md")
        deleteCount += writer.DeleteUnregisteredFiles("documentation/technical",r".*\.md")
        deleteCount += writer.DeleteUnregisteredFiles("documentation/misc",r".*\.md")
        if deleteCount:
            Alert.info(deleteCount,"documentation file(s) deleted.")

    if Alert.verbosity >= 2:
        PrintWordCount()