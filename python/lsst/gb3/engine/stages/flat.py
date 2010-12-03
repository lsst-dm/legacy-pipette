#!/usr/bin/env python

#import lsst.ip.isr as ipIsr
from lsst.pipette.engine.stages.detrend import Detrend

class Flat(Detrend):
    def run(self, exposure=None, detrends=None, **kwargs):
        """Flat-fielding

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        flat = self._checkDimensions(exposure, detrends['flat'])
        mi = exposure.getMaskedImage()
        image = mi.getImage()
        variance = mi.getVariance()
        flatImage = flat.getMaskedImage().getImage()
        self.log.log(self.log.INFO, "Flattening image")
        # XXX This looks awful because AFW doesn't define useful functions.  Need to fix this.
        image /= flatImage
        variance /= flatImage
        variance /= flatImage
        ### This API is bad --- you NEVER want to rescale your flat on the fly.
        ### Scale it properly when you make it and never rescale again.
        #ipIsr.flatCorrection(exposure, flat, "USER", 1.0)
        return
