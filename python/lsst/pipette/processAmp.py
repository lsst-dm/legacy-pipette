#!/usr/bin/env python

import math
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.afw.cameraGeom as cameraGeom
import lsst.ip.isr as ipIsr
import lsst.pipette.util as pipUtil
import lsst.pipette.process as pipProc

class ProcessAmp(pipProc.Process):
    def run(self, exposure):
        """Process a single amplifier

        @param exposure Exposure (with single amp) to process
        """
        assert exposure, "No exposure provided"
        do = self.config['do']['isr']['processAmp']

        if do['saturation']:
            self.saturation(exposure)

        if do['overscan']:
            self.overscan(exposure)

        if do['linearize']:
            self.linearize(exposure)

        # XXX trim is unnecessary given CCD assembly
        #if do['trim']:
        #    self.trim(exposure)

        self.display('amp', exposure=exposure, pause=True)
        return
    

    def linearize(self, exposure):
        """Correct for non-linearity

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"

        image = exposure.getMaskedImage().getImage()

        ccd = pipUtil.getCcd(exposure)

        for amp in ccd:
            if not pipUtil.haveAmp(exposure, amp):
                continue

            if False:
                linear_threshold = amp.getElectronicParams().getLinearizationThreshold()
                linear_c = amp.getElectronicParams().getLinearizationCoefficient()
            else:
                linear_threshold = self.config["linearize"]["threshold"]
                linear_c = self.config["linearize"]["coefficient"]

            if linear_c == 0.0:     # nothing to do
                continue
            
            self.log.log(self.log.INFO,
                         "Applying linearity corrections to Ccd %s Amp %s" % (ccd.getId(), amp.getId()))

            log10_thresh = math.log10(linear_threshold)

            ampImage = image.Factory(image, amp.getDiskDataSec(), afwImage.LOCAL)

            width, height = ampImage.getDimensions()

            for y in range(height):
                for x in range(width):
                    val = ampImage.get(x, y)
                    if True:
                        val += linear_c*val*val
                        ampImage.set(x, y, val)
                    else:
                        if val > linear_threshold:
                            val += val*linear_c*(math.log10(val) - log10_thresh)
                            ampImage.set(x, y, val)

    def saturation(self, exposure):
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
            miAmp = MaskedImage(mi, amp.getDiskDataSec(), afwImage.PARENT)
            expAmp = Exposure(miAmp)
            bboxes = ipIsr.saturationDetection(expAmp, saturation, doMask = True)
            self.log.log(self.log.INFO, "Masked %d saturated objects on amp %s: %f" %
                         (len(bboxes), amp.getId(), saturation))
        return

    def overscan(self, exposure):
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
            # we'll do this ourselves.  The options for overscan correction are currently quite limited, so
            # we're not missing out on anything.
            #ipIsr.overscanCorrection(exposure, biassec, "MEDIAN")

            datasec = amp.getDiskDataSec()
            overscan = MaskedImage(mi, biassec, afwImage.LOCAL)
            image = MaskedImage(mi, datasec, afwImage.LOCAL)
            offset = afwMath.makeStatistics(overscan, afwMath.MEDIAN).getValue(afwMath.MEDIAN)
            self.log.log(self.log.INFO, "Overscan correction on amp %s, %s: %f" %
                         (amp.getId(), biassec, offset))
            image -= offset
        return


    def trim(self, exposure):
        """Trim overscan out of exposure

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        mi = exposure.getMaskedImage()
        MaskedImage = type(mi)
        if pipUtil.detectorIsCcd(exposure):
            # Effectively doing CCD assembly since we have all amplifiers
            ccd = pipUtil.getCcd(exposure)
            miCcd = MaskedImage(ccd.getAllPixels(True).getDimensions())
            for amp in ccd:
                diskDataSec = amp.getDiskDataSec()
                trimDataSec = amp.getElectronicDataSec(True)
                miTrim = MaskedImage(mi, diskDataSec, afwImage.LOCAL)
                miTrim = MaskedImage(amp.prepareAmpData(miTrim.getImage()),
                                     amp.prepareAmpData(miTrim.getMask()),
                                     amp.prepareAmpData(miTrim.getVariance()))
                miAmp = MaskedImage(miCcd, trimDataSec, afwImage.LOCAL)
                self.log.log(self.log.INFO, "Trimming amp %s: %s --> %s" %
                             (amp.getId(), diskDataSec, trimDataSec))
                miAmp <<= miTrim
                amp.setTrimmed(True)
            exposure.setMaskedImage(miCcd)
        else:
            # AFW doesn't provide a useful target datasec, so we just make an image that has the useful pixels
            amp = cameraGeom.cast_Amp(exposure.getDetector())
            diskDataSec = amp.getDiskDataSec()
            self.log.log(self.log.INFO, "Trimming amp %s: %s" % (amp.getId(), diskDataSec))
            miTrim = MaskedImage(mi, diskDataSec, afwImage.LOCAL)
            amp.setTrimmed(True)
            miAmp = MaskedImage(amp.prepareAmpData(miTrim.getImage()),
                                amp.prepareAmpData(miTrim.getMask()),
                                amp.prepareAmpData(miTrim.getVariance()))
            exposure.setMaskedImage(miAmp)
        return
