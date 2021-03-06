#!/usr/bin/python

import argparse
from collections import OrderedDict
import math
import pickle
import pprint
import requests

'''
Queries LSST Jira, fetches all database-related epics
and produces html file that contains:
a) a 2-D table (wbs vs fiscal years)
b) a list of orphans epics that did not make it to the 2-D table
It also shows blocking epics. To turn this off, run with "-b 0"
It also show done epics. to turn this off, run with "-d 0"

For long term planning, uncomment lines starting with PLANNING,
run like this:
./build-LDM-240.py  -b 0 |grep PLANNING|sort > /tmp/x.csv
and open the x.csv with spreadsheet

Author: Jacek Becla / SLAC
'''

wbses = OrderedDict()
wbses['02C.06.00'   ] = 'Data Access and Database'
wbses['02C.06.01.01'] = 'Catalogs, Alerts and Metadata'
wbses['02C.06.01.02'] = 'Image and File Archive'
wbses['02C.06.02.01'] = 'Data Access Client Framework'
wbses['02C.06.02.02'] = 'Web Services'
wbses['02C.06.02.03'] = 'Query Services'
wbses['02C.06.02.04'] = 'Image and File Services'
wbses['02C.06.02.05'] = 'Catalog Services'

# fiscal years
fys = ('FY14', 'FY15', 'FY16', 'FY17', 'FY18', 'FY19', 'FY20')
# cycles
cycles = ('W14','S14','W15','S15','W16','X16','F16','S17','F17','S17','F18','S18','F19','S19','F20','S20', 'F20')

cells = OrderedDict()
for wbs in wbses:
    cells[wbs] = {}
    for fy in fys:
        cells[wbs][fy] = []

parser = argparse.ArgumentParser()
parser.add_argument('-b', '--showBlockers', required=False, default=1)
parser.add_argument('-d', '--showDone', required=False, default=1)
parser.add_argument('-o', '--outFileName', required=False, default="/dev/null")

args = vars(parser.parse_args())
showBlockers = int(args['showBlockers'])
showDone = int(args['showDone'])
outFileName = args['outFileName']

SEARCH_URL = "https://jira.lsstcorp.org/rest/api/2/search"

# This is for offline analysis. Run it first with "dumpToFile"
# set to True, this will fetch data from jira as it normally
# does, and save it in file. Then to run offline analysis,
# set readFromFile to True, while dumpToFile is False
fileForOfflineAnalysisDM = "/tmp/for_ldm-240.DM.out"
fileForOfflineAnalysisDLP = "/tmp/for_ldm-240.DLP.out"
dumpToFile = False
readFromFile = False

if readFromFile:
    f = open(fileForOfflineAnalysisDM, "r")
    result = pickle.load(f)
    f.close()
    f = open(fileForOfflineAnalysisDLP, "r")
    resultDLP = pickle.load(f)
    f.close()
else:
    result = requests.get(SEARCH_URL, params={
        "maxResults": 10000,
        "jql":('project = DM'
               ' AND issuetype = Epic'
               ' AND Team = "Data Access and Database"')}).json()

    resultDLP = requests.get(SEARCH_URL, params={
        "maxResults": 10000,
        "jql":('project = "DM Long-range  Planning"'
               ' AND wbs ~ "02C.06*"'
               ' AND type = milestone')}).json()


if dumpToFile:
    f = open(fileForOfflineAnalysisDM, "w")
    pickle.dump(result, f)
    f.close()
    f = open(fileForOfflineAnalysisDLP, "w")
    pickle.dump(resultDLP, f)
    f.close()



# for keeping issues that won't make it into the WBS + FY structure
orphans = []


class EpicEntry:
    def __init__(self, key, summary, status, cycle, sps, blockedBy=None):
        self.key = key
        self.summary = summary
        self.status = status
        self.blockedBy = blockedBy
        self.cycle = cycle  # this can be 'Y', or 'A', or 'B'
                            # where 'A is winter or spring
                            # 'B' is Extra or Summer or Fall
        self.sps = sps

class DLPEpicEntry:
    def __init__(self, key, summary):
        self.key = key
        self.summary = summary

def cycleToAB(cycle):
    # patch related to summer->fall, winter-->spring shift
    # basically all winter and all spring are A, extra and all summer are B
    if cycle[:1] == 'W':
        return 'A'
    if cycle[:1] == 'X':
        return 'B'
    if cycle[:1] == 'F':
        return 'B'
    if cycle in ('S14', 'S15'):
        return 'B'
    return 'A'

def genEpicLine(epic):
    if epic.cycle == 'A':
        color = "c8682c" # dark orange (for Winter cycle)
    elif epic.cycle == 'B':
        color = "309124" # green (for Summer cycle)
    else:
        color = "2c73c8" # blue (cycle no specified)
    if epic.status == "Done":
        (stStart, stStop) = ("<strike>","</strike>")
    else:
        (stStart, stStop) = ("", "")

    fteMonth = epic.sps/26.3
    if fteMonth % 1 < 0.05:
        fteMonth = "%d" % fteMonth
    else:
        fteMonth = "%.1f" % fteMonth
    return '%s<a href="https://jira.lsstcorp.org/browse/%s"><font color="%s">%s (%s)</font></a>%s' % \
        (stStart, epic.key, color, epic.summary, fteMonth, stStop)


# build quick lookup array (key->status)
lookupArr = {}
for issue in result['issues']:
    theKey = issue['key']
    theSts = issue['fields']['status']['name']
    lookupArr[theKey] = theSts

# count story points per FY
spsArr = {}
for fy in fys:
    spsArr[fy] = 0

dlpMilestonesArr = {}
for fy in fys:
    dlpMilestonesArr[fy] = []

for issue in resultDLP['issues']:
    theKey = issue['key']
    cycle = issue['fields']['fixVersions'][0]['name']
    smr = issue['fields']['summary']
    fy = "FY%s" % cycle[1:]
    dlpMilestonesArr[fy].append(DLPEpicEntry(theKey, smr))

for fy in dlpMilestonesArr:
    s = ""
    for e in dlpMilestonesArr[fy]:
        s += "(%s, %s) " % (e.key, e.summary)
    print "%s: %s" % (fy, s)

for issue in result['issues']:
    theKey = issue['key']
    theSmr = issue['fields']['summary']
    theWBS = issue['fields']['customfield_10500']
    theSts = issue['fields']['status']['name']
    theSPs = issue['fields']['customfield_10202']
    if theSPs is None:
        theSPs = 0
    else:
        theSPs = int(theSPs)
    theFY = theSmr[:4]

    # skip 'Done' if requested
    if theSts == 'Done' and not showDone:
        continue

    # skip 'KPM Measurements'
    if "KPM Measurement" in theSmr:
        continue

    # Deal with blocking epics
    blkdBy = []
    if showBlockers:
        for iLink in issue['fields']['issuelinks']:
            if iLink['type']['inward']=='is blocked by' and 'inwardIssue' in iLink:
                blkKey = iLink['inwardIssue']['key']
                blkSmr = iLink['inwardIssue']['fields']['summary']
                blkSts = lookupArr[blkKey] if blkKey in lookupArr else None
                blkdBy.append(EpicEntry(blkKey, blkSmr, blkSts, 'Y', theSPs))
    # Save in the "cells" array
    if theWBS in wbses and theFY in fys:
        spsArr[theFY] += theSPs
        print "GOOD1: %s, %s, %s, %d, %s" % (theKey, theWBS, theFY, theSPs, theSmr)
        cells[theWBS][theFY].append(EpicEntry(theKey, theSmr[4:], theSts, 'Y', theSPs, blkdBy))
        print "PLANNING;%s;%s;%d;%s" %(theFY, theKey, theSPs, theSmr[4:])
    elif theWBS in wbses and theSmr[:3] in cycles:
        theFY = 'FY%s' % theSmr[1:3]
        spsArr[theFY] += theSPs
        theCcl = cycleToAB(theSmr)
        print "GOOD2: %s, %s, %s, %d, %s, %s" % (theKey, theWBS, theFY, theSPs, theSmr, theCcl)
        cells[theWBS][theFY].append(EpicEntry(theKey, theSmr[3:], theSts, theCcl, theSPs, blkdBy))
        print "PLANNING;%s;%s;%d;%s" %(theFY, theKey, theSPs, theSmr[3:])
    else:
        orphans.append(EpicEntry(theKey, theSmr, theSts, 'Y', theSPs, blkdBy))
        #print "ORPHAN: %s, %s, %s, %s" % (theKey, theWBS, theFY, theSmr)

theHTML = '''
<html>
<head>
<title>LDM-240 for 02C.06</title>

<style>
    .col14 {display: table-cell; }
    .col15 {display: table-cell; }
    .col16 {display: table-cell; }
    .col17 {display: table-cell; }
    .col18 {display: table-cell; }
    .col19 {display: table-cell; }
    .col20 {display: table-cell; }

    table.show14 .col14 { display: none; }
    table.show15 .col15 { display: none; }
    table.show16 .col16 { display: none; }
    table.show17 .col17 { display: none; }
    table.show18 .col18 { display: none; }
    table.show19 .col19 { display: none; }
    table.show20 .col20 { display: none; }
</style>

<script>
function toggleColumn(n) {
    var currentClass = document.getElementById("mytable").className;
    if (currentClass.indexOf("show"+n) != -1) {
        document.getElementById("mytable").className = currentClass.replace("show"+n, "");
    } else {
        document.getElementById("mytable").className += " " + "show"+n;
    }
}
</script>

</head>
<body>

<p><a href="http://rook.swinbank.org:8080/wbs/02C.06*">Dependency graph for milestones</a></p>

<p>Press to turn off/on a given column:
<table border="1">
  <tr>
    <td onclick="toggleColumn(14)">FY14</td>
    <td onclick="toggleColumn(15)">FY15</td>
    <td onclick="toggleColumn(16)">FY16</td>
    <td onclick="toggleColumn(17)">FY17</td>
    <td onclick="toggleColumn(18)">FY18</td>
    <td onclick="toggleColumn(19)">FY19</td>
    <td onclick="toggleColumn(20)">FY20</td>
  </tr>
</table></p>


<table id="mytable" border='1'>
  <tr>
    <td bgcolor="#BEBEBE"></td>'''
for fy in fys:
    theHTML += '''
    <td class="col%s" bgcolor="#BEBEBE" align='middle' width='15%%'>%s</td>''' % (fy[2:], fy)
theHTML += '''
  </tr>'''


# now the DLP row with milestones
theHTML += '''
  <tr>
    <td width="10%" bgcolor="#BEBEBE" valign="top">DLP milestones</td>'''
for fy in fys:
    theHTML += '''
    <td class="col%s" valign="top" bgcolor="#7DDB90">
      <ul style="list-item-style:none; margin-left:0px;padding-left:20px;">''' % fy[2:]
    for e in dlpMilestonesArr[fy]:
        theHTML += '''
        <li><a href="https://jira.lsstcorp.org/browse/%s">%s</a></li>''' % (e.key, e.summary)
    theHTML += '''
      </ul></td>
'''
theHTML += '''</tr>
'''

for row in cells:
    theHTML += '''
  <tr>
    <td valign="top" bgcolor="#BEBEBE">%s<br>%s</td>''' % (row, wbses[row])
    fyN = 14
    for col in cells[row]:
        cellContent = cells[row][col]
        if len(cellContent) == 0:
            theHTML += '''
    <td class="col%d" valign="top">&nbsp;</td>''' % fyN
        else:
            theHTML += '''
    <td class="col%d" valign="top">
      <ul style="list-item-style:none; margin-left:0px;padding-left:20px;">''' % fyN
            for cycle in ('A', 'B', 'Y'): # sort epics by cycle
                for epic in cellContent:
                    if epic.cycle == cycle:
                        theHTML += '''
        <li>%s</li>''' % genEpicLine(epic)
                        if len(epic.blockedBy) > 0:
                            theHTML += '''
          <ul>'''
                            for bEpic in epic.blockedBy:
                                theHTML += '''
            <li><small><i>%s</i></small></li>''' % genEpicLine(bEpic)
                            theHTML += '''
          </ul>'''
            theHTML += '''
      </ul></td>'''
        fyN += 1
    theHTML += '''
  </tr>'''



theHTML += '''
</table>

<p>Breakdown of story points per FY:
<table border='1'>
    <tr>
      <td align='middle'>FY
      <td align='middle'>story points
      <td align='middle'>SP-based FTE-months
      <td align='middle'>SP-based FTE-years
      <td align='middle'>FTE-years w/overhead
'''
for fy in fys:
    theHTML += '''
    <tr><td align='middle'>%s<td align='middle'>%d<td align='middle'>%d<td align='middle'>%0.1f<td align='middle'>%0.1f''' % (fy, spsArr[fy], spsArr[fy]/26.3, spsArr[fy]/26.3/12, spsArr[fy]/26.3/12/0.7)

theHTML += '''
</table>

<p>The following did not make it to the above table:
  <ul>'''

for o in orphans:
    theHTML += '''
    <li><a href="https://jira.lsstcorp.org/browse/%s">%s</a></li>''' % \
          (o.key, o.summary)
theHTML += '''
</ul></p>
<p>
Explanation: orange color - winter cycle, green color - summer cycle, blue color - cycle not specified.</p>

The numbers next to epics in brackets: effort expressed in FTE-months, where 1 FTE month = 26.3 story points

</body>
</html>
'''

if outFileName != "/dev/null":
    f = open(outFileName, "w")
    f.write(theHTML)
    f.close()
