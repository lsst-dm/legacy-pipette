#!/usr/bin/env python

import lsst.afw.math as afwMath
import lsst.afw.detection as afwDet
import lsst.meas.algorithms as measAlg
from lsst.pipette.stage import BaseStage

class Cr(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Cr, self).__init__(requires=['exposure', 'psf'], *args, **kwargs)
        self.keepCRs = False
        return

    def run(self, exposure=None, psf=None, **kwargs):
        """Cosmic ray masking

        @param exposure Exposure to process
        @param psf PSF
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        # Blow away old mask
        try:
            mask = exposure.getMaskedImage().getMask()
            crBit = mask.getMaskPlane("CR")
            mask.clearMaskPlane(crBit)
        except: pass
        
        policy = self.config['cr'].getPolicy()
        mi = exposure.getMaskedImage()
        bg = afwMath.makeStatistics(mi, afwMath.MEDIAN).getValue()
        crs = measAlg.findCosmicRays(mi, psf, bg, policy, self.keepCRs)
        num = 0
        if crs is not None:
            mask = mi.getMask()
            crBit = mask.getPlaneBitMask("CR")
            afwDet.setMaskFromFootprintList(mask, crs, crBit)
            num = len(crs)
        self.log.log(self.log.INFO, "Identified %d cosmic rays." % num)
        return


class CrIdentify(Cr):
    """Stage to find and mask cosmic rays, but not clobber the pixels.
    We'll clobber the pixels later when we know the true PSF.
    """
    def __init__(self, *args, **kwargs):
        super(CrIdentify, self).__init__(*args, **kwargs)
        self.keepCRs = True
        return
