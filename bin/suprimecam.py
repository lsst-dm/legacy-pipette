#!/usr/bin/env python

import os
import sys

import lsst.pex.logging as pexLog
import lsst.obs.suprimecam as suprimecam
import lsst.pipette.config as pipConfig
import lsst.pipette.processCcd as pipProcCcd
import lsst.pipette.options as pipOptions
import lsst.pipette.catalog as pipCatalog
import lsst.pipette.readwrite as pipReadWrite
import lsst.pipette.specific.suprimecam as pipSuprimeCam

def run(rerun,                          # Rerun name
        frame,                          # Frame number
        ccd,                            # CCD number
        config,                         # Configuration
        log = pexLog.Log.getDefaultLog(), # Log object
        ):

    roots = config['roots']
    registry = os.path.join(roots['data'], 'registry.sqlite3')
    imapp = suprimecam.SuprimecamMapper(rerun=rerun, root=roots['data'], calibRoot=roots['calib'])
    omapp = suprimecam.SuprimecamMapper(rerun=rerun, root=roots['output'], calibRoot=roots['calib'],
					registry=registry)
    io = pipReadWrite.ReadWrite([imapp, omapp], ['visit', 'ccd'], config=config)
    ccdProc = pipProcCcd.ProcessCcd(config=config, Isr=pipSuprimeCam.IsrSuprimeCam, log=log)
    dataId = { 'visit': frame, 'ccd': ccd }

    raws = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    exposure, psf, apcorr, brightSources, sources, matches, matchMeta = ccdProc.run(raws, detrends)
    io.write(dataId, exposure=exposure, psf=psf, sources=sources, matches=matches, matchMeta=matchMeta)

    catPolicy = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "catalog.paf")
    catalog = pipCatalog.Catalog(catPolicy, allowNonfinite=False)
    basename = os.path.join(roots['output'], '%s-%d%d' % (rerun, frame, ccd))
    if sources is not None:
        catalog.writeSources(basename + '.sources', sources, 'sources')
    if matches is not None:
        catalog.writeMatches(basename + '.matches', matches, 'sources')
    return


def getConfig(overrideFile=None):
    """Return a proper config object, maybe given the name of policy file with an additional set of overrides"""
    
    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam.paf")
    config = pipConfig.configuration(default, overrides)
    if overrideFile:
        config.merge(pipConfig.Config(overrideFile))

    return config


if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frame", dest="frame",
                      help="visit to run (default=%default)")
    parser.add_option("-c", "--ccd", dest="ccd",
                      help="CCD to run (default=%default)")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frame is None or opts.ccd is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, int(opts.frame), int(opts.ccd), config)
