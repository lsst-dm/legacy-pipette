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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import lsst.afw.coord as afwCoord
import lsst.afw.math as afwMath
import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.coadd.utils as coaddUtils
import lsst.pipette.process as pipProc

class Skycell(object):
    def __init__(self, wcs, width, height):
        self._wcs = wcs
        self._width = width
        self._height = height

    def getWcs(self):
        return self._wcs

    def getDimensions(self):
        return self._width, self._height


class Warp(pipProc.Process):
    def run(self, identList, butler, ra, dec, scale, xSize, ySize):
        """Warp an exposure to a specified size, xy0 and WCS

        @param[in] identList Identifiers of CCDs to warp
        @param[in] butler Data butler
        @param[in] ra Right Ascension (radians) of skycell centre
        @param[in] dec Declination (radians) of skycell centre
        @param[in] scale Scale (arcsec/pixel) of skycell
        @param[in] xSize Size in x
        @parma[in] ySize Size in y
        
        @return Warped exposure
        """

        skycell = self.skycell(ra, dec, scale, xSize, ySize)
        return self.warp(identList, butler, skycell)

    def skycell(self, ra, dec, scale, xSize, ySize):
        """Define a skycell
        
        @param[in] ra Right Ascension (degrees) of skycell centre
        @param[in] dec Declination (degrees) of skycell centre
        @param[in] scale Scale (arcsec/pixel) of skycell
        @param[in] xSize Size in x
        @parma[in] ySize Size in y
        
        @return Skycell
        """
        crval = afwGeom.Point2D.make(ra, dec)
        crpix = afwGeom.Point2D.make(xSize / 2.0, ySize / 2.0)
        wcs = afwImage.createWcs(crval, crpix, scale / 3600.0, 0.0, 0.0, scale / 3600.0)
        return Skycell(wcs, xSize, ySize)

    def warp(self, identList, butler, skycell, ignore=False):
        """Warp an exposure to a nominated skycell

        @param[in] identList List of data identifiers
        @param[in] butler Data butler
        @param[in] skycell Skycell specification
        @param[in] ignore Ignore missing files?
        @return Warped exposure
        """

        skyWcs = skycell.getWcs()
        xSize, ySize = skycell.getDimensions()
        warp = afwImage.ExposureF(skycell.getDimensions(), skyWcs)
        weight = afwImage.ImageF(skycell.getDimensions())
        
        for ident in identList:
            md = self.read(butler, ident, ["calexp_md"], ignore=ignore)
            if md is None or len(md) == 0:
                self.log.log(self.log.WARN, "Unable to read %s --- ignoring" % ident)
                continue
            md = md[0]
            width, height = md.get("NAXIS1"), md.get("NAXIS2")
            expWcs = afwImage.makeWcs(md)

            xSkycell = list()
            ySkycell = list()
            for x, y in ((0.0, 0.0), (0.0, height), (width, 0.0), (width, height)):
                sky = expWcs.pixelToSky(x, y)
                position = skyWcs.skyToPixel(sky)
                xSkycell.append(position.getX())
                ySkycell.append(position.getY())

            xMin = max(0, int(min(xSkycell)))
            xMax = min(xSize - 1, int(max(xSkycell) + 0.5))
            yMin = max(0, int(min(ySkycell)))
            yMax = min(ySize - 1, int(max(ySkycell) + 0.5))
            self.log.log(self.log.INFO, "Bounds of image: %d,%d --> %d,%d" % (xMin, yMin, xMax, yMax))
            if xMin < xSize and xMax >= 0 and yMin < ySize and yMax >= 0:
                bbox = afwGeom.Box2I(afwGeom.Point2I(xMin, yMin), afwGeom.Point2I(xMax, yMax))
                exp = self.read(butler, ident, ["calexp"])[0]
                self.warpComponent(warp, weight, exp, bbox)
                del exp
            del md

        # XXX Check that every pixel in the weight is either 1 or 0

        coaddUtils.setCoaddEdgeBits(warp.getMaskedImage().getMask(), weight)

        return warp
 

    def warpComponent(self, warp, weight, exposure, bbox):
        """Warp a component to a specified skycell

        @param[out] warp Warped exposure
        @param[out] weight Accumulated weight map
        @param[in] exposure Exposure component to process
        @param[in] bbox Bounding box for component on warp, in local coords
        """
        target = warp.Factory(warp.getDimensions(), warp.getWcs())
        subTarget = target.Factory(target, bbox, afwImage.LOCAL)

        policy = self.config["warp"]
        kernel = afwMath.makeWarpingKernel(policy["warpingKernelName"])
        kernel.computeCache(policy["cacheSize"])
        interpLength = policy["interpLength"]

        afwMath.warpExposure(subTarget, exposure, kernel, interpLength)

        subWarp = warp.getMaskedImage().Factory(warp.getMaskedImage(), bbox, afwImage.LOCAL)
        subWeight = weight.Factory(weight, bbox, afwImage.LOCAL)

        badpix = afwImage.MaskU.getPlaneBitMask("EDGE") # Allow everything else through
        coaddUtils.addToCoadd(subWarp, subWeight, subTarget.getMaskedImage(), badpix, 1.0)
