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
            requires=["exposure", "bbox", "wcs"],
            provides=["coadd", "coaddWeight"],
        *args, **kwargs)

        self._policy = self.config["coaddPolicy"].getPolicy()

        self._coadd = None

    def run(self, exposure, bbox, wcs, **kwargs):
        """Add the exposure to a Coadd
        
        The coadd is created on the first call and accumulated indefinitely.
        Create a new object to start a new coadd.
        
        @param[in] exposure Exposure to add; must be background-subtracted, warped to match the coadd
            and otherwise preprocessed (e.g. psf-matched to a reference)
        @param[in] bbox bounding box for coadd (only used the first time);
            coadd dimensions = bbox dimensions
            coadd xy0 = bbox minimum position
        @param[in] wcs wcs of coadd (only used the first time)
          
        @return {
        "coadd:", coadd
        }
        where:
        - coadd is the lsst.coadd.utils.Coadd object to which the exposure was added
        - coaddWeight is the weight with which this exposure
        was added to the coadd; it is 1/clipped mean variance of the exposure
        """
        if not self._coadd:
            self._coadd = coaddUtils.Coadd(
                bbox = bbox,
                wcs = wcs,
                allowedMaskPlanes = self.policy.getPolicy("coaddPolicy").get("allowedMaskPlanes"))

        weight = self._coadd.addExposure(exposure)

        return {
            "coadd": self._coadd,
            "coaddWeight": weight,
        }

class Coadd(IterateMultiStage):
    """Coadd stage
    
    For each exposure: warp, psf match to image and add to coadd.

    Unanswered questions:
    - how to tie the stages together; in particular
      - how to get dimensions, xy0 and wcs and referenceExposure into the first stage
        (get them from the first exposure, which is the reference exposure)
      - how to process a list of exposures, especially without having them
        all in memory at the same time
      - how to output the coadd at the very end
    """
    def __init__(self, name="coadd", factory=None, *args, **kwargs):
        factory = StageFactory(factory,
            warp=warp.Warp,
            psfMatchToImage=psfMatch.PsfMatchToImage,
            addToCoadd=AddToCoadd)
        stages = factory.create(["warp",
                                 "psfMatchToImage",
                                 "addToCoadd"], *args, **kwargs)
        super(Coadd, self).__init__(name, stages, iterate=['exposure'], *args, **kwargs)
