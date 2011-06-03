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
import lsst.daf.base as dafBase
import lsst.ip.diffim as ipDiffIm
import lsst.pex.logging as pexLog
import lsst.pipette.coaddOptions

FWHMPerSigma = 2 * math.sqrt(2 * math.log(2))

class ExposureMetadata(object):
    """Metadata for an exposure
        
    Attributes:
    - path: path to exposure FITS file
    - wcs: WCS of exposure
    - bbox: parent bounding box of exposure
    - weight = weightFactor / clipped mean variance
    """
    def __init__(self, path, exposure, badPixelMask, weightFactor = 1.0):
        """Create an ExposureMetadata
        
        @param[in] path: path to Exposure FITS file
        @param[in] exposure: Exposure
        @param[in] badPixelMask: bad pixel mask for pixels to ignore
        @param[in] weightFactor: additional scaling factor for weight:
        """
        self.path = path
        self.wcs = exposure.getWcs()
        self.bbox = exposure.getBBox(afwImage.PARENT)
        
        maskedImage = exposure.getMaskedImage()

        statsCtrl = afwMath.StatisticsControl()
        statsCtrl.setNumSigmaClip(3.0)
        statsCtrl.setNumIter(2)
        statsCtrl.setAndMask(badPixelMask)
        statObj = afwMath.makeStatistics(maskedImage.getVariance(), maskedImage.getMask(),
            afwMath.MEANCLIP, statsCtrl)
        meanVar, meanVarErr = statObj.getResult(afwMath.MEANCLIP);
        weight = weightFactor / float(meanVar)
        self.weight = weight

def psfMatchAndWarp(idList, butler, desFwhm, coaddWcs, coaddBBox, policy):
    """Normalize, PSF-match and warp exposures and save the resulting exposures as FITS files
    
    @param[in] idList: a list of IDs of calexp (and associated PSFs) to coadd
    @param[in] butler: data butler for retrieving input calexp and associated PSFs
    @param[in] desFwhm: desired FWHM (pixels)
    @param[in] coaddWcs: desired WCS of coadd
    @param[in] coaddBBox: bounding box for coadd
    @param[in] policy: policy: see policy/outlierRejectedCoaddDictionary.paf
    
    @return exposureMetadataList: a list of ExposureMetadata objects
        describing the saved psf-matched and warped exposures
    """
    psfMatchPolicy = policy.getPolicy("psfMatchPolicy")
    warpPolicy = policy.getPolicy("warpPolicy")
    coaddPolicy = policy.getPolicy("coaddPolicy")
    badPixelMask = coaddUtils.makeBitMask(coaddPolicy.getArray("badMaskPlanes"))
    coaddZeroPoint = coaddPolicy.get("coaddZeroPoint")
    coddFluxMag0 = 10**(0.4 * coaddZeroPoint)
    destCalib = afwImage.Calib()
    destCalib.setFluxMag0(coddFluxMag0)

    if len(idList) > 0:
        exposurePsf = butler.get("psf", idList[0])
        exposurePsfKernel = exposurePsf.getKernel()

        kernelDim = exposurePsfKernel.getDimensions()
        print "Create double Gaussian PSF model with core fwhm %0.1f and size %dx%d" % \
            (desFwhm, kernelDim[0], kernelDim[1])
        coreSigma = desFwhm / FWHMPerSigma
        modelPsf = afwDetection.createPsf("DoubleGaussian", kernelDim[0], kernelDim[1],
            coreSigma, coreSigma * 2.5, 0.1)
    
    psfMatcher = ipDiffIm.ModelPsfMatch(psfMatchPolicy)
    warper = afwMath.Warper.fromPolicy(warpPolicy)
    
    exposureMetadataList = []
    for id in idList:
        outPath = "_".join(["%s_%s" % (k, id[k]) for k in sorted(id.keys())])
        outPath = outPath.replace(",", "_")
        outPath = outPath + ".fits"
        if True:        
            print "Processing id=%s; will save as %s" % (id, outPath)
            exposure = butler.get("calexp", id)
            psf = butler.get("psf", id)
            exposure.setPsf(psf)
    
            srcCalib = exposure.getCalib()
            scaleFac = 1.0 / srcCalib.getFlux(coaddZeroPoint)
            maskedImage = exposure.getMaskedImage()
            maskedImage *= scaleFac
            print "Normalized using scaleFac=%0.3g; now PSF match to model" % (scaleFac,)

            exposure, psfMatchingKernel, kernelCellSet = psfMatcher.matchExposure(exposure, modelPsf)
            
            print "Warp exposure"
            exposure = warper.warpExposure(coaddWcs, exposure, maxBBox = coaddBBox)
            exposure.setCalib(destCalib)

            exposure.writeFits(outPath)
        else:
            # debug mode; exposures already exist
            print "WARNING: DEBUG MODE; Processing id=%s; retrieving from %s" % (id, outPath)
            exposure = afwImage.ExposureF(outPath)

        expMetadata = ExposureMetadata(
                path = outPath,
                exposure = exposure,
                badPixelMask = badPixelMask,
            )
        exposureMetadataList.append(expMetadata)
        
    return exposureMetadataList

def subBBoxIter(bbox, subregionSize):
    """Iterate over subregions of a bbox
    
    @param[in] bbox: bounding box over which to iterate: afwGeom.Box2I
    @param[in] subregionSize: size of sub-bboxes

    @return subBBox: next sub-bounding box of size subregionSize or smaller;
        each subBBox is contained within bbox, so it may be smaller than subregionSize at the edges of bbox,
        but it will never be empty
    """
    if bbox.isEmpty():
        raise RuntimeError("bbox %s is empty" % (bbox,))
    if subregionSize[0] < 1 or subregionSize[1] < 1:
        raise RuntimeError("subregionSize %s must be nonzero" % (subregionSize,))

    for rowShift in range(0, bbox.getHeight(), subregionSize[1]):
        for colShift in range(0, bbox.getWidth(), subregionSize[0]):
            subBBox = afwGeom.Box2I(bbox.getMin() + afwGeom.Extent2I(colShift, rowShift), subregionSize)
            subBBox.clip(bbox)
            if subBBox.isEmpty():
                raise RuntimeError("Bug: empty bbox! bbox=%s, subregionSize=%s, colShift=%s, rowShift=%s" % \
                    (bbox, subregionSize, colShift, rowShift))
            yield subBBox

def outlierRejectedCoadd(idList, butler, desFwhm, coaddWcs, coaddBBox, policy):
    """PSF-match, warp and coadd images, using outlier rejection
    
    PSF matching is to a double gaussian model with core FWHM = desFwhm
    and wings of amplitude 1/10 of core and FWHM = 2.5 * core.
    The size of the PSF matching kernel is the same as the size of the kernel
    found in the first calibrated science exposure, since there is no benefit
    to making it any other size.
    
    PSF-matching is performed before warping so the code can use the PSF models
    associated with the calibrated science exposures (without having to warp those models).
    
    @todo Figure out where subregionSize comes from: I suspect we need a new
      outlier-rejection coadd dictionary, but where to put it?
      For now just use a hard-coded value.

    @param[in] idList: list of data identity dictionaries
    @param[in] butler: data butler for input images
    @param[in] desFwhm: desired PSF of coadd, but in science exposure pixels
                (the coadd usually has a different scale!)
    @param[in] coaddWcs: WCS for coadd
    @param[in] coaddBBox: bounding box for coadd
    @param[in] policy: see policy/outlierRejectedCoaddDictionary.paf
    @output:
    - coaddExposure: coadd exposure
    - weightMap: a float Image of the same dimensions as the coadd; the value of each pixel
        is the sum of the weights of all the images that contributed to that pixel.
    """
    exposureMetadataList = psfMatchAndWarp(
        idList = idList,
        butler = butler,
        desFwhm = desFwhm,
        coaddWcs = coaddWcs,
        coaddBBox = coaddBBox,
        policy = policy,
    )
    
    edgeMask = afwImage.MaskU.getPlaneBitMask("EDGE")
    
    coaddPolicy = policy.getPolicy("coaddPolicy")
    badPixelMask = coaddUtils.makeBitMask(coaddPolicy.getArray("badMaskPlanes"))

    statsCtrl = afwMath.StatisticsControl()
    statsCtrl.setNumSigmaClip(3.0)
    statsCtrl.setNumIter(2)
    statsCtrl.setAndMask(badPixelMask)

    coaddExposure = afwImage.ExposureF(coaddBBox, coaddWcs)
    coaddMaskedImage = coaddExposure.getMaskedImage()
    subregionSizeArr = policy.getArray("subregionSize")
    subregionSize = afwGeom.Extent2I(subregionSizeArr[0], subregionSizeArr[1])
    dumPS = dafBase.PropertySet()
    for bbox in subBBoxIter(coaddBBox, subregionSize):
        print "Computing coadd %s" % (bbox,)
        coaddView = afwImage.MaskedImageF(coaddMaskedImage, bbox, afwImage.PARENT, False)
        maskedImageList = afwImage.vectorMaskedImageF() # [] is rejected by afwMath.statisticsStack
        weightList = []
        for expMeta in exposureMetadataList:
            if expMeta.bbox.contains(bbox):
                maskedImage = afwImage.MaskedImageF(expMeta.path, 0, dumPS, bbox, afwImage.PARENT)
            elif not bbox.overlaps(expMeta.bbox):
                print "Skipping %s; no overlap" % (expMeta.path, bbox)
            else:
                overlapBBox = afwGeom.Box2I(expMeta.bbox)
                overlapBBox.clip(bbox)
                print "Processing %s; grow from %s to %s" % (expMeta.path, overlapBBox, bbox)
                maskedImage = afwImage.MaskedImageF(bbox)
                maskedImage.getMask().set(edgeMask)
                maskedImageView = afwImage.MaskedImageF(maskedImage, overlapBBox, afwImage.PARENT, False)
                maskedImageView <<= afwImage.MaskedImageF(expMeta.path, 0,dumPS, overlapBBox, afwImage.PARENT)
            maskedImageList.append(maskedImage)
            weightList.append(expMeta.weight)
        try:
            coaddSubregion = afwMath.statisticsStack(
                maskedImageList, afwMath.MEANCLIP, statsCtrl, weightList)

            coaddView <<= coaddSubregion
        except Exception, e:
            print "Outlier rejection failed; setting EDGE mask: %s" % (e,)
            raise
            # setCoaddEdgeBits does this later, so no need to do it here

    coaddUtils.setCoaddEdgeBits(coaddMaskedImage.getMask(), coaddMaskedImage.getVariance())

    return coaddExposure

if __name__ == "__main__":
    pexLog.Trace.setVerbosity('lsst.coadd', 5)
    pexLog.Trace.setVerbosity('lsst.ip.diffim', 1)

    parser = lsst.pipette.coaddOptions.CoaddOptionParser()
    parser.add_option("--fwhm", dest="fwhm", type="float", help="Desired FWHM, in science exposure pixels")
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "outlierRejectedCoaddDictionary.paf")
    config, opts, args = parser.parse_args(policyPath, requiredArgs=["fwhm"])
    
    coaddExposure = outlierRejectedCoadd(
        idList = parser.getIdList(),
        butler = parser.getReadWrite().inButler,
        desFwhm = opts.fwhm,
        coaddWcs = parser.getCoaddWcs(),
        coaddBBox = parser.getCoaddBBox(),
        policy = config.getPolicy())

    coaddBasePath = parser.getCoaddBasePath()
    coaddExposure.writeFits(coaddBasePath + "_outlierRejectedCoadd.fits")
