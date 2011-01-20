#!/usr/bin/env python

import os
import sys

import lsst.obs.lsstSim as lsstSim
import lsst.pipette.engine.config as engConfig
import lsst.pipette.engine.stages.coadd as engCoadd
import lsst.pipette.run.options as runOptions
import lsst.pipette.run.readwrite as runReadWrite

### this may need work; how are calibrated science exposures identified?
def run(rerun,                          # Rerun name
        visit,                          # Visit number
        snap,                           # Snap number
        raft,                           # Raft id
        sensor,                         # Sensor id
        config,                         # Configuration
        ):
    io = runReadWrite.ReadWrite(lsstSim.LsstSimMapper, ["visit", "snap", "raft", "sensor"],
                                fileKeys=["visit", "snap", "raft", "sensor"], config=config)
    roots = config["roots"]
    basename = os.path.join(roots["output"], "%s-%d-%d-%s-%s" % (rerun, visit, snap, raft, sensor))
    proc = engCoadd.Coadd(config=config)
    dataId = {"visit": visit, "snap": snap, "raft": raft, "sensor": sensor}

    exposures = io.read("visitim", dataId)
    referenceExposure = exposures[0]
    
    clipboard = proc.run(
        exposure=exposures,
        referenceExposure = exposure,
        dimensions = referenceExposure.getMaskedImage().getDimensions(),
        xy0 = referenceExposure.getXY0(),
        wcs = referenceExposure.getWcs(),
    )
    coadd = clipboard["coadd"]
    coaddExposure = coadd.getCoadd()
    weightMap = coadd.getWeightMap()
    
### How to output coaddExposure and weightMap properly;
# will either of these work? Meanwhile just hack it with writeFits...
#    io.write(dataId, **clipboard)
#    io.write(dataId, coaddExposure=coaddExposure, weightMap=weightMap)
    coaddExposure.writeFits("coadd.fits")
    weightMap.writeFits("weightMap.fits")


if __name__ == "__main__":
    parser = runOptions.OptionParser()
    parser.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="Rerun name (default=%default)")
    parser.add_option("-v", "--visit", dest="visit", help="Visit to run")
    parser.add_option("-S", "--snap", dest="snap", help="Snap to run")
    parser.add_option("-r", "--raft", dest="raft", help="Raft to run")
    parser.add_option("-s", "--sensor", dest="sensor", help="Sensor to run")

    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "coaddPsfMatchToImage.paf")
    config, opts, args = parser.parse_args(overrides)
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.visit is None or \
           opts.snap is None or opts.raft is None or opts.sensor is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, int(opts.visit), int(opts.snap), opts.raft, opts.sensor, config)
