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


class Warp(pipProc.Process):
    def run(self, exposureList, ra, dec, scale, xSize, ySize):
        """Warp an exposure to a specified size, xy0 and WCS

        @param[in] exposureList Exposures to process
        @param[in] ra Right Ascension (radians) of skycell centre
        @param[in] dec Declination (radians) of skycell centre
        @param[in] scale Scale (arcsec/pixel) of skycell
        @param[in] xSize Size in x
        @parma[in] ySize Size in y
        
        @return Warped exposure
        """

        skyWcs = self.skycell(ra, dec, scale, xSize, ySize)

        warp = afwImage.ExposureF(xSize, ySize)
        warp.setWcs(skyWcs)
        weight = afwImage.ImageF(xSize, ySize)
        
        for index, exp in enumerate(exposureList):
            width, height = exp.getWidth(), exp.getHeight()
            expWcs = exp.getWcs()
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
            self.log.log(self.log.INFO, "Bounds of image %d: %d,%d --> %d,%d" %
                         (index, xMin, yMin, xMax, yMax))
            if xMin < xSize and xMax >= 0 and yMin < ySize and yMax >= 0:
                bbox = afwImage.BBox(afwImage.PointI(xMin, yMin), afwImage.PointI(xMax, yMax))
                self.warp(warp, weight, exp, bbox)

        # XXX Check that every pixel in the weight is either 1 or 0

        return warp

    def skycell(self, ra, dec, scale, xSize, ySize):
        """Define a skycell
        
        @param[in] ra Right Ascension (degrees) of skycell centre
        @param[in] dec Declination (degrees) of skycell centre
        @param[in] scale Scale (arcsec/pixel) of skycell
        @param[in] xSize Size in x
        @parma[in] ySize Size in y
        
        @return WCS of skycell
        """
        crval = afwGeom.Point2D.make(ra, dec)
        crpix = afwGeom.Point2D.make(xSize / 2.0, ySize / 2.0)
        wcs = afwImage.createWcs(crval, crpix, scale / 3600.0, 0.0, 0.0, scale / 3600.0)
        return wcs

    def warp(self, warp, weight, exposure, bbox):
        """Warp an exposure to a specified skycell

        @param[out] warp Warped exposure
        @param[out] weight Accumulated weight map
        @param[in] exposure Exposure to process
        @param[in] bbox bounding box for resulting exposure;
            dimensions = bbox dimensions
            xy0 = bbox minimum position
        """

        warpImage = warp.getMaskedImage()
        targetImage = warpImage.Factory(warpImage.getDimensions())
        targetImage.set((0, 0, 0))
        target = afwImage.makeExposure(targetImage, warp.getWcs())
        subTarget = target.Factory(target, bbox)

        policy = self.config["warp"]
        kernel = afwMath.makeWarpingKernel(policy["warpingKernelName"])
        kernel.computeCache(policy["cacheSize"])
        interpLength = policy["interpLength"]

        afwMath.warpExposure(subTarget, exposure, kernel, interpLength)

        subWarp = warp.getMaskedImage().Factory(warp.getMaskedImage(), bbox)
        subWeight = weight.Factory(weight, bbox)

        badpix = ~afwImage.MaskU.getPlaneBitMask("DETECTED") # Allow these through
        coaddUtils.addToCoadd(subWarp, subWeight, subTarget.getMaskedImage(), badpix, 1.0)
