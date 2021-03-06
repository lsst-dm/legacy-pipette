#!/usr/bin/env python

import os
import sys

import lsst.pex.logging as pexLog
import lsst.obs.lsstSim as lsstSim
import lsst.pipette.config as pipConfig
import lsst.pipette.processCcd as pipProcCcd
import lsst.pipette.options as pipOptions
import lsst.pipette.catalog as pipCatalog
import lsst.pipette.readwrite as pipReadWrite


def run(rerun,                          # Rerun name
        visit,                          # Visit number
        snap,                           # Snap number
        raft,                           # Raft id
        sensor,                         # Sensor id
        config,                         # Configuration
        log = pexLog.Log.getDefaultLog() # Log object
        ):
    io = pipReadWrite.ReadWrite(lsstSim.LsstSimMapper, ['visit', 'snap', 'raft', 'sensor'],
                                fileKeys=['visit', 'snap', 'raft', 'sensor', 'channel'], config=config)
    roots = config['roots']
    basename = os.path.join(roots['output'], '%s-%d-%d-%s-%s' % (rerun, visit, snap, raft, sensor))
    ccdProc = pipProcCcd.ProcessCcd(config=config, log=log)
    dataId = {'visit': visit, 'snap': snap, 'raft': raft, 'sensor': sensor}

    detrends = io.detrends(dataId, config)
    if len([x for x in detrends if x]): # We need to run at least part of the ISR
        raws = io.readRaw(dataId)
    else:
        io.fileKeys = ['visit', 'raft', 'sensor']
        raws = io.read('calexp', dataId)
        detrends = None

    exposure, psf, brightSources, apcorr, sources, matches, matchMeta = ccdProc.run(raws, detrends)
    
    io.write(dataId, exposure=exposure, psf=psf, sources=sources, matches=matches, matchMeta=matchMeta)

    catPolicy = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "catalog.paf")
    catalog = pipCatalog.Catalog(catPolicy, allowNonfinite=False)
    if sources is not None:
        catalog.writeSources(basename + '.sources', sources, 'sources')
    if matches is not None:
        catalog.writeMatches(basename + '.matches', matches, 'sources')
    return

def getConfig(overrideFile=None):
    """Return a proper config object, maybe given the name of policy file with an additional set of overrides"""
    
    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "lsstSim.paf")
    config = pipConfig.configuration(default, overrides)
    if overrideFile:
        config.merge(pipConfig.Config(overrideFile))

    return config

if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="Rerun name (default=%default)")
    parser.add_option("-v", "--visit", dest="visit", help="Visit to run")
    parser.add_option("-S", "--snap", dest="snap", help="Snap to run")
    parser.add_option("-r", "--raft", dest="raft", help="Raft to run")
    parser.add_option("-s", "--sensor", dest="sensor", help="Sensor to run")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "lsstSim.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0:
        print >> sys.stderr, 'Unrecognized arguments: "%s"' % '", '.join(args)
        sys.exit(1)
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    if not opts.rerun:
        print >> sys.stderr, "Please specify a rerun"
        sys.exit(1)
    if not opts.visit:
        print >> sys.stderr, "Please specify a visit"
        sys.exit(1)
    if not opts.snap:
        print >> sys.stderr, "Please specify a snap"
        sys.exit(1)
    if not opts.raft:
        print >> sys.stderr, "Please specify a raft"
        sys.exit(1)
    if not opts.sensor:
        print >> sys.stderr, "Please specify a sensor"
        sys.exit(1)

    run(opts.rerun, int(opts.visit), int(opts.snap), opts.raft, opts.sensor, config)
