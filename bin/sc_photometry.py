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

def filterSources(sources, md, bright, flags=0x80):
    if isinstance(sources, afwDet.PersistableSourceVector):
        sources = sources.getSources()
    calib = afwImage.Calib(md)
    wcs = afwImage.makeWcs(md)
    offsets = numpy.ndarray(len(sources))
    outSources = afwDet.SourceSet()
    for i, src in enumerate(sources):
        try:
#            psfMag = calib.getMagnitude(src.getPsfFlux())
            apMag = calib.getMagnitude(src.getApFlux())
#            modelMag = calib.getMagnitude(src.getModelFlux())
        except:
            continue

        if bright is not None and apMag > bright:
            continue

        if src.getFlagForDetection() & flags == 0:
            continue

#        src.setPsfFlux(psfMag)
#        src.setApFlux(apMag)
#        src.setModelFlux(modelMag)

        x, y = src.getXAstrom(), src.getYAstrom()
        #if x < 5 or x > 2043 or y < 5 or y > 4172:
        #    src.setRa(4.32)
        #    src.setDec(0.0)
        #    continue
        sky = wcs.pixelToSky(x, y)
        src.setRa(sky[0])
        src.setDec(sky[1])
#        x1, y1 = src.getXAstrom(), src.getYAstrom()
#        sky = wcs.pixelToSky(x1, y1)
#        pix = wcs.skyToPixel(sky)
#        offsets[i] = math.hypot(pix.getX()-x1, pix.getY()-y1)
        outSources.push_back(src)
#    print offsets.mean(), offsets.std()
    return outSources

def run(outName, rerun, frame1, frame2, config, matchTol=1.0, bright=None, ccd=None):
    io = pipReadWrite.ReadWrite(hscSim.HscSimMapper(rerun=rerun),
                                ['visit'], fileKeys=['visit', 'ccd'], config=config)
    roots = config['roots']
    outName = os.path.join(roots['output'], '%s.pdf' % outName) if outName is not None else None

    data1 = {'visit': frame1}
    data2 = {'visit': frame2}
    if ccd is not None:
        data1['ccd'] = ccd
        data2['ccd'] = ccd

    sources1 = io.read('src', data1, ignore=True)
    md1 = io.read('calexp_md', data1, ignore=True)
    sources2 = io.read('src', data2, ignore=True)
    md2 = io.read('calexp_md', data2, ignore=True)


    assert len(sources1) == len(md1)
    for i in range(len(sources1)):
        sources1[i] = filterSources(sources1[i], md1[i], bright)
    sources1 = concatenate(sources1)
    print len(sources1), "sources filtered from", frame1

    assert len(sources2) == len(md2)
    for i in range(len(sources2)):
        sources2[i] = filterSources(sources2[i], md2[i], bright)
    sources2 = concatenate(sources2)
    print len(sources2), "sources filtered from", frame2

    comp = pipCompare.Comparisons(sources1, sources2, matchTol=matchTol)
    print "%d matches" % comp.num

    ra = (comp['ra1'] + comp['ra2']) / 2.0
    dec = (comp['dec1'] + comp['dec2']) / 2.0

    if False:
        psfAvg = (comp['psf1'] + comp['psf2']) / 2.0
        psfDiff = comp['psf1'] - comp['psf2']
        apAvg = (comp['ap1'] + comp['ap2']) / 2.0
        apDiff = comp['ap1'] - comp['ap2']
        modelAvg = (comp['model1'] + comp['model2']) / 2.0
        modelDiff = comp['model1'] - comp['model2']
    else:
        psfAvg = (-2.5*numpy.log10(comp['psf1']) -2.5*numpy.log10(comp['psf2'])) / 2.0
        psfDiff = -2.5*numpy.log10(comp['psf1']) + 2.5*numpy.log10(comp['psf2'])
        apAvg = (-2.5*numpy.log10(comp['ap1']) - 2.5*numpy.log10(comp['ap2'])) / 2.0
        apDiff = (-2.5*numpy.log10(comp['ap1']) + 2.5*numpy.log10(comp['ap2']))
        modelAvg = (-2.5*numpy.log10(comp['model1']) - 2.5*numpy.log10(comp['model2'])) / 2.0
        modelDiff = (-2.5*numpy.log10(comp['model1']) + 2.5*numpy.log10(comp['model2']))


    plot = plotter.Plotter(outName)
    plot.xy(ra, dec, title="Detections")
    plot.xy(psfAvg, psfDiff, axis=[comp['psf1'].min(), comp['psf1'].max(), -0.25, 0.25],
            title="PSF photometry")
    plot.xy(apAvg, apDiff, axis=[comp['ap1'].min(), comp['ap1'].max(), -0.25, 0.25],
            title="Aperture photometry")
    plot.histogram(psfDiff, [-0.25, 0.25], title="PSF photometry")
    plot.histogram(apDiff, [-0.25, 0.25], title="Aperture photometry")
    plot.histogram(modelDiff, [-0.25, 0.25], title="Model photometry")

    plot.xy(psfAvg, modelAvg - psfAvg, title="PSF vs Model")
    plot.histogram(modelAvg - psfAvg, [-0.6, 0.2], bins=81, title="PSF vs Model")

    plot.xy2(ra, comp['distance'], dec, comp['distance'],
             axis1=[ra.min(), ra.max(), 0, matchTol], axis2=[dec.min(), dec.max(), 0, matchTol],
             title1="Right ascension", title2="Declination")

    plot.quivers(ra, dec, comp['ra1'] - comp['ra2'], comp['dec1'] - comp['dec2'], title="Astrometry", addUnitQuiver=1.0/3600.0)

    plot.close()



    

def concatenate(listOfLists):
    newList = list()
    for index, eachList in enumerate(listOfLists):
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
    parser.add_option("--save", type="string", default=None, dest="output", help="Output name for plot")

    defaults = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam.paf")
    config, opts, args = parser.parse_args([defaults, overrides])
    frame1 = args[0]
    frame2 = args[1]

    run(opts.output, opts.rerun, int(frame1), int(frame2), config,
        matchTol=opts.match, bright=opts.bright, ccd=opts.ccd)
