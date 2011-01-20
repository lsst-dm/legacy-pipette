#!/usr/bin/env python

import os
import sys

#import lsst.pex.logging as pexLog
import lsst.pex.policy as pexPolicy
import lsst.daf.persistence as dafPersist
import lsst.obs.suprime as suprime
import lsst.pipette.engine.config as pipConfig
import lsst.pipette.engine.master as pipMaster
import lsst.pipette.run.options as runOptions
import lsst.pipette.run.readwrite as runReadWrite
import lsst.pipette.run.catalog as runCatalog

def run(rerun,                          # Rerun name
        frames,                         # Frame number
        ccds,                           # CCD number
        config,                         # Configuration
        ):
#    log = pexLog.getDefaultLog()
#    log.setThreshold(log.DEBUG)

    roots = config['roots']
    io = runReadWrite.ReadWrite(suprime.SuprimeMapper, ['visit', 'ccd'], config=config)
    detProc = pipMaster.Master(config=config)
    identMatrix = list()
    for ccd in ccds:
        identList = list()
        for frame in frames:
            dataId = { 'visit': frame, 'ccd': ccd }
            identList.append(dataId)
        identMatrix.append(identList)

    masterList = detProc.run(identMatrix, io.inButler, io.outButler)

    for master, ccd in zip(masterList, ccds):
        name = "%s-%d.fits" % (rerun, ccd)
        master.writeFits(name)
        print "Wrote %s" % name

    return


if __name__ == "__main__":
    parser = runOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", dest="frames",
                      help="visits to run, colon-delimited")
    parser.add_option("-c", "--ccds", dest="ccds",
                      help="CCDs to run, colon-delimited")

    default = os.path.join(os.getenv("PIPETTE_ENGINE_DIR"), "policy", "MasterProcessDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "suprimecam_detrend.paf")
    config, opts, args = parser.parse_args(default, overrides)
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frames is None or opts.ccds is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, map(int, opts.frames.split(":")), map(int, opts.ccds.split(":")), config)
