#!/usr/bin/env python

import os
import sys
import multiprocessing
import collections

import lsst.pex.logging as pexLog
import lsst.pipette.runHsc as runHsc
import lsst.pipette.options as pipOptions

Inputs = collections.namedtuple('Inputs', ['rerun', 'frame', 'ccd', 'config', 'log'])

def run(inputs):
    rerun = inputs.rerun
    frame = inputs.frame
    ccd = inputs.ccd
    config = inputs.config
    log = inputs.log

    pexLog.Log.getDefaultLog().addDestination(log)
    log = pexLog.Log.getDefaultLog()

    runHsc.doRun(rerun, frame, ccd, instrument=config['camera'], log=log)


def getConfigFromArguments(argv=None):
    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "ProcessCcdDictionary.paf")
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", dest="frames", help="visits to run, colon-delimited")
    parser.add_option("-T", "--threads", type="int", dest="threads", help="Number of threads")

    config, opts, args = parser.parse_args([default], argv=argv)
    if (len(args) > 0 # or opts.instrument is None
        or opts.rerun is None
        or opts.frames is None
        or opts.threads is None):

        parser.print_help()
        print "argv was: %s" % (argv)
        return None, None, None

    return config, opts, args

def main(argv=None):
    config, opts, args = getConfigFromArguments(argv)
    if not config:
        raise SystemExit("argument parsing error")

    camera = config['camera']
    if camera.lower() in ('hsc'):
        numCcds = 100
    elif camera.lower() in ("suprimecam", "suprime-cam", "sc",
                            "suprimecam-mit", "sc-mit", "scmit", "suprimecam-old", "sc-old", "scold"):
        numCcds = 10
    else:
        raise RuntimeError("Unrecognised camera: %s" % config['camera'])

    frames = map(int, opts.frames.split(":"))

    inputs = list()
    for frame in frames:
        for ccd in range(numCcds):
            inputs.append(Inputs(rerun=opts.rerun, frame=frame, ccd=ccd, config=config,
                                 log="%s.%d.%d.log" % (opts.rerun, frame, ccd)))

    pool = multiprocessing.Pool(processes=opts.threads, maxtasksperchild=1)
    pool.map(run, inputs)
    pool.close()
    pool.join()
    

if __name__ == "__main__":
    main()
