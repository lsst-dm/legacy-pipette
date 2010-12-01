#!/usr/bin/env python

import lsst.ip.isr as ipIsr

import lsst.gb3.engine.crank as engCrank
from lsst.gb3.engine.stage import Stage

import lsst.gb3.engine.util as engUtil

class IsrCrank(engCrank.Crank):
    def __init__(self, *args, **kwargs):
        super(IsrCrank, self).__init__(*args, **kwargs)
        self.stages = [Stage('saturation', depends='exposure', always=False),
                       Stage('overscan', depends='exposure', always=False),
                       Stage('trim', depends='exposure', always=True),
                       Stage('bias', depends=['exposure', 'detrends'], always=False),
                       Stage('variance', depends='exposure', always=True),
                       Stage('dark', depends=['exposure', 'detrends'], always=False),
                       Stage('flat', depends=['exposure', 'detrends'], always=False),
                       Stage('fringe', depends=['exposure', 'detrends'], always=False),
                       ]
        return


    def _saturation(self, exposure=None, **kwargs):
        """Mask saturated pixels

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        ccd = engUtil.getCcd(exposure)
        mi = exposure.getMaskedImage()
        Exposure = type(exposure)
        MaskedImage = type(mi)
        for amp in ccd:
            if not engUtil.haveAmp(exposure, amp):
                continue
            saturation = amp.getElectronicParams().getSaturationLevel()
            miAmp = MaskedImage(mi, amp.getDiskDataSec())
            expAmp = Exposure(miAmp)
            bboxes = ipIsr.saturationDetection(expAmp, saturation, doMask = True)
            self.log.log(self.log.INFO, "Masked %d saturated pixels on amp %s: %f" %
                         (len(bboxes), amp.getId(), saturation))
        return

    def _overscan(self, exposure=None, **kwargs):
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

    def _trim(self, exposure=None, **kwargs):
        """Trim overscan out of exposure

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        mi = exposure.getMaskedImage()
        MaskedImage = type(mi)
        if engUtil.detectorIsCcd(exposure):
            # Effectively doing CCD assembly since we have all amplifiers
            ccd = engUtil.getCcd(exposure)
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
            miAmp = MaskedImage(mi, diskDataSec)
            amp.setTrimmed(True)
            exposure.setMaskedImage(miAmp)
        return

    def _trimAmp(self, miTo, miFrom, amp, toDatasec):
        """Trim overscan from amplifier

        @param miTo Target MaskedImage
        @param miFrom Source MaskedImage
        @param amp Amplifier being trimmed
        @param toDatasec Data section on target
        """
        MaskedImage = type(miTo)
        fromDatasec = amp.getDiskDataSec()
        self.log.log(self.log.INFO, "Trimming amp %s: %s --> %s" % (amp.getId(), fromDatasec, toDatasec))
        trimAmp = amp.prepareAmpData(MaskedImage(miFrom, fromDatasec))
        trimImage = MaskedImage(miTo, toDatasec)
        trimImage <<= trimAmp
        amp.setTrimmed(True)
        return

    def _checkDimensions(self, exposure, detrend, name):
        """Check that dimensions of detrend matches that of exposure
        of interest; trim if necessary.

        @param exposure Exposure being processed
        @param detrend Detrend exposure to check
        @param name Name of detrend (for log messages)
        @returns Exposure with matching dimensions
        """
        if detrend.getMaskedImage().getDimensions() == exposure.getMaskedImage().getDimensions():
            return detrend
        self.log.log(self.log.INFO, "Trimming %s to match dimensions" % name)
        self._trim(detrend)
        if detrend.getMaskedImage().getDimensions() != exposure.getMaskedImage().getDimensions():
            raise RuntimeError("Detrend %s is of wrong size: %s vs %s" %
                               (name, detrend.getMaskedImage().getDimensions(),
                                exposure.getMaskedImage().getDimensions()))
        return detrend

    def _bias(self, exposure=None, detrends=None, **kwargs):
        """Bias subtraction

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        bias = self._checkDimensions(exposure, detrends['bias'], "bias")
        self.log.log(self.log.INFO, "Debiasing image")
        ipIsr.biasCorrection(exposure, bias)
        return

    def _variance(self, exposure=None, **kwargs):
        """Set variance from gain

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        mi = exposure.getMaskedImage()
        if engUtil.detectorIsCcd(exposure):
            ccd = engUtil.getCcd(exposure)
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

    def _dark(self, exposure=None, detrends=None, **kwargs):
        """Dark subtraction

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        dark = self._checkDimensions(exposure, detrends['dark'], "dark")
        expTime = float(exposure.getCalib().getExptime())
        darkTime = float(dark.getCalib().getExptime())
        self.log.log(self.log.INFO, "Removing dark (%f sec vs %f sec)" % (expTime, darkTime))
        ipIsr.darkCorrection(exposure, dark, expTime, darkTime)
        return

    def _flat(self, exposure=None, detrends=None, **kwargs):
        """Flat-fielding

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        flat = self._checkDimensions(exposure, detrends['flat'], "flat")
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

    def _fringe(self, exposure=None, detrends=None, **kwargs):
        """Fringe subtraction

        @param exposure Exposure to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        """
        assert exposure, "No exposure provided"
        assert detrends, "No detrends provided"
        fringe = detrends['fringe']
        raise NotimplementedError, "Fringe subtraction is not yet implemented."

