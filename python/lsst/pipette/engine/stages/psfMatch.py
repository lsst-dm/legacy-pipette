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
import lsst.coadd.psfmatched as coaddPsfMatch

class PsfMatchToImage(BaseStage):
    def __init__(self, *args, **kwargs):
        BaseStage.__init__(self,
            requires=["exposure", "referenceExposure"], *args, **kwargs)

        policy = self.config["psfMatchToImagePolicy"].getPolicy()

        self._matcher = coaddPsfMatch.PsfMatchToImage.fromPolicy(policy)

    def run(self, exposure, referenceExposure, **kwargs):
        """PSF-match the exposure to a reference exposure in-place

        @param[in] exposure Exposure to add; must be warped to match referenceExposure
        @param[in] referenceExposure Exposure whose PSF is to be matched
        """
        psfMatchedExposure = self._matcher.matchExposure(exposure, referenceExposure)
        return {"exposure": psfMatchedExposure}
