#!/usr/bin/env python

import lsst.afw.math as afwMath
#import lsst.ip.isr as ipIsr
import lsst.pipette.util as pipUtil
from lsst.pipette.stage import BaseStage

class Overscan(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Overscan, self).__init__(requires='exposure', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Overscan subtraction

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        ccd = pipUtil.getCcd(exposure)
        mi = exposure.getMaskedImage()
        MaskedImage = type(mi)
        for amp in ccd:
            if not pipUtil.haveAmp(exposure, amp):
                continue
            biassec = amp.getDiskBiasSec()

            # XXX lsst.ip.isr.overscanCorrection doesn't allow for the exposure to contain multiple amps, so
            # we'll do this ourselves
            #ipIsr.overscanCorrection(exposure, biassec, "MEDIAN")

            datasec = amp.getDiskDataSec()
            overscan = MaskedImage(mi, biassec)
            image = MaskedImage(mi, datasec)
            offset = afwMath.makeStatistics(overscan, afwMath.MEDIAN).getValue(afwMath.MEDIAN)
            self.log.log(self.log.INFO, "Overscan correction on amp %s, %s: %f" %
                         (amp.getId(), biassec, offset))
            image -= offset
        return
