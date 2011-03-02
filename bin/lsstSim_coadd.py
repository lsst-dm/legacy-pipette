#!/usr/bin/env python

import os
import sys

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.coadd.utils as coaddUtils
import lsst.pipette.coaddOptions

def coadd(idList, butler, coaddWcs, coaddBBox, policy):
    """Warp and stack images

    @param idList: list of image identity dictionaries
    @param butler: data butler for input images
    @param coaddWcs: WCS for coadd
    @param coaddBBox: bounding box for coadd
    @param policy: a Policy object that must contain these policies:
        warpPolicy: see coadd_utils/policy/WarpDictionary.paf
        coaddPolicy: see coadd_utils/policy/CoaddDictionary.paf
    @output Stacked image
    """
    warpPolicy = policy.getPolicy("warpPolicy")
    coaddPolicy = policy.getPolicy("coaddPolicy")
    
    warper = coaddUtils.Warp.fromPolicy(warpPolicy)
    coadd = coaddUtils.Coadd.fromPolicy(coaddBBox, coaddWcs, coaddPolicy)
    for ident in idList:
        print "Processing", ident
        exposure = butler.get("calexp", ident)
        warpedExposure = warper.warpExposure(coaddWcs, exposure, maxBBox = coaddBBox)
        coadd.addExposure(exposure)

    coaddExposure = coadd.getCoadd()
    weightMap = coadd.getWeightMap()

    return coaddExposure, weightMap

if __name__ == "__main__":
    parser = lsst.pipette.coaddOptions.CoaddOptionParser("lsstSim")
    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "lsstSim_coadd.paf")
    config, opts, args = parser.parse_args(default)
    
    coaddExposure, weightMap = coadd(
        idList = parser.getIdList(),
        butler = parser.getReadWrite().inButler,
        coaddWcs = parser.getCoaddWcs(),
        coaddBBox = parser.getCoaddBBox(),
        policy = config.getPolicy())

    baseName = parser.getCoaddBaseName()
    coaddExposure.writeFits(baseName + "Coadd.fits")
    weightMap.writeFits(baseName + "WeightMap.fits")
