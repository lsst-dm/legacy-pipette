#!/usr/bin/env python

import os
import sys

#import lsst.pex.logging as pexLog
import lsst.pex.policy as pexPolicy
import lsst.daf.persistence as dafPersist
import lsst.obs.suprimecam as suprimecam
import lsst.pipette.config as pipConfig
import lsst.pipette.master as pipMaster
import lsst.pipette.options as pipOptions
import lsst.pipette.readwrite as pipReadWrite
import lsst.pipette.catalog as pipCatalog

def run(rerun,                          # Rerun name
        frames,                         # Frame number
        ccds,                           # CCD number
        config,                         # Configuration
        ):
#    log = pexLog.getDefaultLog()
#    log.setThreshold(log.DEBUG)

    mapper = suprimecam.SuprimecamMapper(rerun=rerun)
    io = pipReadWrite.ReadWrite(mapper, ['visit', 'ccd'], config=config)
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
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", dest="frames",
                      help="visits to run, colon-delimited")
    parser.add_option("-c", "--ccds", dest="ccds",
                      help="CCDs to run, colon-delimited")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "MasterProcessDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam_detrend.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frames is None or opts.ccds is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, map(int, opts.frames.split(":")), map(int, opts.ccds.split(":")), config)
