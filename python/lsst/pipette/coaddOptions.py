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

import lsst.afw.coord as afwCoord
import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.skymap as skymap
import idListOptions

_RadPerDeg = math.pi / 180.0

class CoaddOptionParser(idListOptions.IdListOptionParser):
    """OptionParser is an lsst.pipette.idListOptions.IdListOptionParser specialized for coaddition.
    
    @todo:
    - Add support for more cameras
    - Correct default scale for suprimecam
    - Change to using skymap sky tiles
    """
    _DefaultScale = dict(
        lsstSim = 0.14,
        suprimecam = 0.14,
    )
    _DefaultOverlap = dict(
        lsstSim = 3.5,
        suprimecam = 1.5,
    )
    def __init__(self, usage="usage: %prog dataSource [options]", **kwargs):
        """Construct an option parser
        """
        idListOptions.IdListOptionParser.__init__(self, usage=usage, **kwargs)
        self._dataSource = None

        self.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                        help="rerun name (default=%default)")
        self.add_option("--radec", dest="radec", type="float", nargs=2,
help="RA, Dec to find tileid; center of coadd unless llc specified (ICRS, degrees, space-separated)")
        self.add_option("--tileid", dest="tileid", type="int",
                        help="sky tile ID; if omitted the best sky tile for radec is used")
        self.add_option("--llc", dest="llc", nargs=2, type="int",
help="x, y index of lower left corner (pixels, space-separated); if omitted, coadd is centered on radec")
        self.add_option("--size", dest="size", nargs=2, type="int",
                        help="x y size of coadd (pixels, space-separated)")
        self.add_option("--projection", dest="projection", default="STG",
                        help="WCS projection used for sky tiles, e.g. STG or TAN")
        
    def _handleDataSource(self):
        """Set attributes based on self._dataSource
        
        Called by parse_args before the main parser is called
        """
        idListOptions.IdListOptionParser._handleDataSource(self)
        defaultScale = self._DefaultScale[self._dataSource]
        defaultOverlap = self._DefaultOverlap[self._dataSource]
        self.add_option("--scale", dest="scaleAS", type="float",
                        default = defaultScale,
                        help="Pixel scale for skycell, in arcsec/pixel")
        self.add_option("--overlap", dest="overlapDeg", type="float",
                        default = defaultOverlap,
                        help="Overlap between adjacent sky tiles, in deg")

    def parse_args(self, policyPath, requiredArgs=()):
        """Parse the arguments
        
        @param[in] policyPath: path to main policy dictionary
        @param[in] requiredArgs: list of required arguments, in addition to the standard ones
        
        @return
        - config: a Configuration object
        - opts: command-line options, as from optparse
        - args: command-line arguments, as from optparse
        
        Must be called before calling getReadWrite, getWcs, getWcsBBox, getIdList
        """
        config, opts, args = idListOptions.IdListOptionParser.parse_args(self,
            policyPath = policyPath,
            requiredArgs = ("size",) + tuple(requiredArgs)
        )
        
        pixelScale = opts.scaleAS * _RadPerDeg / 3600.0
        
        self._skyMap = skymap.SkyMap(
            projection = opts.projection,
            pixelScale = pixelScale,
            overlap = opts.overlapDeg * _RadPerDeg,
        )

        raDec = getattr(opts, "radec", None)
        if raDec != None:
            ctrCoord = afwCoord.IcrsCoord(afwGeom.Point2D(opts.radec[0], opts.radec[1]), afwCoord.DEGREES)

        dimensions = afwGeom.Extent2I(opts.size[0], opts.size[1])
        
        tileId = opts.tileid
        if tileId == None:
            if opts.radec == None:
                raise RuntimeError("Must specify tileid or radec")
            tileId = self._skyMap.getSkyTileId(ctrCoord)

        self._skyTileInfo = self._skyMap.getSkyTileInfo(tileId)

        self._coaddWcs = self._skyTileInfo.getWcs()
        
        # determine bounding box
        if opts.llc != None:
            llcPixInd = afwGeom.Point2I(opts.llc[0], opts.llc[1])
        else:
            if opts.radec == None:
                raise RuntimeError("Must specify llc or radec")
            ctrPixPos = self._coaddWcs.skyToPixel(ctrCoord)
            ctrPixInd = afwGeom.Point2I(ctrPixPos)
            llcPixInd = ctrPixInd - (dimensions / 2)
        self._coaddBBox = afwGeom.Box2I(llcPixInd, dimensions)
        
        roots = config["roots"]
        self._coaddBasePath = os.path.join(roots["output"], opts.rerun)
        
        return config, opts, args
    
    def getCoaddBasePath(self):
        """Return the coadd base path. You must call parse_args first.
        """
        return self._coaddBasePath
        
    def getCoaddWcs(self):
        """Return WCS for coadd. You must call parse_args first.
        """
        return self._coaddWcs
    
    def getCoaddBBox(self):
        """Return coadd bounding box (as an afwGeom.Box2I). You must call parse_args first.
        """
        return self._coaddBBox
