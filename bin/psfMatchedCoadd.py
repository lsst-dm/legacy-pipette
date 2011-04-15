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
import math
import os
import sys

import lsst.afw.geom as afwGeom
import lsst.afw.detection as afwDetection
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.coadd.utils as coaddUtils
import lsst.coadd.psfmatched as coaddPsfMatched
import lsst.pex.logging as pexLog
import lsst.pipette.coaddOptions

FWHMPerSigma = 2 * math.sqrt(2 * math.log(2))

def psfMatchedCoadd(idList, butler, desFwhm, coaddWcs, coaddBBox, policy):
    """PSF-match, warp and coadd images
    
    PSF matching is to a double gaussian model with core FWHM = desFwhm
    and wings of amplitude 1/10 of core and FWHM = 2.5 * core.
    The size of the PSF matching kernel is the same as the size of the kernel
    found in the first calibrated science exposure, since there is no benefit
    to making it any other size.
    
    PSF-matching is performed before warping so the code can use the PSF models
    associated with the calibrated science exposures (without having to warp those models).

    @param[in] idList: list of data identity dictionaries
    @param[in] butler: data butler for input images
    @param[in] desFwhm: desired PSF of coadd, but in science exposure pixels
                (the coadd usually has a different scale!)
    @param[in] coaddWcs: WCS for coadd
    @param[in] coaddBBox: bounding box for coadd
    @param[in] policy: a Policy object that must contain these policies:
        psfMatchPolicy: see ip_diffim/policy/PsfMatchingDictionary.paf
        warpPolicy: see afw/policy/WarpDictionary.paf
        coaddPolicy: see coadd_utils/policy/CoaddDictionary.paf
    @output:
    - coaddExposure: coadd exposure
    - weightMap: a float Image of the same dimensions as the coadd; the value of each pixel
        is the sum of the weights of all the images that contributed to that pixel.
    """
    psfMatchPolicy = policy.getPolicy("psfMatchPolicy")
    warpPolicy = policy.getPolicy("warpPolicy")
    coaddPolicy = policy.getPolicy("coaddPolicy")

    if len(idList) > 0:
        exposurePsf = butler.get("psf", idList[0])
        exposurePsfKernel = exposurePsf.getKernel()

        kernelWidth = exposurePsfKernel.getWidth()
        kernelHeight = exposurePsfKernel.getHeight()
        print "Create double Gaussian PSF model with core fwhm %0.1f and size %dx%d" % \
            (desFwhm, kernelWidth, kernelHeight)
        coreSigma = desFwhm / FWHMPerSigma
        modelPsf = afwDetection.createPsf("DoubleGaussian", kernelWidth, kernelHeight,
            coreSigma, coreSigma * 2.5, 0.1)
    
    psfMatcher = coaddPsfMatched.PsfMatchToModel(psfMatchPolicy)
    warper = afwMath.Warper.fromPolicy(warpPolicy)
    coadd = coaddUtils.Coadd.fromPolicy(coaddBBox, coaddWcs, coaddPolicy)
    for id in idList:
        print "Processing id=%s" % (id,)
        exposure = butler.get("calexp", id)
        psf = butler.get("psf", id)
        exposure.setPsf(psf)
        exposure, psfMatchingKernel = psfMatcher.matchExposure(exposure, modelPsf)
        exposure = warper.warpExposure(coaddWcs, exposure, maxBBox = coaddBBox)
        coadd.addExposure(exposure)

    coaddExposure = coadd.getCoadd()
    weightMap = coadd.getWeightMap()

    return coaddExposure, weightMap

if __name__ == "__main__":
    pexLog.Trace.setVerbosity('lsst.coadd', 5)
    pexLog.Trace.setVerbosity('lsst.ip.diffim', 1)

    parser = lsst.pipette.coaddOptions.CoaddOptionParser()
    parser.add_option("--fwhm", dest="fwhm", type="float", help="Desired FWHM, in science exposure pixels")
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "psfMatchedCoaddDictionary.paf")
    config, opts, args = parser.parse_args(policyPath, requiredArgs=["fwhm"])
    
    coaddExposure, weightMap = psfMatchedCoadd(
        idList = parser.getIdList(),
        butler = parser.getReadWrite().inButler,
        desFwhm = opts.fwhm,
        coaddWcs = parser.getCoaddWcs(),
        coaddBBox = parser.getCoaddBBox(),
        policy = config.getPolicy())

    coaddBasePath = parser.getCoaddBasePath()
    coaddExposure.writeFits(coaddBasePath + "psfMatchedCoadd.fits")
    weightMap.writeFits(coaddBasePath + "psfMatchedWeightMap.fits")
