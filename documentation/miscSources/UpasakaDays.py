"""Download csv files from Google sheet WR2025 readings and parse them into AP QS Archive excerpt format."""

import sys, os
import argparse
import csv

scriptDir,_ = os.path.split(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(scriptDir,'../../python/modules'))
sys.path.append(os.path.join(scriptDir,'../../python/utils'))
import DownloadCSV, Utils

os.chdir("documentation/miscSources")

def DownloadSheet():
    DownloadCSV.gOptions = Utils.gOptions = options
    DownloadCSV.ParseArguments()

    sheets = {
        "MarkdownCode": 303658647
    }
    DownloadCSV.DownloadSheets(sheets,None)

parser = argparse.ArgumentParser(description="""Download csv files from Google sheet WR2025 readings and parse them into AP QS Archive excerpt format.""")
parser.add_argument('--spreadsheet',type=str, default = 'https://docs.google.com/spreadsheets/d/1ZrStmtWWqtc4GWxvqQHifmx1WYhCLbNAeC0VAEWvdME/', help='URL of the Upasaka Day table Google Sheet')
parser.add_argument('--multithread',**Utils.STORE_TRUE,help="Multithread some operations")

options = parser.parse_args(sys.argv[1:])

header = """
## Upāsakā Day Themes
<!--TITLE:Upāsakā Day Themes-->

From 2006 to 2019, there were five [Upāsakā Days](about:Event-series#upasika-days) a year, each organized around one of five themes.
Dimmed entries indicate that no recording is available.
Links marked ![External link](../images/icons/Link-external-small-ltr-progressive.svg) are recordings outside the Ajahn Pasanno Archive.

### Table of Upāsakā Day themes:
"""

footer = """
<br>
### Teacher abbreviations:
AP: Ajahn Pasanno <br>
AY: Ajahn Yatiko <br>
AKd: Ajahn Karuṇadhammo <br>
AÑ: Ajahn Ñāṇiko <br>
DS: Debbie Stamp <br>
JD: Jeanie Daskais <br>

## Later Upāsakā Days in the Archive:

[Living in a Changing Society](event:UD2020)<br>
&nbsp;&nbsp;Ajahn Pasanno

Honoring the Buddha: The Mahāparinibbāna Sutta – April 2021
"""

DownloadSheet()

with (open("MarkdownCode.csv",encoding='utf8') as csvFile,open("UpasakaDays.md","w",encoding='utf8') as markdownFile):
    print(header,file=markdownFile)
    for line in csv.reader(csvFile,dialect=csv.excel):
        if line:
            print(line[0],file=markdownFile)
    print(footer,file=markdownFile)