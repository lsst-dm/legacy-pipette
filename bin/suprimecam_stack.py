#!/usr/bin/env python

import os
import sys

import lsst.obs.suprimecam as suprimecam
import lsst.pipette.config as pipConfig
import lsst.pipette.stack as pipStack
import lsst.pipette.options as pipOptions
import lsst.pipette.readwrite as pipReadWrite

def run(rerun,                          # Rerun name
        frames,                          # Frame number
        ccds,                           # CCD number
        filter,                         # Filter name
        patch,                          # Sky patch identifier
        config,                         # Configuration
        coords,                         # Skycell centre coordinates
        scale,                          # Pixel scale
        sizes,                          # Skycell size
        ):
    io = pipReadWrite.ReadWrite(suprimecam.SuprimecamMapper(rerun=rerun), ['visit', 'ccd'], config=config)
    stackProc = pipStack.Stack(config=config)

    identMatrix = list()
    for frame in frames:
        identList = list()
        for ccd in ccds:
            dataId = { 'visit': frame, 'ccd': ccd }
            identList.append(dataId)
        identMatrix.append(identList)

    stack = stackProc.run(identMatrix, io.inButler, coords[0], coords[1], scale, sizes[0], sizes[1])

    #stack.writeFits(basename + ".fits")
    stackProc.write(io.outButler, {'stack': rerun, 'patch': patch, 'filter': filter}, {"stack": stack})




if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", dest="frames",
                      help="visit to run, colon-delimited")
    parser.add_option("-c", "--ccds", dest="ccds", default="0:1:2:3:4:5:6:7:8:9",
                      help="CCD to run (default=%default)")
    parser.add_option("-p", "--patch", dest="patch", type="int",
                      help="Sky patch identifier")
    parser.add_option("--coords", dest="coords", type="float", nargs=2,
                      help="Coordinates for skycell, degrees")
    parser.add_option("--scale", dest="scale", type="float",
                      help="Pixel scale for skycell, arcsec/pixel")
    parser.add_option("--sizes", dest="sizes", nargs=2, type="int",
                      help="Sizes in x and y for skycell, pixels")
    parser.add_option("-F", "--filter", dest="filter", type="string",
                      help="Filter name")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "WarpProcessDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam_warp.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frames is None or \
       opts.ccds is None or opts.patch is None or opts.coords is None or opts.scale is None or \
       opts.sizes is None or opts.filter is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, map(int, opts.frames.split(":")), map(int, opts.ccds.split(":")), opts.filter,
        opts.patch, config, opts.coords, opts.scale, opts.sizes)
