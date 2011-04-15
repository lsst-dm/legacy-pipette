#!/usr/bin/env python
import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.coadd.utils as coaddUtils

import lsst.pipette.process as pipProcess
import lsst.pipette.warp as pipWarp


class Stack(pipProcess.Process):
    def __init__(self, Warp=pipWarp.Warp, **kwargs):
        super(Stack, self).__init__(**kwargs)
        self._warp = Warp(**kwargs)

    
    def run(self, identMatrix, butler, ra, dec, scale, xSize, ySize, ignore=False):
        """Warp and stack images

        @param[in] identMatrix Matrix of warp identifiers
        @param[in] butler Data butler
        @param[in] ra Right Ascension (radians) of skycell centre
        @param[in] dec Declination (radians) of skycell centre
        @param[in] scale Scale (arcsec/pixel) of skycell
        @param[in] xSize Size in x
        @param[in] ySize Size in y
        @param[in] ignore Ignore missing files?
        @output Stacked exposure
        """
        assert identMatrix, "No identMatrix provided"

        skycell = self.skycell(ra, dec, scale, xSize, ySize)

        coaddDim = afwGeom.Extent2I(xSize, ySize)
        coadd = afwImage.ExposureF(coaddDim, skycell.getWcs())
        weight = afwImage.ImageF(coaddDim)

        badpix = afwImage.MaskU.getPlaneBitMask("EDGE") # Allow everything else through
        for identList in identMatrix:
            warp = self.warp(identList, butler, skycell, ignore=ignore)
            # XXX Save for later?
            
            coaddUtils.addToCoadd(coadd.getMaskedImage(), weight, warp.getMaskedImage(), badpix, 1.0)

        coaddUtils.setCoaddEdgeBits(coadd.getMaskedImage().getMask(), weight)

        coaddImage = coadd.getMaskedImage()
        coaddImage /= weight

        # XXX Coadd has NANs where weight=0

        return coadd

    def skycell(self, ra, dec, scale, xSize, ySize):
        """Define a skycell
        
        @param[in] ra Right Ascension (degrees) of skycell centre
        @param[in] dec Declination (degrees) of skycell centre
        @param[in] scale Scale (arcsec/pixel) of skycell
        @param[in] xSize Size in x
        @parma[in] ySize Size in y
        
        @return Skycell
        """
        return self._warp.skycell(ra, dec, scale, xSize, ySize)

    def warp(self, identList, butler, skycell, ignore=False):
        """Warp an exposure to a nominated skycell

        @param[in] identList List of data identifiers
        @param[in] butler Data butler
        @param[in] skycell Skycell specification
        @return Warped exposure
        """
        return self._warp.warp(identList, butler, skycell, ignore=ignore)
