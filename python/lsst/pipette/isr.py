#!/usr/bin/env python

import math

import numpy.random
import numpy.ma as ma

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.afw.math as afwMath
import lsst.afw.cameraGeom as cameraGeom
import lsst.ip.isr as ipIsr
import lsst.meas.algorithms as measAlg
import lsst.pipette.util as pipUtil
import lsst.pipette.process as pipProc
import lsst.pipette.processAmp as pipAmp
import lsst.pipette.background as pipBackground

class Isr(pipProc.Process):
    def __init__(self, ProcessAmp=pipAmp.ProcessAmp, Background=pipBackground.Background, *args, **kwargs):
        super(Isr, self).__init__(*args, **kwargs)
        self._ProcessAmp = ProcessAmp
        self._Background = Background
    
    def run(self, exposureList, detrends=None):
        """Run Instrument Signature Removal (ISR)

        @param exposureList List of exposures to process
        @param detrends Dict with detrends to apply (bias,dark,flat,fringe)
        @return Exposure, list of defects, background
        """
        assert exposureList, "No exposure provided"
        do = self.config['do']['isr']
        if not isinstance(exposureList, list):
            exposureList = [exposureList]

        for exp in exposureList:
            self.processAmp(exp)

        if do['assembly']:
            exposure = self.assembly(exposureList)
            if detrends is not None:
                for kind in detrends.keys():
                    detrends[kind] = self.assembly(detrends[kind])
            self.display('assembly', exposure=exposure)
        else:
            exposure = None

        if do['bias']:
            self.bias(exposure, detrends['bias'])
        if do['variance']:
            self.variance(exposure)
        if do['dark']:
            self.dark(exposure, detrends['dark'])
        if do['flat']:
            self.flat(exposure, detrends['flat'])
        if do['fringe'] and self.config['fringe'].has_key('filters'):
            filtName = exposure.getFilter().getName()
            if filtName in self.config['fringe']['filters']:
                self.fringe(exposure, detrends['fringe'])

        if exposure:
            self.display('flattened', exposure=exposure)

        if do['defects']:
            defects = self.defects(exposure)
        else:
            defects = None

        if do['background']:
            bg, exposure = self.background(exposure)
        else:
            bg = None

        if exposure:
            self.display('isr', exposure=exposure)
            
        return exposure, defects, bg

    def processAmp(self, exposure):
        """Process a single amplifier

        @param exposure Exposure to process
        """
        processAmp = self._ProcessAmp(config=self.config, log=self.log)
        processAmp.run(exposure)

    def assembly(self, exposureList):
        """Assembly of amplifiers into a CCD

        @param exposure List of exposures to be assembled (each is an amp from the same exposure)
        @return Assembled exposure
        """
        if not hasattr(exposureList, "__iter__"):
            # This is not a list; presumably it's a single item needing no assembly
            return exposureList
        assert len(exposureList) > 0, "Nothing in exposureList"
        if len(exposureList) == 1 and exposureList[0].getMaskedImage().getDimensions() == \
           pipUtil.getCcd(exposureList[0]).getAllPixels(True).getDimensions():
            # Special case: single exposure of the correct size
            return exposureList[0]
        
        egExp = exposureList[0]         # The (assumed) model for exposures
        egMi = egExp.getMaskedImage()   # The (assumed) model for masked images
        Exposure = type(egExp)
        MaskedImage = type(egMi)
        ccd = pipUtil.getCcd(egExp)
        miCcd = MaskedImage(ccd.getAllPixels(True).getDimensions())

        for exp in exposureList:
            mi = exp.getMaskedImage()
            if pipUtil.detectorIsCcd(exp):
                for amp in ccd:
                    self._assembleAmp(miCcd, mi, amp)
                exp.setMaskedImage(miCcd)
            else:
                amp = pipUtil.getAmp(exp)
                self._assembleAmp(miCcd, mi, amp)

        exp = afwImage.makeExposure(miCcd, egExp.getWcs())
        exp.setWcs(egExp.getWcs())
        exp.setMetadata(egExp.getMetadata())
        md = exp.getMetadata()
        if md.exists('DATASEC'):
            md.remove('DATASEC')
        exp.setFilter(egExp.getFilter())
        exp.setDetector(ccd)
        exp.getCalib().setExptime(egExp.getCalib().getExptime())
        exp.getCalib().setMidTime(egExp.getCalib().getMidTime())
        return exp

    def _assembleAmp(self, target, source, amp):
        """Assemble an amplifier

        @param target Target image (CCD)
        @param source Source image (amplifier)
        @param amp Amplifier
        """
        sourceDataSec = amp.getDiskDataSec()
        targetDataSec = amp.getDataSec(True)
        self.log.log(self.log.INFO, "Assembling amp %s: %s --> %s" %
                     (amp.getId(), sourceDataSec, targetDataSec))
        sourceTrim = source.Factory(source, sourceDataSec, afwImage.LOCAL)
        sourceTrim = sourceTrim.Factory(amp.prepareAmpData(sourceTrim.getImage()),
                                        amp.prepareAmpData(sourceTrim.getMask()),
                                        amp.prepareAmpData(sourceTrim.getVariance()))
        targetTrim = target.Factory(target, targetDataSec, afwImage.LOCAL)
        targetTrim <<= sourceTrim
        amp.setTrimmed(True)

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

    def _checkDimensions(self, name, exposure, detrend):
        """Check that dimensions of detrend matches that of exposure
        of interest; trim if necessary.

        @param exposure Exposure being processed
        @param detrend Detrend exposure to check
        @returns Exposure with matching dimensions
        """
        if detrend.getMaskedImage().getDimensions() == exposure.getMaskedImage().getDimensions():
            return detrend
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

        # XXX This is a first cut at fringe subtraction.  It should be fairly simple to generalise to allow
        # multiple fringe frames (generated from, e.g., Principal Component Analysis) and solve for the linear
        # combination that best reproduces the fringes on the science frame.        
        # Optimisations:
        # * Push the whole thing into C++
        # * Persist the fringe measurements along with the fringe frame


        science = exposure.getMaskedImage()
        fringe = fringe.getMaskedImage()

        # XXX Fringe can have mask bits set, because afwMath.statisticsStack propagates them
        fringe.getMask().set(0)
        
        width, height = exposure.getWidth(), exposure.getHeight()

        policy = self.config['fringe']
        num = policy['num']
        size = policy['size']
        iterations = policy['iterations']
        clip = policy['clip']
        discard = policy['discard']

        xList = numpy.random.random_integers(width - size, size=num)
        yList = numpy.random.random_integers(height - size, size=num)

        bgStats = afwMath.makeStatistics(science, afwMath.MEDIAN | afwMath.STDEVCLIP)
        bgScience = bgStats.getValue(afwMath.MEDIAN)
        sdScience = bgStats.getValue(afwMath.STDEVCLIP)
        bgFringe = afwMath.makeStatistics(fringe, afwMath.MEDIAN).getValue()

        measScience = ma.zeros(num)
        measFringe = ma.zeros(num)
        for i in range(num):
            x, y = int(xList[i]), int(yList[i])
            bbox = afwGeom.Box2I(afwGeom.Point2I(x, y), afwGeom.Point2I(x + size - 1, y + size - 1))

            subScience = science.Factory(science, bbox, afwImage.LOCAL)
            subFringe = fringe.Factory(fringe, bbox, afwImage.LOCAL)

            measScience[i] = afwMath.makeStatistics(subScience, afwMath.MEDIAN).getValue() - bgScience
            measFringe[i] = afwMath.makeStatistics(subFringe, afwMath.MEDIAN).getValue() - bgFringe

        # Immediately discard measurements that aren't in the background 'noise' (which includes the fringe
        # modulation.  These have been corrupted by objects.
        limit = discard * sdScience
        masked = ma.masked_outside(measScience, -limit, limit)
        measScience.mask = masked.mask
        measFringe.mask = masked.mask

        self.log.log(self.log.DEBUG, "Fringe discard: %f %d" % (limit, measScience.count()))

        regression = lambda x, y, n: ((x * y).sum() - x.sum() * y.sum() / n) / ((x**2).sum() - x.sum()**2 / n)

        # Solve for the fringe amplitude, with rejection of bad points
        lastNum = num
        for i in range(iterations):
            slope = regression(measFringe, measScience, 2.0 * num)
            intercept = measScience.mean() - slope * measFringe.mean()
            
            fit = measFringe * slope + intercept
            resid = measScience - fit
            sort = ma.sort(resid.copy())
            rms = 0.74 * (sort[int(0.75 * lastNum)] - sort[int(0.25 * lastNum)])
            limit = clip * rms

            resid = ma.masked_outside(resid, -limit, limit)
            measScience.mask = resid.mask
            measFringe.mask = resid.mask

            newNum = resid.count()
            self.log.log(self.log.DEBUG, "Fringe iter %d: %f %f %f %d" % (i, slope, intercept, rms, newNum))
            if newNum == lastNum:
                # Iterating isn't buying us anything
                break
            lastNum = newNum

        slope = regression(measFringe, measScience, 2.0 * num)
        self.log.log(self.log.INFO, "Fringe amplitude scaling: %f" % slope)
        science.scaledMinus(slope, fringe)

    def defects(self, exposure):
        """Mask defects

        @param exposure Exposure to process
        @return Defect list
        """
        assert exposure, "No exposure provided"

        policy = self.config['defects']
        defects = measAlg.DefectListT()
        ccd = pipUtil.getCcd(exposure)
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

        return defects

    def background(self, exposure):
        """Background subtraction

        @param exposure Exposure to process
        @return Background, Background-subtracted exposure
        """
        background = self._Background(config=self.config, log=self.log)
        return background.run(exposure)
