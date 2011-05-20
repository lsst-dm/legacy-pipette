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
import idListOptions
import readwrite

class CoaddOptionParser(idListOptions.IdListOptionParser):
    """OptionParser is an lsst.pipette.idListOptions.IdListOptionParser specialized for coaddition.
    
    @todo:
    - Add support for more cameras
    - Correct default scale for suprimecam
    - Change to using skymap sky tiles
    """
    def __init__(self, usage="usage: %prog dataSource [options]", **kwargs):
        """Construct an option parser
        """
        idListOptions.IdListOptionParser.__init__(self, usage=usage, **kwargs)
        self._dataSource = None

        self.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                          help="rerun name (default=%default)")
        self.add_option("--radec", dest="radec", type="float", nargs=2,
                          help="RA Dec of center of coadd (degrees, space-separated)")
        self.add_option("--size", dest="size", nargs=2, type="int",
                        help="x y size for coadd (pixels, space-separated)")
        
    def _handleDataSource(self):
        """Set attributes based on self._dataSource
        
        Called by parse_args before the main parser is called
        """
        idListOptions.IdListOptionParser._handleDataSource(self)
        defaultScale = dict(
            lsstSim = 0.14,
            suprimecam = 0.14,
        )[self._dataSource]
        self.add_option("--scale", dest="scale", type="float",
                        default = defaultScale,
                        help="Pixel scale for skycell, arcsec/pixel")

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
            requiredArgs = ("rerun", "radec", "scale", "size") + tuple(requiredArgs)
        )
    
        crval = afwGeom.Point2D(opts.radec[0], opts.radec[1])
        crpix = afwGeom.Point2D(opts.size[0] / 2.0, opts.size[1] / 2.0)
        self._coaddWcs = afwImage.createWcs(crval, crpix, opts.scale / 3600.0, 0.0, 0.0, opts.scale / 3600.0)
        self._coaddBBox = afwGeom.Box2I(afwGeom.Point2I(0,0), afwGeom.Extent2I(opts.size[0], opts.size[1]))
        
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
