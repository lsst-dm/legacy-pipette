#!/usr/bin/env python
#
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#
import os
import sys

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.coadd.chisquared as coaddChiSq
import lsst.pipette.coaddOptions

def chiSquaredCoadd(idList, butler, coaddWcs, coaddBBox, policy):
    """Warp and coadd images

    @param[in] idList: list of data identity dictionaries
    @param[in] butler: data butler for input images
    @param[in] coaddWcs: WCS for coadd
    @param[in] coaddBBox: bounding box for coadd
    @param[in] policy: a Policy object that must contain these policies:
        warpPolicy: see afw/policy/WarpDictionary.paf
        coaddPolicy: see coadd_utils/policy/CoaddDictionary.paf
    @output:
    - coaddExposure: coadd exposure
    - weightMap: a float Image of the same dimensions as the coadd; the value of each pixel
        is the sum of the weights of all the images that contributed to that pixel.
    """
    warpPolicy = policy.getPolicy("warpPolicy")
    coaddPolicy = policy.getPolicy("coaddPolicy")
    
    warper = afwMath.Warper.fromPolicy(warpPolicy)
    coadd = coaddChiSq.Coadd.fromPolicy(coaddBBox, coaddWcs, coaddPolicy)
    for id in idList:
        print "Processing id=%s" % (id,)
        exposure = butler.get("calexp", id)
        psf = butler.get("psf", id)
        exposure.setPsf(psf)
        print "Warp exposure"
        exposure = warper.warpExposure(coaddWcs, exposure, maxBBox = coaddBBox)
        coadd.addExposure(exposure)

    coaddExposure = coadd.getCoadd()
    weightMap = coadd.getWeightMap()

    return coaddExposure, weightMap

if __name__ == "__main__":
    parser = lsst.pipette.coaddOptions.CoaddOptionParser()
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "chiSquaredCoaddDictionary.paf")
    config, opts, args = parser.parse_args(policyPath)
    
    coaddExposure, weightMap = chiSquaredCoadd(
        idList = parser.getIdList(),
        butler = parser.getReadWrite().inButler,
        coaddWcs = parser.getCoaddWcs(),
        coaddBBox = parser.getCoaddBBox(),
        policy = config.getPolicy())

    coaddBasePath = parser.getCoaddBasePath()
    coaddExposure.writeFits(coaddBasePath + "_chiSquaredCoadd.fits")
    weightMap.writeFits(coaddBasePath + "_chiSquaredCoadd_weight.fits")
