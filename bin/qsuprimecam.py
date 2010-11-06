#/usr/bin/env python

import sys
import os

import lsst.obs.suprime as suprime
import lsst.gb3.config as gb3Config
import lsst.gb3.options as gb3Options
import lsst.gb3.crank as gb3Crank
import lsst.gb3.queue as gb3Queue

def run(rerun,                          # Rerun name
        frameList,                      # Frame numbers
        ccdList,                        # CCD numbers
        config,                         # Configuration
        queue=None,                     # Queue name
        ):
    imports = [ ( "lsst.obs.suprime", "suprime"),
                ( "lsst.gb3.crank", "gb3Crank" ),
                ]
    script = "gb3Crank.Crank(basename, suprime.SuprimeMapper, config=config).turn(dataId)"

    queue = gb3Queue.Queue(script, importList=imports, resourceList="walltime=300")
    roots = config['roots']
    for frame in frameList:
        for ccd in ccdList:
            basename = os.path.join(roots['output'], '%s-%d%d' % (rerun, frame, ccd))
            queue.sub(basename, basename=basename, config=config, dataId={ 'visit': frame, 'ccd': ccd })
    return


if __name__ == "__main__":
    parser = gb3Options.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", default=None, dest="frames",
                      help="colon separated frames to run (default=%default)")
    parser.add_option("-c", "--ccds", default="0:1:2:3:4:5:6:7:8:9", dest="ccds",
                      help="colon separated CCDs to run (default=%default)")
    parser.add_option("-q", "--queue", default=None, dest="queue",
                      help="queue name to which to submit (default=%default)")
    parser.add_option("-s", "--submit", action="store_true", default=False, dest="submit",
                      help="submit to queue? (default=%default)")

    config, opts, args = gb3Config.configuration(parser, "policy/suprimecam.paf")
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frames is None or opts.ccds is None:
        parser.print_help()
        sys.exit(1)

    if opts.debug:
        print "Debugging is not recommended for queue submission."
        sys.exit(1)

    run(opts.rerun, map(int, opts.frames.split(":")), map(int, opts.ccds.split(":")), config, queue=opts.queue)
