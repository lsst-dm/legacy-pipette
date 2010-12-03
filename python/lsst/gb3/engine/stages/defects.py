#!/usr/bin/env python

import lsst.ip.isr as ipIsr
import lsst.meas.algorithms as measAlg
import lsst.pipette.engine.util as engUtil
from lsst.pipette.engine.stage import BaseStage

class Defects(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Defects, self).__init__(requires='exposure', provides='defects', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Mask defects

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"

        policy = self.config['defects']
        defects = measAlg.DefectListT()
        ccd = engUtil.getCcd(exposure)
        statics = ccd.getDefects() # Static defects
        for defect in statics:
            bbox = defect.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)
        ipIsr.maskBadPixelsDef(exposure, defects, fwhm=None, interpolate=False, maskName='BAD')
        self.log.log(self.log.INFO, "Masked %d static defects." % len(statics))

        grow = policy['grow']
        sat = ipIsr.defectListFromMask(exposure, growFootprints=grow, maskName='SAT') # Saturated defects
        self.log.log(self.log.INFO, "Added %d saturation defects." % len(sat))
        for defect in sat:
            bbox = defect.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)

        exposure.getMaskedImage().getMask().addMaskPlane("UNMASKEDNAN")
        nanMasker = ipIsr.UnmaskedNanCounterF()
        nanMasker.apply(exposure.getMaskedImage())
        nans = ipIsr.defectListFromMask(exposure, maskName='UNMASKEDNAN')
        self.log.log(self.log.INFO, "Added %d unmasked NaNs." % nanMasker.getNpix())
        for defect in nans:
            bbox = defect.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)

        return {'defects': defects}
