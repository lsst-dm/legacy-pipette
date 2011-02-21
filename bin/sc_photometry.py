#!/usr/bin/env python

import os
import math

import matplotlib
matplotlib.use('pdf')
import matplotlib.backends.backend_pdf
import matplotlib.pyplot as plot

import numpy
import numpy.ma

import lsst.pex.logging as pexLog
import lsst.obs.suprimecam as suprimecam
import lsst.obs.hscSim as hscSim
import lsst.afw.detection as afwDet

import lsst.pipette.options as pipOptions
import lsst.pipette.readwrite as pipReadWrite
import lsst.pipette.comparisons as pipCompare


def gaussian(param, x):
    norm = param[0]
    offset = param[1]
    width = param[2]
    return norm * numpy.exp(-((x - offset)/width)**2)    
    

def run(outName, frame1, frame2, config, matchTol=1.0, ccd=None):
    io = pipReadWrite.ReadWrite(hscSim.HscSimMapper, ['visit'], fileKeys=['visit', 'ccd'], config=config)
    roots = config['roots']
    output = os.path.join(roots['output'], '%s.pdf' % outName)

    if ccd is None:
        # Use entire exposure
        sources1 = concatenate(io.read('src', {'visit': frame1}))
        sources2 = concatenate(io.read('src', {'visit': frame2}))
    else:
        # Use single ccd
        sources1 = io.read('src', {'visit': frame1, 'ccd': ccd})[0].getSources()
        sources2 = io.read('src', {'visit': frame2, 'ccd': ccd})[0].getSources()

    print len(sources1), "sources read from", frame1
    print len(sources2), "sources read from", frame2
    matches = afwDet.matchRaDec(sources1, sources2, matchTol)
    print len(matches), "matches"
    comp = pipCompare.Comparisons(matches)

    pdf = matplotlib.backends.backend_pdf.PdfPages(output)
   
#    plot.figure()
#    plot.plot(comp['ra'], comp['dec'], 'ro')
#    pdf.savefig()
#    plot.close()

    plot_xy(comp, 'psfAvg', 'psfDiff', [-16, -7, -0.25, 0.25], "PSF photometry", pdf=pdf)
    plot_xy(comp, 'apAvg', 'apDiff', [-16, -7, -0.25, 0.25], "Aperture photometry", pdf=pdf)

    plot_histogram(comp, 'psfDiff', range=[-0.25, 0.25], bins=51, brightName='psfAvg', brightLimit=-12, title="PSF photometry", pdf=pdf)
    plot_histogram(comp, 'apDiff', range=[-0.25, 0.25], bins=51, brightName='apAvg', brightLimit=-12, title="Aperture photometry", pdf=pdf)

    pdf.close()


def plot_xy(comparisons, xName, yName, axis, title=None, pdf=None):
    plot.figure()
    scat = plot.scatter(comparisons[xName], comparisons[yName], marker='x')
    plot.axis(axis)
    if title is not None:
        plot.title(title)
    if pdf is not None:
        pdf.savefig()
    plot.close()

def plot_histogram(comparisons, histName, range=[-0.25, 0.25], bins=51, brightName=None, brightLimit=-12, title=None, pdf=None):
    plot.figure()
    mask = numpy.isnan(comparisons[histName])
    if brightName is not None:
        mask = numpy.bitwise_or(mask, comparisons[brightName] > brightLimit)
    diff = numpy.ma.masked_array(comparisons[histName], mask)
    n, bins, patches = plot.hist(diff.compressed(), bins=bins, range=range, normed=False, histtype='bar', align='mid')
    norm = n.max()
    gauss = gaussian([norm, 0.0, 0.02], bins)
    plot.plot(bins, gauss, 'r-')
    if title is not None:
        plot.title(title)
    if pdf is not None:
        pdf.savefig()
    plot.close()
    

def concatenate(listOfLists):
    newList = list()
    for index, eachList in enumerate(listOfLists):
        if index >= 100:
            continue
        if isinstance(eachList, afwDet.PersistableSourceVector):
            eachList = eachList.getSources()
        for thing in eachList:
            newList.append(thing)
    return newList

def extract(listOfDicts, name):
    newList = list()
    for eachDict in listOfDicts:
        newList.append(eachDict[name])
    return newList

if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-c", "--ccd", type='int', default=None, dest="ccd", help="CCD to use")

    defaults = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam.paf")
    config, opts, args = parser.parse_args(defaults, overrides)
    frame1 = args[0]
    frame2 = args[1]
    outName = args[2]

    run(outName, int(frame1), int(frame2), config, ccd=opts.ccd)
