#!/usr/bin/env python

import lsst.ip.isr as ipIsr
from lsst.pipette.stages.detrend import Detrend


class Dark(Detrend):
    def run(self, exposure=None, detrends=None, **kwargs):
        """Dark subtraction

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        dark = self._checkDimensions(exposure, detrends['dark'])
        expTime = float(exposure.getCalib().getExptime())
        darkTime = float(dark.getCalib().getExptime())
        self.log.log(self.log.INFO, "Removing dark (%f sec vs %f sec)" % (expTime, darkTime))
        ipIsr.darkCorrection(exposure, dark, expTime, darkTime)
        return
