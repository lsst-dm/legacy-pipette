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
import warp
import psfMatch

class AddToCoadd(BaseStage):
    def __init__(self, *args, **kwargs):
        BaseStage.__init__(self,
            requires=["exposure"], *args, **kwargs)

        policy = self.config["coadd"].getPolicy()

        self._coadd = coaddUtils.Coadd.fromPolicy(policy)

    def run(self, exposure, dimensions, xy0, wcs, **kwargs):
        """Add the exposure to a Coadd

        @param[in] exposure Exposure to add; must be background-subtracted,
            warped to match the coadd and otherwise preprocessed (e.g. psf-matched to a reference)
            
        @return {"coaddWeight": coaddWeight} where coaddWeight is the weight with which this exposure
            was added to the coadd; it is 1/clipped mean variance of the exposure
        """
        weightFactor = self._coadd.addExposure(exposure)
        return {"coaddWeight": coaddWeight}

class CoaddStageFactory(StageFactory):
    """StageFactory for the coadd stage
    """
    stages = StageFactory.stages.copy()
    stages["warp"] = warp.Warp
    stages["psfMatchToImage"] = psfMatch.PsfMatchToImage
    stages["addToCoadd"] = AddToCoadd
    stages = StageDict(stages)

class Coadd(MultiStage):
    """Coadd stage
    """
    def __init__(self, name="coadd", factory=CoaddStageFactory, *args, **kwargs):
        stages = [factory.create([name], *args, **kwargs)
            for name in ("warp", "psfMatchToImage", "addToCoadd")]
        MultiStage.__init__(self, name, stages, *args, **kwargs)
