#!/usr/bin/env python

import lsst.ip.isr as ipIsr
from lsst.pipette.engine.stages.detrend import Detrend

class Bias(Detrend):
    def run(self, exposure=None, detrends=None, **kwargs):
        """Bias subtraction

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        bias = self._checkDimensions(exposure, detrends['bias'])
        self.log.log(self.log.INFO, "Debiasing image")
        ipIsr.biasCorrection(exposure, bias)
        return
