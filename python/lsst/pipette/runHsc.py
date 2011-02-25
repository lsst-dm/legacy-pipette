#!/usr/bin/env python

import os
import sys

import lsst.obs.hscSim as obsHsc
import lsst.pipette.config as pipConfig
import lsst.pipette.processCcd as pipCcd
import lsst.pipette.options as pipOptions
import lsst.pipette.catalog as pipCatalog
import lsst.pipette.readwrite as pipReadWrite

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
    inMapper = obsHsc.HscSimMapper()
    outMapper = obsHsc.HscSimMapper(rerun=rerun)
    io = pipReadWrite.ReadWrite([inMapper, outMapper],
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
    # I don't know how to get the full ID out of the butler, so reconstruct
    dataId['filter'] = raws[0].getMetadata().getAsString('FILTER01').strip()
    dataId['pointing'] = frame / 10
    
    exposure, psf, apcorr, sources, matches = ccdProc.run(raws, detrends)
    defer = True
    if defer:
        io.write(dataId, exposure=None, psf=psf, sources=None, matches=matches)
    else:
        io.write(dataId, exposure=exposure, psf=psf, sources=sources, matches=matches)

    catPolicy = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "catalog.paf")
    catalog = pipCatalog.Catalog(catPolicy, allowNonfinite=False)

    if not "needs to use outMapper":
        basename = os.path.join(roots['output'], '%s-%d%d' % (rerun, frame, ccd))
        if sources is not None:
            catalog.writeSources(basename + '.sources', sources, 'sources')
        if matches is not None:
            catalog.writeMatches(basename + '.matches', matches, 'sources')

    deferredState = DeferredHSCState(dataId, io, matches, sources, exposure)
    io.log.log(io.log.WARN, "state: %s" % (deferredState))
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
