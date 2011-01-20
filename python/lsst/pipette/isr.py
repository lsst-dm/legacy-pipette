#!/usr/bin/env python

import lsst.afw.math as afwMath
import lsst.afw.cameraGeom as cameraGeom
import lsst.ip.isr as ipIsr
import lsst.pipette.util as pipUtil
import lsst.pipette.process as pipProc

class Isr(pipProc.Process):
    def run(self, exposure, detrends=None):
        """Run Instrument Signature Removal (ISR)

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        do = self.config['do']
        if do['saturation']:
            self.saturation(exposure)
        if do['overscan']:
            self.overscan(exposure)
        if do['trim']:
            self.trim(exposure)
        if do['bias']:
            self.bias(exposure, detrends['bias'])
        if do['variance']:
            self.variance(exposure)
        if do['dark']:
            self.dark(exposure, detrends['dark'])
        if do['flat']:
            self.flat(exposure, detrends['flat'])
        if do['fringe']:
            self.fringe(exposure, detrends['fringe'])

        self.display('isr', exposure=exposure)
        return
    

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
            miAmp = MaskedImage(mi, amp.getDiskDataSec())
            expAmp = Exposure(miAmp)
            bboxes = ipIsr.saturationDetection(expAmp, saturation, doMask = True)
            self.log.log(self.log.INFO, "Masked %d saturated pixels on amp %s: %f" %
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
            overscan = MaskedImage(mi, biassec)
            image = MaskedImage(mi, datasec)
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
                trimDataSec = amp.getDataSec(True)
                miTrim = MaskedImage(mi, diskDataSec)
                miTrim = MaskedImage(amp.prepareAmpData(miTrim.getImage()),
                                     amp.prepareAmpData(miTrim.getMask()),
                                     amp.prepareAmpData(miTrim.getVariance()))
                miAmp = MaskedImage(miCcd, trimDataSec)
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
            miTrim = MaskedImage(mi, diskDataSec)
            amp.setTrimmed(True)
            miAmp = MaskedImage(amp.prepareAmpData(miTrim.getImage()),
                                amp.prepareAmpData(miTrim.getMask()),
                                amp.prepareAmpData(miTrim.getVariance()))
            exposure.setMaskedImage(miAmp)
        return


    def _checkDimensions(self, name, exposure, detrend):
        """Check that dimensions of detrend matches that of exposure
        of interest; trim if necessary.

        @param exposure Exposure being processed
        @param detrend Detrend exposure to check
        @returns Exposure with matching dimensions
        """
        if detrend.getMaskedImage().getDimensions() == exposure.getMaskedImage().getDimensions():
            return detrend
        self.log.log(self.log.INFO, "Trimming %s to match dimensions" % name)
        self.trim(detrend)
        if detrend.getMaskedImage().getDimensions() != exposure.getMaskedImage().getDimensions():
            raise RuntimeError("Detrend %s is of wrong size: %s vs %s" %
                               (name, detrend.getMaskedImage().getDimensions(),
                                exposure.getMaskedImage().getDimensions()))
        return detrend

    def bias(self, exposure, bias):
        """Bias subtraction

        @param exposure Exposure to process
        @param bias Bias frame to apply
        """
        assert exposure, "No exposure provided"
        assert bias, "No bias provided"
        bias = self._checkDimensions("bias", exposure, bias)
        self.log.log(self.log.INFO, "Debiasing image")
        ipIsr.biasCorrection(exposure, bias)
        return

    def variance(self, exposure):
        """Set variance from gain

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        mi = exposure.getMaskedImage()
        if pipUtil.detectorIsCcd(exposure):
            ccd = pipUtil.getCcd(exposure)
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

    def dark(self, exposure, dark):
        """Dark subtraction

        @param exposure Exposure to process
        @param dark Dark frame to apply
        """
        assert exposure, "No exposure provided"
        assert dark, "No dark provided"
        dark = self._checkDimensions("dark", exposure, dark)
        expTime = float(exposure.getCalib().getExptime())
        darkTime = float(dark.getCalib().getExptime())
        self.log.log(self.log.INFO, "Removing dark (%f sec vs %f sec)" % (expTime, darkTime))
        ipIsr.darkCorrection(exposure, dark, expTime, darkTime)
        return

    def flat(self, exposure, flat):
        """Flat-fielding

        @param exposure Exposure to process
        @param flat Flat frame to apply
        """
        assert exposure, "No exposure provided"
        assert flat, "No flat provided"
        flat = self._checkDimensions("flat", exposure, flat)
        mi = exposure.getMaskedImage()
        image = mi.getImage()
        variance = mi.getVariance()
        flatImage = flat.getMaskedImage().getImage()
        self.log.log(self.log.INFO, "Flattening image")
        # XXX This looks awful because AFW doesn't define useful functions.  Need to fix this.
        image /= flatImage
        variance /= flatImage
        variance /= flatImage
        ### This API is bad --- you NEVER want to rescale your flat on the fly.
        ### Scale it properly when you make it and never rescale again.
        #ipIsr.flatCorrection(exposure, flat, "USER", 1.0)
        return

    def fringe(self, exposure, fringe):
        """Fringe subtraction

        @param exposure Exposure to process
        @param frome Fringe frame to apply
        """
        assert exposure, "No exposure provided"
        assert fringe, "No fringe provided"
        fringe = self._checkDimensions("fringe", exposure, fringe)
        raise NotimplementedError, "Fringe subtraction is not yet implemented."

