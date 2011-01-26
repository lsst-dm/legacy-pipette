#!/usr/bin/env python

import lsst.afw.image as afwImage
import lsst.coadd.utils as coaddUtils

import lsst.pipette.warp as pipWarp


class Stack(pipWarp.Warp):
    def run(self, identMatrix, butler, ra, dec, scale, xSize, ySize):
        """Warp and stack images

        @param[in] identMatrix Matrix of warp identifiers
        @param[in] butler Data butler
        @param[in] ra Right Ascension (radians) of skycell centre
        @param[in] dec Declination (radians) of skycell centre
        @param[in] scale Scale (arcsec/pixel) of skycell
        @param[in] xSize Size in x
        @parma[in] ySize Size in y
        @output Stacked image
        """
        assert identMatrix, "No identMatrix provided"

        skycell = self.skycell(ra, dec, scale, xSize, ySize)

        coadd = afwImage.ExposureF(xSize, ySize)
        coadd.setWcs(skycell.getWcs())
        weight = afwImage.ImageF(xSize, ySize)

        badpix = ~afwImage.MaskU.getPlaneBitMask("DETECTED") # Allow these through
        for identList in identMatrix:
            warp = self.warp(identList, butler, skycell)
            # XXX Save for later
            
            coaddUtils.addToCoadd(coadd.getMaskedImage(), weight, warp.getMaskedImage(), badpix, 1.0)

        coaddUtils.setCoaddEdgeBits(warp.getMaskedImage().getMask(), weight)

        coaddImage = coadd.getMaskedImage()
        coaddImage /= weight

