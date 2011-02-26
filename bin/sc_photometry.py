#!/usr/bin/env python

import os
import math

import numpy

import lsst.obs.suprimecam as suprimecam
import lsst.obs.hscSim as hscSim
import lsst.afw.detection as afwDet
import lsst.afw.image as afwImage
import lsst.afw.display.ds9 as ds9

import lsst.pipette.options as pipOptions
import lsst.pipette.readwrite as pipReadWrite
import lsst.pipette.comparisons as pipCompare
import lsst.pipette.plotter as plotter
    
def setRaDec(sources, exposure):
    if isinstance(sources, afwDet.PersistableSourceVector):
        sources = sources.getSources()
    exposure # Evaluate to force read of proxy
    wcs = afwImage.makeWcs(exposure)
    offsets = numpy.ndarray(len(sources))
    for i, src in enumerate(sources):
        x, y = src.getXAstrom(), src.getYAstrom()
        #if x < 5 or x > 2043 or y < 5 or y > 4172:
        #    src.setRa(4.32)
        #    src.setDec(0.0)
        #    continue
        sky = wcs.pixelToSky(x, y)
        src.setRa(sky[0])
        src.setDec(sky[1])

        x1, y1 = src.getXAstrom(), src.getYAstrom()
        sky = wcs.pixelToSky(x1, y1)
        pix = wcs.skyToPixel(sky)
        offsets[i] = math.hypot(pix.getX()-x1, pix.getY()-y1)
    print offsets.mean(), offsets.std()

def run(outName, rerun, frame1, frame2, config, matchTol=1.0, bright=None, ccd=None):
    io = pipReadWrite.ReadWrite(hscSim.HscSimMapper(rerun=rerun),
                                ['visit'], fileKeys=['visit', 'ccd'], config=config)
    roots = config['roots']
    output = os.path.join(roots['output'], '%s.pdf' % outName)

    data1 = {'visit': frame1}
    data2 = {'visit': frame2}
    if ccd is not None:
        data1['ccd'] = ccd
        data2['ccd'] = ccd

    sources1 = io.read('src', data1)
    sources2 = io.read('src', data2)
    exp1 = io.read('calexp_md', data1)
    exp2 = io.read('calexp_md', data2)
    for index, (sources, exp) in enumerate(zip(sources1, exp1)):
        if index >= 100:
            continue
        exp
        setRaDec(sources, exp)
        
    for index, (sources, exp) in enumerate(zip(sources2, exp2)):
        if index >= 100:
            continue
        exp
        setRaDec(sources, exp)
           
    sources1 = concatenate(sources1)
    sources2 = concatenate(sources2)

    print len(sources1), "sources read from", frame1
    print len(sources2), "sources read from", frame2

    comp = pipCompare.Comparisons(sources1, sources2, matchTol=matchTol, bright=bright)
    print "%d matches" % comp.num

    plot = plotter.Plotter(output)
    plot.xy(comp['ra'], comp['dec'], title="Detections")
    plot.xy(comp['psfAvg'], comp['psfDiff'], axis=[-16, -7, -0.25, 0.25], title="PSF photometry")
    plot.xy(comp['apAvg'], comp['apDiff'], axis=[-16, -7, -0.25, 0.25], title="Aperture photometry")
    plot.histogram(comp['psfDiff'], range=[-0.25, 0.25], bins=51, mean=0.0, sigma=0.02, title="PSF photometry")
    plot.histogram(comp['apDiff'], range=[-0.25, 0.25], bins=51, mean=0.0, sigma=0.02, title="Aperture photometry")

    plot.xy2(comp['ra'], comp['distance'],
             comp['dec'], comp['distance'],
             axis1=[comp['ra'].min(), comp['ra'].max(), 0, matchTol],
             axis2=[comp['dec'].min(), comp['dec'].max(), 0, matchTol],
             title1="Right ascension", title2="Declination")

    plot.quivers(comp['ra'], comp['dec'],
                 comp['ra1'] - comp['ra2'], comp['dec1'] - comp['dec2'],
                 title="Astrometry")

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
    parser.add_option("-b", "--bright", type='float', default=None, dest="bright",
                      help="Bright limit (instmag)")
    parser.add_option("-m", "--match", type='float', default=None, dest="match",
                      help="Match radius (arcsec)")
    parser.add_option("-c", "--ccd", type='int', default=None, dest="ccd", help="CCD to use")

    defaults = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam.paf")
    config, opts, args = parser.parse_args([defaults, overrides])
    frame1 = args[0]
    frame2 = args[1]
    outName = args[2]

    run(outName, opts.rerun, int(frame1), int(frame2), config,
        matchTol=opts.match, bright=opts.bright, ccd=opts.ccd)
