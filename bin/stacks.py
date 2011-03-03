#!/usr/bin/env python

import os
import sys
import optparse

import lsst.obs.hscSim as hsc
import lsst.pipette.config as pipConfig
import lsst.pipette.stack as pipStack
import lsst.pipette.readwrite as pipReadWrite
import lsst.skypix as skypix

def run(rerun,                          # Rerun name
        stack,                          # Stack identifier
        filter,                         # Filter name
        scale,                          # Scale, arcsec/pix
        ):
    io = pipReadWrite.ReadWrite(hsc.HscSimMapper(rerun=rerun), ['visit', 'ccd'])

    skyPolicy = io.inButler.get('skypolicy')
    print skyPolicy.toString()
    sky = skypix.QuadSpherePixelization(skyPolicy.get('resolutionPix'), skyPolicy.get('paddingArcsec') / 3600.0)

    skytiles = io.inButler.queryMetadata('calexp', None, 'skyTile', {'filter': filter})
    for tile in skytiles:
        visits = io.inButler.queryMetadata('calexp', None, 'visit', {'skyTile': tile, 'filter': filter})
        if len(visits) == 0:
            continue

        geom = sky.getGeometry(tile)
        bbox = geom.getBoundingBox()
        ra, dec = bbox.getCenter()      # Degrees
        theta = bbox.getThetaExtent()   # Width, degrees
        size = int(theta * 3600.0 / scale)   # Size, pixels
        
        cmd  = "hsc_stack.py --rerun " + rerun
        cmd += " --stack %d" % stack
        cmd += " --patch %d" % tile
        cmd += " --filter %s" % filter
        cmd += " --coords %f %f" % (ra, dec)
        cmd += " --scale %f" % scale
        cmd += " --sizes %d %d" % (size, size)
        cmd += " --frames %s" % ":".join(map(str, visits))
        print cmd



if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-s", "--stack", dest="stack", type="int",
                      help="Stack identifier")
    parser.add_option("-f", "--filter", dest="filter", type="string",
                      help="Filter name")
    parser.add_option("--scale", dest="scale", type="float", help="Scale, arcsec/pix")

    opts, args = parser.parse_args()
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.stack is None \
           or opts.filter is None or opts.scale is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, opts.stack, opts.filter, opts.scale)
