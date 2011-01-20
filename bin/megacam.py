#!/usr/bin/env python

import os
import sys

import lsst.obs.cfht as cfht
import lsst.pipette.engine.config as engConfig
import lsst.pipette.engine.stages.ccd as ccdStage
import lsst.pipette.run.options as runOptions
import lsst.pipette.run.readwrite as runReadWrite

def run(rerun,                          # Rerun name
        visit,                          # Visit number
        ccd,                            # CCD number
        config,                         # Configuration
        ):
    io = runReadWrite.ReadWrite(cfht.CfhtMapper, ['visit', 'ccd'], fileKeys=['amp'], config=config)
    roots = config['roots']
    basename = os.path.join(roots['output'], '%s-%d-%d' % (rerun, visit, ccd))
    proc = ccdStage.CcdProcessing(config=config)
    dataId = {'visit': visit, 'ccd': ccd}

    exposures = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    clipboard = proc.run(exposure=exposures, detrends=detrends)
    io.write(dataId, **clipboard)
    return


if __name__ == "__main__":
    parser = runOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="Rerun name (default=%default)")
    parser.add_option("-v", "--visit", dest="visit", help="Visit to run")
    parser.add_option("-c", "--ccd", dest="ccd", help="CCD to run")

    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "megacam.paf")
    config, opts, args = parser.parse_args(overrides)
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or \
           opts.visit is None or opts.ccd is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, int(opts.visit), int(opts.ccd), config)
