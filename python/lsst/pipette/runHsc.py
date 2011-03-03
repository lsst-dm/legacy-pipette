#!/usr/bin/env python

import os
import sys

import lsst.obs.hscSim as obsHsc
import lsst.obs.suprimecam as obsSc
import lsst.pipette.config as pipConfig
import lsst.pipette.processCcd as pipCcd
import lsst.pipette.options as pipOptions
import lsst.pipette.catalog as pipCatalog
import lsst.pipette.readwrite as pipReadWrite

import lsst.pipette.ioHacks as pipExtraIO
from lsst.pipette.hscCalibrate import HscCalibrate

class DeferredHSCState(object):
    def __init__(self, dataId, io, matchlist, matchMeta, sources, brightSources, exposure):
        self.dataId = dataId
        self.io = io
        self.matchlist = matchlist
        self.matchMeta = matchMeta
        self.sources = sources
        self.brightSources = brightSources
        self.exposure = exposure

    def __str__(self):
        return "DeferredHSCState(id=%s, exposure=%s)" % (self.dataId, self.exposure)
    
def run(rerun,                          # Rerun name
        frame,                          # Frame number
        ccd,                            # CCD number
        config,                         # Configuration
    ):

    """ """

    # Make our own mappers for now
    camera = config['camera']
    if camera.lower() in ("hsc"):
        mapper = obsHsc.HscSimMapper(rerun=rerun)
    elif camera.lower() in ("suprimecam", "suprime-cam", "sc"):
        mapper = obsSc.SuprimecamMapper(rerun=rerun)
    io = pipReadWrite.ReadWrite(mapper, ['visit', 'ccd'], config=config)
    roots = config['roots']
    oldUmask = os.umask(2)
    if oldUmask != 2:
        io.log.log(io.log.WARN, "pipette umask started as: %s" % (os.umask(2)))

    ccdProc = pipCcd.ProcessCcd(config=config, Calibrate=HscCalibrate)
    dataId = { 'visit': frame, 'ccd': ccd }

    raws = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    
    exposure, psf, apcorr, brightSources, sources, matches, matchMeta = ccdProc.run(raws, detrends)
    io.write(dataId, exposure=None, psf=psf, sources=None)

    catPolicy = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "catalog.paf")
    catalog = pipCatalog.Catalog(catPolicy, allowNonfinite=False)

    deferredState = DeferredHSCState(dataId, io, matches, matchMeta, sources, brightSources, exposure)
    return deferredState

def doMergeWcs(deferredState, wcs):
    dataId = deferredState.dataId
    io = deferredState.io
    exposure = deferredState.exposure
    matchlist = deferredState.matchlist
    
    if not wcs:
        wcs = exposure.getWcs()
        io.log.log(deferredState.io.log.WARN, "!!!!! stuffing exposure with its own wcs.!!!")

    exposure.setWcs(wcs)

    # Apply WCS to sources
    sources = deferredState.sources
    for source in sources:
        sky = wcs.pixelToSky(source.getXAstrom(), source.getYAstrom())
        source.setRa(sky[0])
        source.setDec(sky[1])

    brightSources = deferredState.brightSources
    for source in brightSources:
        sky = wcs.pixelToSky(source.getXAstrom(), source.getYAstrom())
        source.setRa(sky[0])
        source.setDec(sky[1])

    # The matchedList sources are _not_ the same as in the source lists.
    for sourceMatch in matchlist:
        # _Only_ convert the .second source, which is our measured source.
        source = sourceMatch.second
        sky = wcs.pixelToSky(source.getXAstrom(), source.getYAstrom())
        source.setRa(sky[0])
        source.setDec(sky[1])

    # Write SRC....fits files here, until we can push the scheme into a butler.
    if sources:
        metadata = exposure.getMetadata()
        hdrInfo = dict([(m, metadata.get(m)) for m in metadata.names()])
        filename = io.outButler.get('source_filename', dataId)[0]
        io.log.log(io.log.INFO, "writing sources to: %s" % (filename))
        try:
            pipExtraIO.writeSourceSetAsFits(sources, filename, hdrInfo=hdrInfo, clobber=True)
        except Exception, e:
            print "failed to write sources: %s" % (e)

    filename = io.outButler.get('matchFull_filename', dataId)[0]
    io.log.log(io.log.INFO, "writing match debugging info to: %s" % (filename))
    try:
        pipExtraIO.writeMatchListAsFits(matchlist, filename)
    except Exception, e:
        print "failed to write matchlist: %s" % (e)
        
    deferredState.io.write(deferredState.dataId, sources=sources, exposure=exposure,
                           matches=matchlist,
                           matchMeta=deferredState.matchMeta)

    
def doRun(rerun=None, frameId=None, ccdId=None,
          doMerge=True, doBreak=False,
          instrument="hsc"):
    argv = []
    argv.extend(["runHsc",
                 "--instrument=%s" % (instrument),
                 "--frameId=%s" % (frameId),
                 "--ccdId=%s" % (ccdId)])
    if rerun:
        argv.append("--rerun=" % (rerun))
                
    if doBreak:
        import pdb; pdb.set_trace()

    config, opts, args = getConfig(argv=argv)

    state = run(rerun, frameId, ccdId, config)

    if doMerge:
        doMergeWcs(state, None)
    else:
        return state

def getConfig(argv=None):
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frame", dest="frame",
                      help="visit to run (default=%default)")
    parser.add_option("-c", "--ccd", dest="ccd",
                      help="CCD to run (default=%default)")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    if argv == None:
        argv = sys.argv
    return parser.parse_args([default], argv=argv)

def main(argv=None):
    config, opts, args = getConfig(sys.argv)
    
    if (len(args) > 0 or opts.instrument is None
        or opts.rerun is None
        or opts.frame is None
        or opts.ccd is None):
        
        parser.print_help()
        sys.exit(1)

    state = run(opts.rerun, int(opts.frame), int(opts.ccd), config)
    doMergeWcs(state, None)

if __name__ == "__main__":
    main()
