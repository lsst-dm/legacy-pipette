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
from lsst.pipette.engine.stage import BaseStage
import lsst.coadd.utils as coaddUtils

class Warp(BaseStage):
    def __init__(self, *args, **kwargs):
        BaseStage.__init__(self,
            requires=['exposure', 'dimensions', 'xy0', 'wcs'], *args, **kwargs)

        policy = self.config['warp'].getPolicy()

        self._warper = coaddUtils.Warp.fromPolicy(policy)

    def run(self, exposure, **kwargs):
        """Warp an Exposure to a specified size, xy0 and WCS

        @param[in] exposure Exposure to process
        @param[in] dimensions dimensions of resulting exposure
        @param[in] xy0 xy0 of resulting exposure
        @param[in] wcs wcs of resulting exposure
        
        @return {"exposure": warpedExposure}
        """
        warpedExposure = self._warper.warpExposure(dimensions, xy0, wcs, exposure)
        return {"exposure": warpedExposure}
