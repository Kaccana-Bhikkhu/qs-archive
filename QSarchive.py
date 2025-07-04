"""Main program to create the Ajahn Pasanno Archive website
"""

from __future__ import annotations

import argparse, shlex
import importlib
import os, sys, re
import json
from typing import Tuple
from collections import Counter

scriptDir,_ = os.path.split(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(scriptDir,'python/modules')) # Look for modules in these subdirectories of the directory containing QAarchive.py
sys.path.append(os.path.join(scriptDir,'python/utils'))

import Utils, Alert, Filter, Database, Document
Alert.ObjectPrinter = Database.ItemRepr

def PrintModuleSeparator(moduleName:str) -> None:
    if moduleName:
        Alert.structure(f"{'='*10} {moduleName} {'='*(25 - len(moduleName))}")
    else:
        Alert.structure('='*37)

def ReadJobOptions(jobName: str) -> list[str]:
    "Read a list of job options from the .vscode/launch.json"
    
    with open(".vscode/launch.json", "r") as file:
        fixed_json = ''.join(line for line in file if not line.lstrip().startswith('//'))
        config = json.loads(fixed_json)
    
    for job in config["configurations"]:
        if job["name"] == jobName:
            return job["args"]
    
    allJobs = [job["name"] for job in config["configurations"]]
    if jobName:
        print(f"{repr(jobName)} does not appear in .vscode/launch.json.")
    print(f"Available jobs: {allJobs}")
    sys.exit(2)

def ApplyDefaults(argumentStrings:list[str],parser: argparse.ArgumentParser) -> None:
    "Parse and apply the given arguments as defaults to the parser."

    processedArgs = shlex.split(" ".join(argumentStrings))
    argIndexes = [n for n,arg in enumerate(processedArgs) if arg == "--args"]

    nextArgumentToProcess = 0
    for argIndex in argIndexes:
        # First process all arguments up to the --args argument
        commandArgs = ["DummyOp"] + processedArgs[nextArgumentToProcess:argIndex]
        defaultArgs = parser.parse_args(commandArgs)
        parser.set_defaults(**vars(defaultArgs))
        nextArgumentToProcess = argIndex + 2

        # Then parse the file specified by the --args argument
        if (argIndex + 1) < len(processedArgs):
            argsFile = processedArgs[argIndex + 1]
            ReadArgsFile(argsFile,parser)
        else:
            Alert.error("--args must be followed by a file to read from.")

    # Finally process any remaining arguments
    commandArgs = ["DummyOp"] + processedArgs[nextArgumentToProcess:]
    defaultArgs = parser.parse_args(commandArgs)
    parser.set_defaults(**vars(defaultArgs))

def ReadArgsFile(argsFilename: str,parser: argparse.ArgumentParser) -> None:
    "Read the specified .args file and apply these as default values to parser."
    if gParsedArgsFileCount[argsFilename] > 3:
        Alert.error(f"Attempting to load .args file {argsFilename} more than three times. This probably indicates recursive inclusion.")
        sys.exit(1)
    
    try:
        with open(argsFilename,"r",encoding="utf-8") as argsFile:
            argumentStrings = []
            for line in argsFile:
                removeComments = re.split(r"\s//|^//",line)
                line = removeComments[0].strip()
                if line:
                    argumentStrings.append(line)
        gParsedArgsFileCount[argsFilename] += 1
    except OSError:
        gErrorArgsFiles.append(argsFilename)
        return
    
    ApplyDefaults(argumentStrings,parser)

def LoadDatabaseAndAddMissingOps(opSet: set[str]) -> Tuple[dict,set[str]]:
    "Scan the list of specified ops to see if we can load a database to save time. Add any ops needed to support those specified."

    newDB = {}
    opSet:set = set(opSet) # Clone opSet

    if 'DownloadCSV' in opSet:
        if len(opSet) > 1: # If we do anything other than DownloadCSV, we need to parse the newly-downloaded files
            opSet.add('ParseCSV')
        else:
            return newDB,opSet
    
    requireSpreadsheetDBset = set(requireSpreadsheetDB)
    requireRenderedDBset = set(requireRenderedDB)

    if 'Render' in opSet: # Render requires link in all cases
        opSet.add('Link')
    if opSet.intersection(requireRenderedDBset):
        if 'ParseCSV' not in opSet and not opSet.intersection(requireSpreadsheetDBset) and \
                      not Utils.DependenciesModified(clOptions.renderedDatabase,[clOptions.spreadsheetDatabase]):
            try:
                newDB = Database.LoadDatabase(clOptions.renderedDatabase)
                return newDB,opSet
            except OSError:
                pass
        opSet.update(['Link','Render'])
    
    if 'ParseCSV' not in opSet and opSet.intersection(requireSpreadsheetDBset):
        try:
            newDB = Database.LoadDatabase(clOptions.spreadsheetDatabase)
            return newDB,opSet
        except OSError:
            opSet.add('ParseCSV')
    
    return newDB,opSet

# The list of code modules/ops to implement
requireSpreadsheetDB = ['ReviewDatabase','DownloadFiles','SplitMp3','ExportAudio','Link','Render']
requireRenderedDB = ['Build','SetupSearch','SetupAutoComplete','SetupFeatured','TagMp3','PrepareUpload','CheckLinks']
moduleList = ['DownloadCSV','ParseCSV'] + requireSpreadsheetDB + requireRenderedDB
optionalModules = {'ExportAudio'} # These aren't included in All

modules = {modName:importlib.import_module(modName) for modName in moduleList}
priorityInitialization = ['Link']
Utils.ExtendUnique(priorityInitialization,modules.keys())

parser = argparse.ArgumentParser(description="""Create the Ajahn Pasanno Archive website from mp3 files and the 
AP QA archive main Google Sheet.""")

parser.add_argument('ops',type=str,help="""A comma-separated list of operations to perform. No spaces allowed. Available operations:
DownloadCSV - download csv files from the Google Sheet.
ParseCSV - convert the csv files downloaded from the Google Sheet to SpreadsheetDatabase.json.
ReviewDatabase - run various checks on the content of SpreadsheetDatabase.json.
DownloadFiles - download files from remote links or mirrors when needed.
SplitMp3 - split mp3 files into individual excerpts based on the times in SpreadsheetDatabase.json.
Link - try to find valid links to excerpt mp3 files, session mp3 files, and references.
Render - use pryatemp and markdown to convert excerpts into html and saves to RenderedDatabase.json.
Build - create html files for all menus and excerpts.
SetupSearch - create SearchDatabase.json.
SetupAutoComplete - create AutoCompleteDatabase.json
SetupFeatured - create FeaturedDatabase.json.
TagMp3 - update the ID3 tags on excerpt mp3 files.
PrepareUpload - move files that don't need to be uploaded to noUpload directories.
CheckLinks - validate hyperlinks in documentation files and excerpts.
All - run all the above modules in sequence.
""")

parser.add_argument('--homeDir',type=str,default='.',help='All other pathnames are relative to this directory; Default: ./')
parser.add_argument('--defaults',type=str,default='python/config/Default.args,python/config/LocalDefault.args',help='A comma-separated list of .args default argument files; see python/config/Default.args')
parser.add_argument("--args",type=str,action="append",default=[],help="Read arguments from an .args file")
parser.add_argument('--skip',type=str,default='',help='A comma-separated list of operations to skip')
parser.add_argument('--events',type=str,default='All',help='A comma-separated list of event codes to process; Default: All')
parser.add_argument('--spreadsheetDatabase',type=str,default='pages/assets/SpreadsheetDatabase.json',help='Database created from the csv files; keys match spreadsheet headings; Default: pages/assets/SpreadsheetDatabase.json')
parser.add_argument('--multithread',**Utils.STORE_TRUE,help="Multithread some operations")
parser.add_argument('--dumpArgs',**Utils.STORE_TRUE,help="Print the argument parser arguments and exit")

for mod in modules.values():
    mod.AddArguments(parser)

parser.add_argument('--verbose','-v',default=0,action='count',help='increase verbosity')
parser.add_argument('--quiet','-q',default=0,action='count',help='decrease verbosity')
parser.add_argument('--debug',**Utils.STORE_TRUE,help="Print debugging logs")

if sys.argv[1] == "Job" or sys.argv[1] == "Jobs": # If ops == "Job", 
    jobOptionsList = ReadJobOptions(sys.argv[2] if len(sys.argv) >= 3 else None)
    argList = jobOptionsList + sys.argv[3:]
    Alert.essential('python',sys.argv[0]," ".join(argList))
else:
    argList = sys.argv[1:]
PrintModuleSeparator("")

## STEP 1: Parse the command line argument list to set the home directory
baseOptions = parser.parse_args(argList)
if not os.path.exists(baseOptions.homeDir):
    os.makedirs(baseOptions.homeDir)
os.chdir(baseOptions.homeDir)

Alert.verbosity = baseOptions.verbose - baseOptions.quiet
if baseOptions.homeDir != '.':
    Alert.info("Home directory:",baseOptions.homeDir)

## STEP 2: Configure parser with default options read from the .args files
gParsedArgsFileCount = Counter() # Count the number of times an .args file is applied to stop infinite recursion
gErrorArgsFiles = []
argsFileList = baseOptions.defaults.split(",") + baseOptions.args
for argsFile in argsFileList:
    try:
        ReadArgsFile(argsFile,parser)
    except OSError:
        pass
if gParsedArgsFileCount:
    Alert.structure("Read arguments from:",", ".join(gParsedArgsFileCount.keys()))
if gErrorArgsFiles:
    Alert.structure("Could not read:",", ".join(gErrorArgsFiles))

## STEP 3: Parse the command line again to override arguments specified by the .args files
clOptions = parser.parse_args(argList)
clOptions.verbose -= clOptions.quiet
Alert.verbosity = clOptions.verbose
Alert.Debugging(clOptions.debug)

for mod in modules.values():
    mod.gOptions = clOptions
        # Let each module access all arguments
utilityModules = [Utils,Database,Document,Filter]
for mod in utilityModules:
    mod.gOptions = clOptions

for modName in priorityInitialization:
    modules[modName].ParseArguments()
        # Tell each module to parse its own arguments

if Alert.error.count:
    print("Aborting due to argument parsing errors.")
    sys.exit(2)

if clOptions.dumpArgs:
    print("Parsed arguments (clOptions):")
    for attribute in sorted(dir(clOptions)):
        if not attribute.startswith("_"):
            print(f"   {attribute} = {repr(getattr(clOptions,attribute))}")
    sys.exit(0)

if clOptions.events != 'All':
    clOptions.events = clOptions.events.split(',')
        # clOptions.events is now either the string 'All' or a list of strings

if clOptions.ops.strip() == 'All':
    opSet = set(moduleList) - optionalModules
else:
    opSet = set(verb.strip() for verb in clOptions.ops.split(','))

# Check for unsuppported ops
for verb in opSet:
    if verb not in moduleList:
        Alert.warning("Unsupported operation",verb)

# Skip specified ops; useful when all operations are specified.
skipOps = set(verb.strip() for verb in clOptions.skip.split(','))
for verb in skipOps:
    if verb and verb not in moduleList:
        Alert.caution("Can't skip unknown operation",verb)
opSet -= skipOps

database, newOpSet = LoadDatabaseAndAddMissingOps(opSet)
if newOpSet != opSet:
    Alert.info(f"Will run additional module(s): {newOpSet.difference(opSet)}.")
    opSet = newOpSet

# Set up the global namespace for each module - this allows the modules to call each other out of order
for mod in modules.values():
    mod.gDatabase = database
for mod in utilityModules:
    mod.gDatabase = database

# Then run the specified operations in sequential order
initialized = False
for moduleName in moduleList:
    if database and not initialized:
        for modName in priorityInitialization:
            modules[modName].Initialize() # Run each module's initialize function when the database fills up
        initialized = True

    if moduleName in opSet:
        PrintModuleSeparator(moduleName)
        modules[moduleName].main()
PrintModuleSeparator("")

if clOptions.ignoreTeacherConsent:
    Alert.warning("Teacher consent has been ignored. This should only be used for testing and debugging purposes.")
if clOptions.pendingMeansYes:
    Alert.warning("Pending teacher consent has been treated as yes. This should only be used for testing and debugging purposes.")
if clOptions.ignoreExcludes:
    Alert.warning("Session/excerpt exclusion flags have been ignored. This should only be used for testing and debugging purposes.")

errorCountList = []
for error in [Alert.error, Alert.warning, Alert.caution, Alert.notice]:
    countString = error.CountString()
    if countString:
        errorCountList.append(countString)

if errorCountList:
    Alert.essential("  ***** " + ", ".join(errorCountList) + " *****")
else:
    Alert.status("No errors reported.")

Alert.structure("QSarchive.py finished.")