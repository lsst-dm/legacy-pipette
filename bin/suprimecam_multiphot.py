#!/usr/bin/env python

import os
import sys

import lsst.obs.suprimecam as suprimecam
import lsst.pipette.config as pipConfig
import lsst.pipette.multiphot as pipMultiPhot
import lsst.pipette.options as pipOptions
import lsst.pipette.readwrite as pipReadWrite
import lsst.pipette.catalog as pipCatalog

def run(rerun,                          # Rerun name
        reference,                      # Reference stack name
        measureList,                    # List of stack names to measure
        skytile,                        # Sky tile number
        config,                         # Configuration
        ):
    io = pipReadWrite.ReadWrite(suprimecam.SuprimecamMapper, ['visit', 'ccd'], config=config)
    roots = config['roots']
    basename = os.path.join(roots['output'], rerun)

    photProc = pipMultiPhot.MultiPhot(config=config)

    #import lsst.pex.logging as pexLog
    #pexLog.Log.getDefaultLog().setThreshold(pexLog.Log.DEBUG)

    refId = {'stack': reference, 'skytile': skytile, 'filter': "r"}
    refStack = photProc.read(io.inButler, refId, ['stack'])[0]
    measStackList = list()
    for name in measureList:
        dataId = {'stack': name, 'skytile': skytile, 'filter': "r"}
        measStack = refStack if dataId == refId else photProc.read(io.inButler, dataId, ['stack'])[0]
        measStackList.append(measStack)

    sourceList = photProc.run(refStack, measStackList)

    catPolicy = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "catalog.paf")
    catalog = pipCatalog.Catalog(catPolicy, allowNonfinite=False)
    for name, sources in zip(measureList, sourceList):
        catalog.writeSources(basename + '-' + name + '.sources', sources, 'sources')



if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    parser.add_option("-r", "--reference", dest="reference",
                      help="Reference stack name")
    parser.add_option("-m", "--measure", dest="measure", default=[], action="append",
                      help="Stack name to measure")
    parser.add_option("-s", "--skytile", dest="skytile", type="int",
                      help="Skytile identifier")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "MultiPhotProcessDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "suprimecam_multiphot.paf")
    config, opts, args = parser.parse_args([default, overrides])
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or opts.reference is None or \
           opts.measure is None or opts.skytile is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, opts.reference, opts.measure, opts.skytile, config)
