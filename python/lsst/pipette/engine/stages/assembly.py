#!/usr/bin/env python

import lsst.pipette.engine.util as engUtil
from lsst.pipette.engine.stage import BaseStage

class Assembly(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Assembly, self).__init__(requires='exposure', provides='exposure', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Assembly of amplifiers into a CCD

        @param exposure List of exposures to be assembled
        """
        if not hasattr(exposure, "__iter__"):
            # This is not a list; presumably it's a single item needing no assembly
            return
        if len(exposure) == 1:
            # Special case
            return {'exposure': exposure[0]}
        
        egExp = exposure[0]             # The (assumed) model for exposures
        egMi = egExp.getMaskedImage()   # The (assumed) model for masked images
        Exposure = type(egExp)
        MaskedImage = type(egMi)
        ccd = engUtil.getCcd(egExp)
        miCcd = MaskedImage(ccd.getAllPixels(True).getDimensions())
        for exp in exposure:
            amp = getAmp(exp)
            mi = exp.getMaskedImage()
            miAmp = MaskedImage(miCcd, amp.getDataSec(True))
            miAmp <<= mi
        exp = afwImage.makeExposure(miCcd, egExp.getWcs())
        exp.setWcs(egExp.getWcs())
        exp.setMetadata(egExp.getMetadata())
        exp.setFilter(egExp.getFilter())
        exp.setDetector(ccd)
        exp.getCalib().setExptime(egExp.getCalib().getExptime())
        exp.getCalib().setMidTime(egExp.getCalib().getMidTime())
        return {'exposure': exp}
