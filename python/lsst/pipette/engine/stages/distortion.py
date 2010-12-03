#!/usr/bin/env python

import lsst.pipette.engine.util as engUtil
import lsst.pipette.engine.distortion as engDist
from lsst.pipette.engine.stage import BaseStage

class Distortion(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Distortion, self).__init__(requires=['exposure'], provides='distortion', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Generate appropriate optical distortion

        @param exposure Exposure from which to get CCD
        """
        assert exposure, "No exposure provided"
        ccd = engUtil.getCcd(exposure)
        dist = engDist.createDistortion(ccd, self.config['distortion'])
        return {'distortion': dist}
