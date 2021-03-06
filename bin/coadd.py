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

import lsst.afw.detection as afwDetection
import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.coadd.utils as coaddUtils
import lsst.ip.diffim as ipDiffIm
import lsst.pex.logging as pexLog
import lsst.pipette.coaddOptions

FWHMPerSigma = 2 * math.sqrt(2 * math.log(2))

def coadd(idList, butler, desFwhm, coaddWcs, coaddBBox, policy):
    """PSF-match (if desFwhm is specified), warp and coadd images
    
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
                (the coadd usually has a different scale!);
                if 0 then no PSF matching is performed.
    @param[in] coaddWcs: WCS for coadd
    @param[in] coaddBBox: bounding box for coadd
    @param[in] policy: a Policy object that must contain these policies:
        psfMatchPolicy: see ip_diffim/policy/PsfMatchingDictionary.paf (may omit if desFwhm <= 0)
        warpPolicy: see afw/policy/WarpDictionary.paf
        coaddPolicy: see coadd_utils/policy/CoaddDictionary.paf
    @output:
    - coaddExposure: coadd exposure
    - weightMap: a float Image of the same dimensions as the coadd; the value of each pixel
        is the sum of the weights of all the images that contributed to that pixel.
    """
    numExp = len(idList)
    if numExp < 1:
        print "Warning: no exposures to coadd!"
        sys.exit(1)
    print "Coadd %s calexp" % (numExp,)

    warpPolicy = policy.getPolicy("warpPolicy")
    coaddPolicy = policy.getPolicy("coaddPolicy")

    if desFwhm > 0:
        psfMatchPolicy = policy.getPolicy("psfMatchPolicy")
        psfMatchPolicy = ipDiffIm.modifyForModelPsfMatch(psfMatchPolicy)
        psfMatcher = ipDiffIm.ModelPsfMatch(psfMatchPolicy)
    else:
        print "No PSF matching will be done (desFwhm <= 0)"

    warper = afwMath.Warper.fromPolicy(warpPolicy)
    coadd = coaddUtils.Coadd.fromPolicy(coaddBBox, coaddWcs, coaddPolicy)
    prevKernelDim = afwGeom.Extent2I(0, 0) # use this because the test Extent2I == None is an error
    for ind, id in enumerate(idList):
        print "Processing exposure %d of %d: id=%s" % (ind+1, numExp, id)
        exposure = butler.get("calexp", id)
        psf = butler.get("psf", id)
        exposure.setPsf(psf)
        if desFwhm > 0:
            psfKernel = psf.getKernel()
            kernelDim = psfKernel.getDimensions()
            if kernelDim != prevKernelDim:
                print "Create double Gaussian PSF model with core fwhm %0.1f and size %dx%d" % \
                    (desFwhm, kernelDim[0], kernelDim[1])
                coreSigma = desFwhm / FWHMPerSigma
                modelPsf = afwDetection.createPsf("DoubleGaussian", kernelDim[0], kernelDim[1],
                    coreSigma, coreSigma * 2.5, 0.1)
                prevKernelDim = kernelDim

            print "PSF-match exposure"
            exposure, psfMatchingKernel, kernelCellSet = psfMatcher.matchExposure(exposure, modelPsf)
        print "Warp exposure"
        exposure = warper.warpExposure(coaddWcs, exposure, maxBBox = coaddBBox)
        coadd.addExposure(exposure)

    coaddExposure = coadd.getCoadd()
    weightMap = coadd.getWeightMap()

    return coaddExposure, weightMap

if __name__ == "__main__":
    algName = "coadd"
    pexLog.Trace.setVerbosity('lsst.coadd', 3)
    pexLog.Trace.setVerbosity('lsst.ip.diffim', 1)

    parser = lsst.pipette.coaddOptions.CoaddOptionParser()
    parser.add_option("--fwhm", dest="fwhm", type="float", default=0.0,
        help="Desired FWHM, in science exposure pixels; for no PSF matching omit or set to 0")
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "%sDictionary.paf" % (algName,))
    config, opts, args = parser.parse_args(policyPath, requiredArgs=["fwhm"])
    
    desFwhm = opts.fwhm
    coaddExposure, weightMap = coadd(
        idList = parser.getIdList(),
        butler = parser.getReadWrite().inButler,
        desFwhm = desFwhm,
        coaddWcs = parser.getCoaddWcs(),
        coaddBBox = parser.getCoaddBBox(),
        policy = config.getPolicy())
    
    filterName = coaddExposure.getFilter().getName()
    if filterName == "_unknown_":
        filterStr = "unk"
    coaddBasePath = parser.getCoaddBasePath()
    coaddBaseName = "%s_%s_filter_%s_fwhm_%s" % (coaddBasePath, algName, filterName, desFwhm)
    coaddPath = coaddBaseName + ".fits"
    weightPath = coaddBaseName + "weight.fits"
    print "Saving coadd as %s" % (coaddPath,)
    coaddExposure.writeFits(coaddPath)
    print "saving weight map as %s" % (weightPath,)
    weightMap.writeFits(weightPath)
