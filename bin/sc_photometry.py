#!/usr/bin/env python

import os
import math

import matplotlib
#matplotlib.use('pdf')
import matplotlib.colors
import matplotlib.pyplot as plot

import lsst.pex.logging as pexLog
import lsst.obs.suprime as suprime
import lsst.afw.detection as afwDet

import lsst.pipette.run.options as runOptions
import lsst.pipette.run.readwrite as runReadWrite
import lsst.pipette.run.comparisons as runCompare




def run(outName, frame1, frame2, config, matchTol=1.0):
    io = runReadWrite.ReadWrite(suprime.SuprimeMapper, ['visit'], fileKeys=['visit', 'ccd'], config=config)
    roots = config['roots']
    output = os.path.join(roots['output'], '%s.pdf' % outName)
    sources1 = concatenate(io.read('src', {'visit': frame1}))
    print len(sources1), "sources read from", frame1
    sources2 = concatenate(io.read('src', {'visit': frame2}))
    print len(sources2), "sources read from", frame2
    matches = afwDet.matchRaDec(sources1, sources2, matchTol)
    print len(matches), "matches"
    comp = runCompare.Comparisons(matches)
    #plot.plot(comp['ra'], comp['dec'], 'ro')
    #plot.plot(comp['psfAvg'], comp['psfDiff'], 'rx')
    norm = matplotlib.colors.LogNorm(0.01, 1.0, True)
    plot.hsv
    scat = plot.scatter(comp['psfAvg'], comp['psfDiff'], c=comp['distance'], norm=norm, alpha=0.1)
    plot.axis([-16, -7, -1, 1])
    plot.show()
    plot.savefig(output, format="pdf")
    return


def concatenate(listOfLists):
    newList = list()
    for eachList in listOfLists:
        for thing in eachList:
            newList.append(thing)
    return newList

def extract(listOfDicts, name):
    newList = list()
    for eachDict in listOfDicts:
        newList.append(eachDict[name])
    return newList

if __name__ == "__main__":
    parser = runOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")

    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "suprimecam.paf")
    config, opts, args = parser.parse_args(overrides)
    frame1 = args[0]
    frame2 = args[1]
    outName = args[2]

    run(outName, int(frame1), int(frame2), config)
