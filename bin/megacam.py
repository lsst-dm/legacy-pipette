#!/usr/bin/env python

import os
import sys

import lsst.obs.cfht as cfht
import lsst.pipette.config as pipConfig
import lsst.pipette.processCcd as pipProcCcd
import lsst.pipette.options as pipOptions
import lsst.pipette.catalog as pipCatalog
import lsst.pipette.readwrite as pipReadWrite

def run(rerun,                          # Rerun name
        visit,                          # Visit number
        ccd,                            # CCD number
        config,                         # Configuration
        ):
    io = pipReadWrite.ReadWrite(cfht.CfhtMapper, ['visit', 'ccd'], fileKeys=['amp'], config=config)
    roots = config['roots']
    basename = os.path.join(roots['output'], '%s-%d-%d' % (rerun, visit, ccd))
    ccdProc = pipProcCcd.ProcessCcd(config=config)
    dataId = {'visit': visit, 'ccd': ccd}

    raws = io.readRaw(dataId)
    detrends = io.detrends(dataId, config)
    exposure, psf, apcorr, sources, matches = ccdProc.run(raws, detrends)
    io.write(dataId, exposure=exposure, psf=psf, sources=sources, matches=matches)

    catPolicy = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "catalog.paf")
    catalog = pipCatalog.Catalog(catPolicy, allowNonfinite=False)
    if sources is not None:
        catalog.writeSources(basename + '.sources', sources, 'sources')
    if matches is not None:
        catalog.writeMatches(basename + '.matches', matches, 'sources')
    return


if __name__ == "__main__":
    parser = pipOptions.OptionParser()
    parser.add_option("-r", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="Rerun name (default=%default)")
    parser.add_option("-v", "--visit", dest="visit", help="Visit to run")
    parser.add_option("-c", "--ccd", dest="ccd", help="CCD to run")

    default = os.path.join(os.getenv("PIPETTE_ENGINE_DIR"), "policy", "ProcessCcdDictionary.paf")
    overrides = os.path.join(os.getenv("PIPETTE_RUN_DIR"), "policy", "megacam.paf")
    config, opts, args = parser.parse_args(default, overrides)
    if len(args) > 0 or len(sys.argv) == 1 or opts.rerun is None or \
           opts.visit is None or opts.ccd is None:
        parser.print_help()
        sys.exit(1)

    run(opts.rerun, int(opts.visit), int(opts.ccd), config)
