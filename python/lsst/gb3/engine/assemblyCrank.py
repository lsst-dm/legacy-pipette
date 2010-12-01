#!/usr/bin/env python

import lsst.afw.image as afwImage
import lsst.ip.isr as ipIsr
import lsst.meas.algorithms as measAlg
import lsst.meas.utils.sourceDetection as muDetection

import lsst.gb3.engine.util as engUtil
import lsst.gb3.engine.crank as engCrank
from lsst.gb3.engine.stage import Stage

class AssemblyCrank(engCrank.Crank):
    def __init__(self, *args, **kwargs):
        super(AssemblyCrank, self).__init__(*args, **kwargs)
        self.stages = [Stage('assembly', depends='exposure', always=True),
                       Stage('defects', depends='exposure', always=False),
                       Stage('background', depends='exposure', always=True),
                       ]
        return

    def _assembly(self, exposure=None, **kwargs):
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

    def _defects(self, exposure=None, **kwargs):
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

    def _background(self, exposure=None, **kwargs):
        """Background subtraction

        @param exposure Exposure to process
        """
        policy = self.config['background'].getPolicy()
        bg, subtracted = muDetection.estimateBackground(exposure, policy, subtract=True)
        return {'background': bg,
                'exposure': subtracted}
