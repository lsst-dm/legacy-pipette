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

import lsst.pipette.process as pipProc
import lsst.coadd.utils as coaddUtils

class Warp(pipProc.Process):
    def __init__(self, *args, **kwargs):
        super(Warp, self).__init__(*args, **kwargs)
        policy = self.config["warp"].getPolicy()
        self._warper = coaddUtils.Warp.fromPolicy(policy)


    def run(self, exposure, bbox, wcs):
        """Warp an Exposure to a specified size, xy0 and WCS

        @param[in] exposure Exposure to process
        @param[in] bbox bounding box for resulting exposure;
            dimensions = bbox dimensions
            xy0 = bbox minimum position
        @param[in] wcs wcs of resulting exposure
        
        @return Warped exposure
        """
        return self.warp(exposure, bbox, wcs)


    def warp(self, exposure, bbox, wcs):
        """Warp an exposure to a specified skycell

        @param[in] exposure Exposure to process
        @param[in] bbox bounding box for resulting exposure;
            dimensions = bbox dimensions
            xy0 = bbox minimum position
        @param[in] wcs wcs of resulting exposure

        @return Warped exposure
        """
        return self._warper.warpExposure(bbox, wcs, exposure)
