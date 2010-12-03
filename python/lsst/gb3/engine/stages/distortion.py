#!/usr/bin/env python

import lsst.gb3.engine.util as engUtil
import lsst.gb3.engine.distortion as engDist
from lsst.gb3.engine.stage import BaseStage

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
