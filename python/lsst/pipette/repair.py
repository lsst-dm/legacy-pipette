#!/usr/bin/env python

import lsst.afw.math as afwMath
import lsst.afw.detection as afwDet
import lsst.meas.algorithms as measAlg
import lsst.pipette.process as pipProc

import lsst.afw.display.ds9 as ds9
import lsst.afw.display.utils as displayUtils

class Repair(pipProc.Process):
    def __init__(self, keepCRs=False, *args, **kwargs):
        super(Repair, self).__init__(*args, **kwargs)
        self._keepCRs = keepCRs
        return
    
    def run(self, exposure, psf, defects=None):
        """Repair exposure's instrumental problems

        @param exposure Exposure to process
        @param psf Point spread function
        @param defects Defect list
        """
        import lsstDebug
        display = lsstDebug.Info(__name__).display

        assert exposure, "No exposure provided"

        do = self.config['do']['calibrate']['repair']

        if display:
            ds9.setDefaultFrame(0)
            ds9.mtv(exposure, title="Pre-repair")

        if defects is not None and do['interpolate']:
            self.interpolate(exposure, psf, defects)

        if do['cosmicray']:
            self.cosmicray(exposure, psf)

        self.display('repair', exposure=exposure)
        return

    def interpolate(self, exposure, psf, defects):
        """Interpolate over defects

        @param exposure Exposure to process
        @param psf PSF for interpolation
        @param defects Defect list
        """
        assert exposure, "No exposure provided"
        assert defects is not None, "No defects provided"
        assert psf, "No psf provided"
        mi = exposure.getMaskedImage()
        fallbackValue = afwMath.makeStatistics(mi, afwMath.MEANCLIP).getValue()
        measAlg.interpolateOverDefects(mi, psf, defects, fallbackValue)
        self.log.log(self.log.INFO, "Interpolated over %d defects." % len(defects))
        return

    def cosmicray(self, exposure, psf):
        """Cosmic ray masking

        @param exposure Exposure to process
        @param psf PSF
        """
        import lsstDebug
        display = lsstDebug.Info(__name__).display
        displayCR = lsstDebug.Info(__name__).displayCR

        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        # Blow away old mask
        try:
            mask = exposure.getMaskedImage().getMask()
            crBit = mask.getMaskPlane("CR")
            mask.clearMaskPlane(crBit)
        except: pass
        
        policy = self.config['cosmicray'].getPolicy()
        mi = exposure.getMaskedImage()
        bg = afwMath.makeStatistics(mi, afwMath.MEDIAN).getValue()
        crs = measAlg.findCosmicRays(mi, psf, bg, policy, self._keepCRs)
        num = 0
        if crs is not None:
            mask = mi.getMask()
            crBit = mask.getPlaneBitMask("CR")
            afwDet.setMaskFromFootprintList(mask, crs, crBit)
            num = len(crs)

            if display and displayCR:
                ds9.incrDefaultFrame()
                ds9.mtv(exposure, title="Post-CR")
                
                ds9.cmdBuffer.pushSize()

                for cr in crs:
                    displayUtils.drawBBox(cr.getBBox(), borderWidth=0.55)

                ds9.cmdBuffer.popSize()

        self.log.log(self.log.INFO, "Identified %d cosmic rays." % num)
        return

