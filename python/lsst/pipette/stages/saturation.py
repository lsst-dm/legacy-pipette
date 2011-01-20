#!/usr/bin/env python

import lsst.ip.isr as ipIsr
import lsst.pipette.util as pipUtil
from lsst.pipette.stage import BaseStage

class Saturation(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Saturation, self).__init__(requires='exposure', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Mask saturated pixels

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        ccd = pipUtil.getCcd(exposure)
        mi = exposure.getMaskedImage()
        Exposure = type(exposure)
        MaskedImage = type(mi)
        for amp in ccd:
            if not pipUtil.haveAmp(exposure, amp):
                continue
            saturation = amp.getElectronicParams().getSaturationLevel()
            miAmp = MaskedImage(mi, amp.getDiskDataSec())
            expAmp = Exposure(miAmp)
            bboxes = ipIsr.saturationDetection(expAmp, saturation, doMask = True)
            self.log.log(self.log.INFO, "Masked %d saturated pixels on amp %s: %f" %
                         (len(bboxes), amp.getId(), saturation))
        return
