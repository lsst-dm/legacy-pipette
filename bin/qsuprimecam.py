#!/usr/bin/env python

import sys
import os

import lsst.obs.suprime as suprime
import lsst.pipette.engine.config as engConfig
import lsst.pipette.engine.stages.ccd as ccdStage
import lsst.pipette.engine.queue as engQueue
import lsst.pipette.run.options as runOptions
import lsst.pipette.run.readwrite as runReadWrite
import lsst.pipette.run.catalog as runCatalog

def run(rerun,                          # Rerun name
        frameList,                      # Frame numbers
        ccdList,                        # CCD numbers
        config,                         # Configuration
        command=None,                   # Command for PBS
        queue=None,                     # Queue name
        submit=False,                   # Submit to queue?
        ):
    imports = [ ("lsst.obs.suprime", "suprime"),
                ("lsst.pipette.run.readwrite", "runReadWrite"),
                ("lsst.pipette.engine.stages.ccd", "ccdStage"),
                ("lsst.pex.logging", "pexLog"),
                ]
    script = """
    log = pexLog.Log.getDefaultLog()
    log.addDestination(basename + '.log')
    io = runReadWrite.ReadWrite(suprime.SuprimeMapper, ['visit', 'ccd'], config=config)
    exposures = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    proc = ccdStage.CcdProcessing(config=config)
    clipboard = proc.run(exposure=exposures, detrends=detrends)
    io.write(dataId, **clipboard)
    if clipboard.has_key('sources'):
        catalog.writeSources(basename + '.sources', clipboard['sources'], 'sources')
    if clipboard.has_key('matches'):
        catalog.writeMatches(basename + '.matches', clipboard['matches'], 'sources')
    """

    roots = config['roots']
    catPolicy = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "catalog.paf")
    catalog = runCatalog.Catalog(catPolicy, allowNonfinite=False)

    queue = engQueue.PbsQueue(script, command=command, importList=imports, resourceList="walltime=300")
    roots = config['roots']
    for frame in frameList:
        for ccd in ccdList:
            basename = os.path.join(roots['output'], '%s-%d%d' % (rerun, frame, ccd))
            dataId = {'visit': frame, 'ccd': ccd}

            if submit:
                queue.sub(basename,
                          basename=basename,
                          config=config,
                          dataId=dataId,
                          catalog=catalog,
                          )
            else:
                print "Not queuing %s: dataId=%s" % (basename, dataId)
                
    return


if __name__ == "__main__":
    parser = runOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-f", "--frames", default=None, dest="frames",
                      help="colon separated frames to run (default=%default)")
    parser.add_option("-c", "--ccds", default="0:1:2:3:4:5:6:7:8:9", dest="ccds",
                      help="colon separated CCDs to run (default=%default)")
    parser.add_option("-q", "--queue", default=None, dest="queue",
                      help="queue name to which to submit (default=%default)")
    parser.add_option("-C", "--command", default=None, dest="command",
                      help="command to queue script (e.g., 'qsub -V'")
    parser.add_option("-s", "--submit", action="store_true", default=False, dest="submit",
                      help="submit to queue? (default=%default)")

    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "suprimecam.paf")
    config, opts, args = parser.parse_args(overrides)
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.frames is None or opts.ccds is None:
        parser.print_help()
        sys.exit(1)

    if opts.debug:
        print "Debugging is not recommended for queue submission."
        sys.exit(1)

    run(opts.rerun, map(int, opts.frames.split(":")), map(int, opts.ccds.split(":")), config,
        command=opts.command, queue=opts.queue, submit=opts.submit)
