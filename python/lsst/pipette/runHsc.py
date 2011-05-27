#!/usr/bin/env python

import os
import sys

import lsst.pex.logging as pexLog
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
        log = pexLog.Log.getDefaultLog(), # Log object
    ):

    # Make our own mappers for now
    mapperArgs = {'rerun': rerun}       # Arguments for mapper instantiation

    if config.has_key('roots'):
        roots = config['roots']
        for key, value in {'data': 'root',
                           'calib': 'calibRoot',
                           'output': 'outRoot'}.iteritems():
            if roots.has_key(key):
                mapperArgs[value] = roots[key]
    
    camera = config['camera']
    if camera.lower() in ("hsc"):
        mapper = obsHsc.HscSimMapper(**mapperArgs)
        ccdProc = pipCcd.ProcessCcd(config=config, Calibrate=HscCalibrate, log=log)
    elif camera.lower() in ("suprimecam", "suprime-cam", "sc"):
        mapper = obsSc.SuprimecamMapper(**mapperArgs)
        ccdProc = pipCcd.ProcessCcd(config=config, log=log)
        
    io = pipReadWrite.ReadWrite(mapper, ['visit', 'ccd'], config=config)

    oldUmask = os.umask(2)
    if oldUmask != 2:
        io.log.log(io.log.WARN, "pipette umask started as: %s" % (os.umask(2)))

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
        source.setRaDec(wcs.pixelToSky(source.getXAstrom(), source.getYAstrom()))

    brightSources = deferredState.brightSources
    for source in brightSources:
        source.setRaDec(wcs.pixelToSky(source.getXAstrom(), source.getYAstrom()))

    # The matchedList sources are _not_ the same as in the source lists.
    # uhh, they should be --dstn
    for sourceMatch in matchlist:
        # _Only_ convert the .second source, which is our measured source.
        source = sourceMatch.second
        source.setRaDec(wcs.pixelToSky(source.getXAstrom(), source.getYAstrom()))

    # Write SRC....fits files here, until we can push the scheme into a butler.
    if sources:
        metadata = exposure.getMetadata()
        hdrInfo = dict([(m, metadata.get(m)) for m in metadata.names()])
        filename = io.outButler.get('source_filename', dataId)[0]
        io.log.log(io.log.INFO, "writing sources to: %s" % (filename))
        pipExtraIO.writeSourceSetAsFits(sources, filename, hdrInfo=hdrInfo, clobber=True)

    filename = io.outButler.get('matchFull_filename', dataId)[0]
    io.log.log(io.log.INFO, "writing match debugging info to: %s" % (filename))
    try:
        pipExtraIO.writeMatchListAsFits(matchlist, filename)
    except Exception, e:
        print "failed to write matchlist: %s" % (e)
        
    deferredState.io.write(deferredState.dataId, sources=sources, exposure=exposure,
                           matches=matchlist,
                           matchMeta=deferredState.matchMeta)

    
def getConfig(argv=None):
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frame", dest="frame",
                      help="visit to run (default=%default)")
    parser.add_option("-c", "--ccd", dest="ccd",
                      help="CCD to run (default=%default)")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    #if argv == None:
    #    argv = sys.argv

    config, opts, args = parser.parse_args([default], argv=argv)
    if (len(args) > 0 # or opts.instrument is None
        or opts.rerun is None
        or opts.frame is None
        or opts.ccd is None):

        parser.print_help()
        print "argv was: %s" % (argv)
        return None, None, None

    return config, opts, args

def doRun(rerun=None, frameId=None, ccdId=None,
          doMerge=True, doBreak=False,
          instrument="hsc",
	  output=None,
	  data=None,
	  calib=None,
          log = pexLog.Log.getDefaultLog() # Log object
          ):
    argv = []
    argv.extend(["--instrument=%s" % (instrument),
                 "--frame=%s" % (frameId),
                 "--ccd=%s" % (ccdId)])

    if output:
	argv.append("--output=%s" % (output))
    if data:
	argv.append("--data=%s" % (data))
    if calib:
	argv.append("--calib=%s" % (calib))
    
    if rerun:
        argv.append("--rerun=%s" % (rerun))
                
    if doBreak:
        import pdb; pdb.set_trace()

    config, opts, args = getConfig(argv=argv)

    state = run(rerun, frameId, ccdId, config, log=log)

    if doMerge:
        doMergeWcs(state, None)
    else:
        return state

def main(argv=None):
    config, opts, args = getConfig(argv=argv)
    if not config:
        raise SystemExit("argument parsing error")
    
    state = run(opts.rerun, int(opts.frame), int(opts.ccd), config)
    doMergeWcs(state, None)

if __name__ == "__main__":
    main()
