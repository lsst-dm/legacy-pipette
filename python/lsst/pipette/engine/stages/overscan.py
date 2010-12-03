#!/usr/bin/env python

import lsst.ip.isr as ipIsr
import lsst.pipette.engine.util as engUtil
from lsst.pipette.engine.stage import BaseStage

class Overscan(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Overscan, self).__init__(requires='exposure', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Overscan subtraction

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        fittype = "MEDIAN"                # XXX policy argument
        ccd = engUtil.getCcd(exposure)
        for amp in ccd:
            if not engUtil.haveAmp(exposure, amp):
                continue
            biassec = amp.getDiskBiasSec()
            self.log.log(self.log.INFO, "Doing overscan correction on amp %s: %s" % (amp.getId(), biassec))
            ipIsr.overscanCorrection(exposure, biassec, fittype)
        return
