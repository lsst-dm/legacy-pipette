#!/usr/bin/env python

import os
import sys

import lsst.obs.hscSim as obsHsc
import lsst.pipette.config as pipConfig
import lsst.pipette.processCcd as pipCcd
import lsst.pipette.options as pipOptions
import lsst.pipette.catalog as pipCatalog
import lsst.pipette.readwrite as pipReadWrite

import lsst.pipette.ioHacks as pipExtraIO

#from IPython.core.debugger import Tracer;
#debug_here = Tracer()

class DeferredHSCState(object):
    def __init__(self, dataId, io, matchlist, sources, exposure):
        self.dataId = dataId
        self.io = io
        self.matchlist = matchlist
        self.sources = sources
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
    mapper = obsHsc.HscSimMapper(rerun=rerun)
    io = pipReadWrite.ReadWrite(mapper,
                                ['visit', 'ccd'],
                                config=config)
    roots = config['roots']
    oldUmask = os.umask(2)
    if oldUmask != 2:
        io.log.log(io.log.WARN, "pipette umask started as: %s" % (os.umask(2)))

    ccdProc = pipCcd.ProcessCcd(config=config)
    dataId = { 'visit': frame, 'ccd': ccd }

    raws = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    
    exposure, psf, apcorr, sources, matches, matchMeta = ccdProc.run(raws, detrends)
    defer = True
    if defer:
        io.write(dataId, exposure=None, psf=psf, sources=None, matches=matches, matchMeta=matchMeta)
    else:
        io.write(dataId, exposure=exposure, psf=psf, sources=sources, matches=matches, matchMeta=matchMeta)

    catPolicy = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "catalog.paf")
    catalog = pipCatalog.Catalog(catPolicy, allowNonfinite=False)

    # Write SRC....fits files here, until we can push the scheme into a butler.
    metadata = exposure.getMetadata()
    hdrInfo = dict([(m, metadata.get(m)) for m in metadata.names()])

    filename = io.outButler.get('source_filename', dataId)[0]
    io.log.log(io.log.INFO, "writing sources to: %s" % (filename))
    pipExtraIO.writeSourceSetAsFits(sources, filename, hdrInfo=hdrInfo, clobber=True)

    #filename = io.outButler.get('match_filename', dataId)[0]
    #io.log.log(io.log.INFO, "writing matches to: %s" % (filename))
    #pipExtraIO.writeSourceSetAsFits(sources, filename, hdrInfo=hdrInfo, clobber=True)
            
    deferredState = DeferredHSCState(dataId, io, matches, sources, exposure)
    return deferredState

def doMergeWcs(deferredState, wcs):
    exposure = deferredState.exposure
    if not wcs:
        wcs = exposure.getWcs()
        deferredState.io.log.log(deferredState.io.log.WARN, "!!!!! stuffing exposure with its own wcs.!!!")

    # Apply WCS to sources
    sources = deferredState.sources
    for source in sources:
        sky = wcs.pixelToSky(source.getXAstrom(), source.getYAstrom())
        source.setRa(sky[0])
        source.setDec(sky[1])
                                                            
    exposure.setWcs(wcs)
    deferredState.io.write(deferredState.dataId, sources=sources, exposure=exposure)

def getConfig():
    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "hsc.paf")
    config = pipConfig.configuration(default, overrides)

    return config

def doRun(rerun=None, frameId=None, ccdId=None, doMerge=False, doBreak=False):
    if doBreak:
        import pdb; pdb.set_trace()
    config = getConfig()
    state = run(rerun, frameId, ccdId, config)

    if doMerge:
        doMergeWcs(state, None)
    else:
        return state

def main(argv=None):
    
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frame", dest="frame",
                      help="visit to run (default=%default)")
    parser.add_option("-c", "--ccd", dest="ccd",
                      help="CCD to run (default=%default)")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "hsc.paf")
    config, opts, args = parser.parse_args([default, overrides], argv=argv)
    if len(args) > 0 or opts.rerun is None or opts.frame is None or opts.ccd is None:
        parser.print_help()
        sys.exit(1)

    state = run(opts.rerun, int(opts.frame), int(opts.ccd), config)
    doMergeWcs(state, None)

    

if __name__ == "__main__":
    main()
