#!/usr/bin/env python

import os
import sys

import lsst.obs.hscSim as hsc
import lsst.pipette.config as pipConfig
import lsst.pipette.stack as pipStack
import lsst.pipette.options as pipOptions
import lsst.pipette.readwrite as pipReadWrite

def run(rerun,                          # Rerun name
        frames,                          # Frame number
        ccds,                           # CCD number
        stack,                          # Stack identifier
        patch,                          # Patch identifier
        filter,                         # Filter name
        config,                         # Configuration
        coords,                         # Skycell centre coordinates
        scale,                          # Pixel scale
        sizes,                          # Skycell size
        ignore=False,                   # Ignore missing files?
        ):
    io = pipReadWrite.ReadWrite(hsc.HscSimMapper(rerun=rerun), ['visit', 'ccd'], config=config)
    roots = config['roots']
    basename = os.path.join(roots['output'], rerun)
    stackProc = pipStack.Stack(config=config)

    identMatrix = list()
    for frame in frames:
        identList = list()
        for ccd in ccds:
            dataId = { 'visit': frame, 'ccd': ccd }
            identList.append(dataId)
        identMatrix.append(identList)

    exp = stackProc.run(identMatrix, io.inButler,
                        coords[0], coords[1], scale, sizes[0], sizes[1], ignore=ignore)

    #stack.writeFits(basename + ".fits")
    stackProc.write(io.outButler, {'stack': stack, 'patch': patch, 'filter': filter}, {"stack": exp})



if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", dest="frames",
                      help="visit to run, colon-delimited")
    parser.add_option("-c", "--ccds", dest="ccds", default="0:1:2:3:4:5:6:7:8:9:10:11:12:13:14:15:16:17:18:19:20:21:22:23:24:25:26:27:28:29:30:31:32:33:34:35:36:37:38:39:40:41:42:43:44:45:46:47:48:49:50:51:52:53:54:55:56:57:58:59:60:61:62:63:64:65:66:67:68:69:70:71:72:73:74:75:76:77:78:79:80:81:82:83:84:85:86:87:88:89:90:91:92:93:94:95:96:97:98:99",
                      help="CCD to run (default=%default)")
    parser.add_option("-s", "--stack", dest="stack", type="int",
                      help="Stack identifier")
    parser.add_option("-p", "--patch", dest="patch", type="int",
                      help="Patch identifier")
    parser.add_option("--filter", dest="filter", type="string",
                      help="Stack identifier")
    parser.add_option("--coords", dest="coords", type="float", nargs=2,
                      help="Coordinates for skycell, degrees")
    parser.add_option("--scale", dest="scale", type="float",
                      help="Pixel scale for skycell, arcsec/pixel")
    parser.add_option("--sizes", dest="sizes", nargs=2, type="int",
                      help="Sizes in x and y for skycell, pixels")
    parser.add_option("--ignore", dest="ignore", default=False, action="store_true",
                      help="Ignore missing files?")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "WarpProcessDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam_warp.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frames is None or opts.ccds is None \
       or opts.stack is None or opts.patch is None \
       or opts.coords is None or opts.scale is None or opts.sizes is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, map(int, opts.frames.split(":")), map(int, opts.ccds.split(":")), opts.stack, opts.patch,
        opts.filter, config, opts.coords, opts.scale, opts.sizes, ignore=opts.ignore)
