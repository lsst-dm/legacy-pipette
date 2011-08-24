#!/usr/bin/env python

import os
import sys

import lsst.afw.detection as afwDet
import lsst.obs.suprimecam as suprimecam
import lsst.pipette.config as pipConfig
import lsst.pipette.warp as pipWarp
import lsst.pipette.options as pipOptions
import lsst.pipette.diff as pipDiff
import lsst.pipette.readwrite as pipReadWrite

def run(rerun,                          # Rerun name
        frame1,                         # Frame number for input
        frame2,                         # Frame number for template
        diff,                           # Difference identifier for output
        patch,                          # Sky patch identifier
        config,                         # Configuration
        ):
    io = pipReadWrite.ReadWrite(suprimecam.SuprimecamMapper(rerun=rerun), ['visit'], config=config)
    diffProc = pipDiff.Diff(config=config)

    exp1 = io.inButler.get('warp', {'visit': frame1, 'patch': patch})
    exp2 = io.inButler.get('warp', {'visit': frame2, 'patch': patch})

    diffExp, sources, psf, apcorr, brightSources = diffProc.run(exp1, exp2)

    sources = afwDet.PersistableSourceVector(sources)

    diffProc.write(io.outButler, {'diff': diff, 'patch': patch, 'filter': diffExp.getFilter().getName()},
                   {"diff": diffExp, "diffpsf": psf, "diffsources": sources})

if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", dest="frames", type="int", nargs=2, help="visits (2) to run")
    parser.add_option("-d", "--diff", dest="diff", type="int", help="Difference identifier")
    parser.add_option("-p", "--patch", dest="patch", type="int", help="Difference identifier")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "DiffProcessDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam_diff.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or \
           opts.frames is None or opts.patch is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, opts.frames[0], opts.frames[1], opts.diff, opts.patch, config)
