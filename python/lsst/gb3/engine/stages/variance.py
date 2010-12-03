#!/usr/bin/env python

import lsst.gb3.engine.util as engUtil
from lsst.gb3.engine.stage import BaseStage

class Variance(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Variance, self).__init__(requires='exposure', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Set variance from gain

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        mi = exposure.getMaskedImage()
        if engUtil.detectorIsCcd(exposure):
            ccd = engUtil.getCcd(exposure)
            MaskedImage = type(mi)
            for amp in ccd:
                miAmp = MaskedImage(mi, amp.getDataSec(True))
                self._varianceAmp(miAmp, amp)
        else:
            amp = cameraGeom.cast_Amp(exposure.getDetector())
            self._varianceAmp(mi, amp)
        return

    def _varianceAmp(self, mi, amp):
        """Set variance from gain for an amplifier

        @param mi Masked image for amplifier
        @param amp Amplifier of interest
        """
        gain = amp.getElectronicParams().getGain()
        self.log.log(self.log.INFO, "Setting variance for amp %s: %f" % (amp.getId(), gain))
        variance = mi.getVariance()
        variance <<= mi.getImage()
        variance /= gain
        return
