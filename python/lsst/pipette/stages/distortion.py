#!/usr/bin/env python

import lsst.pipette.util as pipUtil
import lsst.pipette.distortion as pipDist
from lsst.pipette.stage import BaseStage

class Distortion(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Distortion, self).__init__(requires=['exposure'], provides='distortion', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Generate appropriate optical distortion

        @param exposure Exposure from which to get CCD
        """
        assert exposure, "No exposure provided"
        ccd = pipUtil.getCcd(exposure)
        dist = pipDist.createDistortion(ccd, self.config['distortion'])
        return {'distortion': dist}
