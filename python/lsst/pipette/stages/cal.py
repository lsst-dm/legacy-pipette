#!/usr/bin/env python

import lsst.meas.photocal as photocal
from lsst.pipette.stage import BaseStage

class Cal(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Cal, self).__init__(requires=['exposure', 'matches'], *args, **kwargs)
        return

    def run(self, exposure=None, matches=None, **kwargs):
        """Photometry calibration

        @param exposure Exposure to process
        @param matches Matched sources
        """
        assert exposure, "No exposure provided"
        assert matches, "No matches provided"
        
        zp = photocal.calcPhotoCal(matches, log=self.log, goodFlagValue=0)
        self.log.log(self.log.INFO, "Photometric zero-point: %f" % zp.getMag(1.0))
        exposure.getCalib().setFluxMag0(zp.getFlux(0))
        return
