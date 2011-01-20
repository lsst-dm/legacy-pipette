#!/usr/bin/env python

import os
import sys

import lsst.obs.suprime as suprime
import lsst.pipette.engine.config as engConfig
import lsst.pipette.engine.stages.ccd as ccdStage
import lsst.pipette.run.options as runOptions
import lsst.pipette.run.readwrite as runReadWrite
import lsst.pipette.run.catalog as runCatalog

def run(rerun,                          # Rerun name
        frame,                          # Frame number
        ccd,                            # CCD number
        config,                         # Configuration
        ):
    io = runReadWrite.ReadWrite(suprime.SuprimeMapper, ['visit', 'ccd'], config=config)
    roots = config['roots']
    basename = os.path.join(roots['output'], '%s-%d%d' % (rerun, frame, ccd))
    proc = ccdStage.CcdProcessing(config=config)
    #print proc
    dataId = { 'visit': frame, 'ccd': ccd }

    exposures = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    clipboard = proc.run(exposure=exposures, detrends=detrends)
    io.write(dataId, **clipboard)

    catPolicy = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "catalog.paf")
    catalog = runCatalog.Catalog(catPolicy, allowNonfinite=False)
    catalog.writeSources(basename + '.sources', clipboard['sources'], 'sources')
    catalog.writeMatches(basename + '.matches', clipboard['matches'], 'sources')
    return


if __name__ == "__main__":
    parser = runOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frame", dest="frame",
                      help="visit to run (default=%default)")
    parser.add_option("-c", "--ccd", dest="ccd",
                      help="CCD to run (default=%default)")

    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "suprimecam.paf")
    config, opts, args = parser.parse_args(overrides)
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frame is None or opts.ccd is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, int(opts.frame), int(opts.ccd), config)
