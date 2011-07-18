#!/usr/bin/env python

import os
import sys
import multiprocessing
import collections

import lsst.pex.logging as pexLog
import lsst.obs.lsstSim as lsstSim
import lsst.pipette.config as pipConfig
import lsst.pipette.processCcd as pipProcCcd
import lsst.pipette.options as pipOptions
import lsst.pipette.catalog as pipCatalog
import lsst.pipette.readwrite as pipReadWrite

Inputs = collections.namedtuple('Inputs', ['rerun', 'visit', 'snap', 'raft', 'sensor', 'config'])

def run(inputs):
    rerun = inputs.rerun
    visit = inputs.visit
    snap = inputs.snap
    raft = inputs.raft
    sensor = inputs.sensor
    config = inputs.config
    log = inputs.log

    pexLog.Log.getDefaultLog().addDestination(log)

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

def require(value, name):
    if not value:
        print >> sys.stderr, "Please specify %s" % name
        sys.exit(1)
 

if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="Rerun name (default=%default)")
    parser.add_option("-v", "--visit", dest="visit", help="Visit to run")
    parser.add_option("-S", "--snap", dest="snap", help="Snap to run")
    parser.add_option("-T", "--threads", dest="threads", help="Number of threads")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "lsstSim.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0:
        print >> sys.stderr, 'Unrecognized arguments: "%s"' % '", '.join(args)
        sys.exit(1)
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    require(opts.rerun, "rerun")
    require(opts.visit, "visit")
    require(opts.snap, "snap")
    require(opts.threads, "threads")

    inputs = list()
    for rx in range(2):
        for ry in range(2):
            if rx,ry in ((0,0), (0,2), (2,0), (2,2)):
                continue
            raft = "%d,%d" % (rx, ry)
            for sx in range(2):
                for sy in range(2):
                    if sx,sy in ((0,0), (0,2), (2,0), (2,2)):
                        continue
                    sensor = "%d,%d" % (sx, sy)
                    logName = "%s.%d%d%d%d.log" % (opts.rerun, rx, ry, sx, sy)
                    inputs.append(Inputs(rerun=opts.rerun, visit=opts.visit, snap=opts.snap,
                                         raft=raft, sensor=sensor, config=config, log=logName))

    pool = multiprocessing.Pool(processes=opts.threads, maxtasks=1)
    pool.map(run, inputs)
    pool.close()
    pool.join()
