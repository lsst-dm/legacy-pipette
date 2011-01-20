#!/usr/bin/env python

import os
import sys

import lsst.obs.lsstSim as lsstSim
import lsst.pipette.engine.config as engConfig
import lsst.pipette.engine.stages.ccd as ccdStage
import lsst.pipette.run.options as runOptions
import lsst.pipette.run.readwrite as runReadWrite

def run(rerun,                          # Rerun name
        visit,                          # Visit number
        snap,                           # Snap number
        raft,                           # Raft id
        sensor,                         # Sensor id
        config,                         # Configuration
        ):
    io = runReadWrite.ReadWrite(lsstSim.LsstSimMapper, ['visit', 'snap', 'raft', 'sensor'],
                                fileKeys=['visit', 'snap', 'raft', 'sensor', 'channel'], config=config)
    roots = config['roots']
    basename = os.path.join(roots['output'], '%s-%d-%d-%s-%s' % (rerun, visit, snap, raft, sensor))
    proc = ccdStage.CcdProcessing(config=config)
    dataId = {'visit': visit, 'snap': snap, 'raft': raft, 'sensor': sensor}

    exposures = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    clipboard = proc.run(exposure=exposures, detrends=detrends)
    io.write(dataId, **clipboard)
    return


if __name__ == "__main__":
    parser = runOptions.OptionParser()
    parser.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="Rerun name (default=%default)")
    parser.add_option("-v", "--visit", dest="visit", help="Visit to run")
    parser.add_option("-S", "--snap", dest="snap", help="Snap to run")
    parser.add_option("-r", "--raft", dest="raft", help="Raft to run")
    parser.add_option("-s", "--sensor", dest="sensor", help="Sensor to run")

    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "lsstSim.paf")
    config, opts, args = parser.parse_args(overrides)
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.visit is None or \
           opts.snap is None or opts.raft is None or opts.sensor is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, int(opts.visit), int(opts.snap), opts.raft, opts.sensor, config)
