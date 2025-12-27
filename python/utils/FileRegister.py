"""The FileRegister base class maintains a cache of information about a group of semi-persistent files that
are typically updated every time the program runs.
Subclasses specify what information to store and how to use it.
The HashWriter subclass stores md5 hashes of utf-8 files. When requested to write a file, it touches the
disk only if the hash has changed."""

from __future__ import annotations

from typing import TypedDict, Callable
from enum import Enum, auto
from datetime import datetime
import json, contextlib, copy, os, re
import posixpath
import hashlib
import urllib.request, urllib.error
import Alert, Utils

class Status(Enum):
    STALE = auto()          # File loaded from disk cache but not registered
    UNCHANGED = auto()      # File registered; its record matched the cache
    UPDATED = auto()        # File registered; its record did not match the cache and has been updated 
    NEW = auto()            # New file registered that had no record in the cache
    BLOCKED = auto()        # There are changes to be made in the file, but something stopped us making them
    NOT_FOUND = auto()      # The file does not appear in the register

Record = TypedDict("Record",{"_status": Status,"_modified": datetime})
"""Stores the information about a file. The elements requred by FileRegister are:
_status: the file status as described above
_modified: the date/time the file was last modified or registered
"""

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

class FileRegister():
    """The FileRegister base class maintains a cache of information about a group of semi-persistent files that
    are typically updated every time the program runs.
    Subclasses specify what information to store and how to use it."""
    basePath: str               # All file paths are relative to this
    cacheFile: str              # Path to the register cache file (.json format)
    record: dict[str,Record]    # Stores a record of each file; key = path
    exactDates: bool            # If True, key "_modified" is the file modification date.
                                # If False, key "_modified" is the last time the file was registered.

    def __init__(self,basePath: str,cacheFile: str,exactDates = False):
        self.basePath = basePath
        self.cacheFile = cacheFile
        self.exactDates = exactDates

        cachePath = posixpath.join(self.basePath,self.cacheFile)
        try:
            with open(cachePath, 'r', encoding='utf-8') as file:
                rawCache = json.load(file)
        except FileNotFoundError:
            rawCache = {}
        except json.JSONDecodeError:
            Alert.caution("FileRegister error when reading JSON cache",cachePath,". Beginning with an empty register.")
            rawCache = {}
        
        self.record = {fileName:self.JsonItemToRecord(data) for fileName,data in rawCache.items()}

    def GetStatus(self,fileName: str) -> Status:
        "Return the status for a given fileName"
        if fileName in self.record:
            return self.record[fileName]["_status"]
        else:
            return Status.NOT_FOUND

    def IsRegistered(self,fileName: str) -> bool:
        "Return True if fileName has been registered."
        return self.GetStatus(fileName) in (Status.UNCHANGED,Status.UPDATED,Status.NEW,Status.BLOCKED)

    def SetStatus(self,fileName: str,status: Status) -> bool:
        """Set the status of an already-registered file.
        Returns False if the record doesn't exist."""
        if fileName in self.record:
            self.record[fileName]["_status"] = status
            return True
        else:
            return False


    def CheckStatus(self,fileName: str,recordData: Record) -> Status:
        """Check the status value that would be returned if we registered this record,
        but don't change anything."""

        returnValue = Status.UNCHANGED
        if fileName in self.record:
            recordCopy = copy.copy(self.record[fileName])
            del recordCopy["_status"]
            del recordCopy["_modified"]
            if recordData != recordCopy:
                returnValue = Status.UPDATED
        else:
            returnValue = Status.NEW

        return returnValue

    def UpdatedOnDisk(self,fileName,checkDetailedContents = False) -> bool:
        """Check whether the file has been modified on disk.
        If checkDetailedContents, call ReadRecordFromDisk and compare.
        Otherwise, if self.exactDates, compare the file modified date with the cache.
        If neither of these are the case, return False if the file exists.
        If fileName is not in the cache, return True if the file exists."""

        fullPath = posixpath.join(self.basePath,fileName)
        if fileName in self.record:
            dataInCache = self.record[fileName]
            try:
                if checkDetailedContents:
                    dataOnDisk = self.ReadRecordFromDisk(fileName)
                    dataOnDisk["_status"] = dataInCache["_status"]
                    dataOnDisk["_modified"] = dataInCache["_modified"]
                    return dataOnDisk != dataInCache
                elif self.exactDates:
                    return Utils.ModificationDate(fullPath) != dataInCache["_modified"]
                else:
                    return not os.path.isfile(fullPath)
            except FileNotFoundError:
                return True
        else:
            return os.path.isfile(fullPath)

    def Register(self,fileName: str,recordData: Record) -> Status:
        """Register a file and its associated record.
        Returns the record status."""

        returnValue = self.CheckStatus(fileName,recordData)
        if returnValue != Status.UNCHANGED:
            self.record[fileName] = recordData
            self.UpdateModifiedDate(fileName)
        
        self.record[fileName]["_status"] = returnValue
        return returnValue

    def UpdateModifiedDate(self,fileName) -> None:
        """Update key "_modified" for record fileName."""
        self.record[fileName]["_modified"] = datetime.now()
        if self.exactDates:
            with contextlib.suppress(FileNotFoundError):
                self.record[fileName]["_modified"] = Utils.ModificationDate(posixpath.join(self.basePath,fileName))

    def __enter__(self) -> FileRegister:
        return self

    def __exit__(self,exc_type, exc_val, exc_tb) -> None:
        self.Flush(disposingObject=True)

    def Flush(self,markAsStale:bool = False,disposingObject:bool = False) -> None:
        """Write the cache records to disk.
        markAsStale: Set status.STALE as if we had just read the cache from disk.
        disposingObject: The object will never be used again, so no need to preserve record."""
        
        if disposingObject:
            writeDict = self.record
        else:
            writeDict = {fileName:copy.copy(data) for fileName,data in self.record.items()}
        writeDict = {fileName:self.RecordToJsonItem(data) for fileName,data in writeDict.items()}

        with open(posixpath.join(self.basePath,self.cacheFile), 'w', encoding='utf-8') as file:
            json.dump(writeDict, file, ensure_ascii=False, indent=2)
        
        if markAsStale:
            for key in self.record:
                self.record[key]["_status"] = Status.STALE

    def Count(self,status: Status) -> int:
        "Return the number of records which have this status."
        return sum(r["_status"] == status for r in self.record.values())

    def StatusSummary(self,unregisteredStr = "unregistered.") -> str:
        "Summarize the status of our records."

        return ", ".join(f"{s.name.lower()}: {self.Count(s)}" for s in Status)
    
    def FilesWithStatus(self,status: Status) -> list[str]:
        "Return a list of filenames with the given status."
        return [filename for filename,record in self.record.items() if record["_status"] == status]

    def ReadRecordFromDisk(self,fileName) -> Record:
        """Reconstruct a record from the information on disk.
        Raise FileNotFoundError if the file does not exist.
        Subclasses should extend as necessary."""
        
        path = posixpath.join(self.basePath,fileName)
        if os.path.isfile(path):
            return {}
        else:
            raise FileNotFoundError(f"{path} is not found or is not a file.")

    def JsonItemToRecord(self,data: dict) -> Record:
        """Convert information read from the json cache file to a Record.
        Data is not reused, so the function can operate in-place.
        Subclasses can extend as necessary."""

        data["_status"] = Status.STALE
        data["_modified"] = datetime.strptime(data["_modified"],DATETIME_FORMAT)
        return data

    def RecordToJsonItem(self,recordData: Record) -> dict:
        """Perform the reverse of JsonItemToRecord in preparation for flushing.
        Can opereate (partially) in place, as a shallow copy of record has already been made.
        Subclasses can extend as necessary."""
        
        del recordData["_status"]
        recordData["_modified"] = recordData["_modified"].strftime(DATETIME_FORMAT)
        return recordData

# Write the file to disk if...
class Write(Enum):
    ALWAYS = auto()                 # always.
    CHECKSUM_CHANGED = auto()       # the new hash differs from the cached hash.
    DESTINATION_UNCHANGED = auto()  # the hash differs and the destination is unchanged.
                                    # This protects changes to the destination file we might want to save.
                                    # (Status.BLOCKED in this case.)
    DESTINATION_CHANGED = auto()    # the hash differs or the destination file has changed (default).
                                    # (UpdatedOnDisk returns True)

class HashWriter(FileRegister):
    """Stores md5 hashes of utf-8 files. When requested to write a file, it touches the
    disk only if the md5 hash has changed."""
    defaultMode: Write              # Default writing mode

    def __init__(self,basePath: str,cacheFile: str = "HashCache.json",exactDates = False,defaultMode = Write.DESTINATION_CHANGED):
        super().__init__(basePath,cacheFile,exactDates)
        self.defaultMode = defaultMode
    
    def __enter__(self) -> HashWriter:
        return self

    def _UpdateFile(self,fileName: str,newHash: str,writeFunction: Callable[[],None],mode:Write|None = None) -> Status:
        """Abstract function which implements the file update logic.
        Determine whether fileName needs to be updated, given newHash and mode.
        If so, call writeFunction to update the file on disk.
        fileName:       the file in question
        newHash:        md5 hash of the new data that might be written
        writeFunction:  callback function to call if the file needs updated
        mode:           write mode (see above)"""

        if mode is None:
            mode = self.defaultMode

        if mode in {Write.DESTINATION_CHANGED,Write.DESTINATION_UNCHANGED}:
            updatedOnDisk = self.UpdatedOnDisk(fileName,checkDetailedContents=False)
        else:
            updatedOnDisk = False
        
        if mode == Write.DESTINATION_UNCHANGED:
            if updatedOnDisk:
                if fileName in self.record:
                    self.record[fileName]["_status"] = Status.BLOCKED
                    return Status.BLOCKED

        newRecord = {"md5":newHash}
        status = self.Register(fileName,newRecord)
        if mode == Write.DESTINATION_CHANGED and updatedOnDisk:
            status = Status.UPDATED
        if mode == Write.ALWAYS:
            status = Status.UPDATED
        
        if status != Status.UNCHANGED:
            try:
                writeFunction()
                self.UpdateModifiedDate(fileName)
            except OSError as error:
                self.record[fileName]["_status"] = Status.BLOCKED
                    # Something stopped us from writing the file, so set status BLOCKED
                raise error
            self.record[fileName]["_status"] = status
        
        return status

    def WriteBinaryFile(self,fileName: str,fileContents: bytes,mode:Write|None = None) -> Status:
        """Write binary data to fileName if the stored hash differs from fileContents."""
        
        fullPath = posixpath.join(self.basePath,fileName)
        os.makedirs(posixpath.split(fullPath)[0],exist_ok=True)

        def WriteBinary() -> None:
            with open(fullPath, 'wb') as file:
                file.write(fileContents)

        newHash = hashlib.md5(fileContents,usedforsecurity=False).hexdigest()
        return self._UpdateFile(fileName,newHash,WriteBinary,mode)

    def WriteTextFile(self,fileName: str,fileContents: str,mode:Write|None = None) -> Status:
        """Write text fileContents to fileName in utf-8 encoding if the stored hash differs."""

        fileContents += "\n" # Append a newline to mimic printing the string.
        utf8Encoded = fileContents.encode("utf-8")
        return self.WriteBinaryFile(fileName,utf8Encoded,mode)
    
    def DownloadFile(self,fileName: str,url: str,mode:Write|None = None,retries: int = 2) -> Status:
        """Download file contents from url; update the file on disk only if the md5 checksum differs.
        The current algorithm is memory-inefficient."""

        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(url) as remoteFile:
                    remoteData = remoteFile.read()
                break
            except urllib.error.HTTPError:
                if attempt < retries:
                    Alert.caution(f"HTTP error when attempting to download {fileName}. Retrying.")
                else:
                    Alert.error(f"HTTP error when attempting to download {fileName}. Giving up after {retries + 1} attempts.")
                    return Status.BLOCKED

        return self.WriteBinaryFile(fileName,remoteData,mode)

    def ReadRecordFromDisk(self, fileName) -> Record:
        fullPath = posixpath.join(self.basePath,fileName)
        with open(fullPath, 'rb') as file:
            contents = file.read()
        
        hash = hashlib.md5(contents,usedforsecurity=False).hexdigest()
        return {"md5":hash}

    def DeleteStaleFiles(self,filterRegex = ".*") -> int:
        """Delete stale files appearing in the register if their full path matches filterRegex."""

        deleteCount = 0
        matcher = re.compile(filterRegex)
        for r in list(self.record):
            if self.record[r]["_status"] == Status.STALE and matcher.match(r):
                try:
                     os.remove(posixpath.join(self.basePath,r))
                     deleteCount += 1
                except FileNotFoundError:
                    pass
                del self.record[r]
        return deleteCount
    
    def DeleteUnregisteredFiles(self,directory = "",filterRegex = ".*") -> int:
        """Delete files in directory (relative to baseDir) that are either stale or unregistered and
        that match filterRegex."""

        deleteCount = 0
        matcher = re.compile(filterRegex)
        baseDir = posixpath.join(self.basePath,directory)
        if not os.path.isdir(baseDir):
            return 0
        stale = {"_status":Status.STALE}
        for fileName in sorted(os.listdir(baseDir)):
            fullPath = posixpath.join(baseDir,fileName)
            relativePath = posixpath.join(directory,fileName)
            if matcher.match(fullPath) and self.record.get(relativePath,stale)["_status"] == Status.STALE:
                try:
                     os.remove(fullPath)
                     deleteCount += 1
                except FileNotFoundError:
                    pass
                self.record.pop(relativePath,None)

        return deleteCount
                     
