#!/usr/bin/env python

import os
import os.path
import optparse
import multiprocessing
import collections

import lsst.pex.logging as pexLog
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.afw.geom as afwGeom
import lsst.obs.hscSim as obsHsc
import lsst.obs.suprimecam as obsSc
import lsst.pipette.runHsc as runHsc
import lsst.pipette.readwrite as pipReadWrite

Arguments = collections.namedtuple('Arguments', ['instrument', 'rerun', 'frame', 'ccd', 'input', 'output'])

def correction(dimensions, wcs):
    image = afwImage.ImageF(dimensions)
    for y in xrange(image.getHeight()):
        for x in xrange(image.getWidth()):
            area = wcs.pixArea(afwGeom.PointD(x, y))
            image.set(x, y, 1.0 / area)
    return image


def getConfigFromArguments():
    parser = optparse.OptionParser()
    parser.add_option("-I", "--instrument", default="suprimecam", dest="instrument",
                      help="Instrument of interest")
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frame", type="int", dest="frame", help="calexp frame with WCS for Jacobian")
    parser.add_option("-i", "--inputs", type="string", dest="inputs", default="FLAT-00000%03d.fits",
                      help="Format for input files")
    parser.add_option("-o", "--outputs", type="string", dest="outputs", default="PHOTFLAT-00000%03d.fits",
                      help="Format for output files")
    parser.add_option("-T", "--threads", type="int", dest="threads", default=1,
                      help="Number of threads to use")

    opts, args = parser.parse_args()
    if (len(args) > 0
        or opts.instrument is None
        or opts.rerun is None
        or opts.frame is None
        or opts.inputs is None
        or opts.outputs is None
        or opts.threads is None):

        parser.print_help()
        print "argv was: %s" % (argv)
        return None, None, None

    return opts.instrument, opts.rerun, opts.frame, opts.inputs, opts.outputs, opts.threads

def run(args):
    camera = args.instrument
    rerun = args.rerun
    frame = args.frame
    ccd = args.ccd
    input = args.input
    output = args.output

    if camera.lower() in ('hsc'):
        Mapper = obsHsc.HscSimMapper
    elif camera.lower() in ("suprimecam", "suprime-cam", "sc",
                            "suprimecam-mit", "sc-mit", "scmit", "suprimecam-old", "sc-old", "scold"):
        Mapper = obsSc.SuprimecamMapper
    else:
        raise RuntimeError("Unrecognised camera: %s" % camera)

    try:                                # LSST exceptions don't pickle
        io = pipReadWrite.ReadWrite(Mapper(rerun=rerun), ['visit', 'ccd'])
        exp = afwImage.ExposureF(input)
        image = exp.getMaskedImage()
        average = afwMath.makeStatistics(image, afwMath.MEANCLIP).getValue()
        md = io.read('calexp_md', {'visit': frame, 'ccd': ccd})[0]
        wcs = afwImage.makeWcs(md)
        image *= correction(image.getDimensions(), wcs)
        image *= average / afwMath.makeStatistics(image, afwMath.MEANCLIP).getValue()
        image.writeFits(output)
    except Exception, e:
        raise RuntimeError("Processing failed: %s" % e)

if __name__ == "__main__":
    camera, rerun, frame, inputs, outputs, threads = getConfigFromArguments()

    if camera.lower() in ('hsc'):
        numCcds = 100
    elif camera.lower() in ("suprimecam", "suprime-cam", "sc",
                            "suprimecam-mit", "sc-mit", "scmit", "suprimecam-old", "sc-old", "scold"):
        numCcds = 10
    else:
        raise RuntimeError("Unrecognised camera: %s" % config['camera'])

    args = [Arguments(camera, rerun, frame, ccd, inputs % ccd, outputs % ccd) for ccd in range(numCcds)]

    if threads > 1:
        pool = multiprocessing.Pool(processes=threads, maxtasksperchild=1)
    else:
        class FakePool(object):
            map = map
            def close(self): pass
            def join(self): pass
        pool = FakePool()

    pool.map(run, args)
    pool.close()
    pool.join()

