#!/usr/bin/env python
#
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import os
import re
import math

import lsst.gb3.engine.config as engConfig

import lsstDebug
import lsst.pex.logging as pexLog
import lsst.afw.cameraGeom as cameraGeom
import lsst.afw.math as afwMath
import lsst.afw.image as afwImage
import lsst.afw.image.utils as imageUtils
import lsst.afw.detection as afwDet
import lsst.ip.isr as ipIsr
import lsst.ip.utils as ipUtils
import lsst.meas.utils.sourceDetection as muDetection
import lsst.meas.utils.sourceMeasurement as muMeasurement
import lsst.meas.algorithms as measAlg
import lsst.meas.algorithms.psfSelectionRhl as maPsfSel
import lsst.meas.algorithms.psfAlgorithmRhl as maPsfAlg
import lsst.meas.algorithms.ApertureCorrection as maApCorr
import lsst.meas.astrom as measAst
import lsst.meas.astrom.net as astromNet
import lsst.meas.astrom.sip as astromSip
import lsst.meas.astrom.verifyWcs as astromVerify
import lsst.meas.photocal as photocal

import lsst.afw.display.ds9 as ds9

import lsst.sdqa as sdqa


"""This module defines the Crank base class for LSST Algorithms testing (Green Blob 3)."""

class Crank(object):

    """Crank is a base class for LSST Algorithms testing (Green Blob 3).


    Public methods: read, isr, ccdAssembly, imgChar, write
    """

    def __init__(self,                  # Crank
                 name,                  # Base name for outputs
                 config=None,           # Configuration
                 ):
        self.name = name
        self.log = pexLog.Log(pexLog.getDefaultLog(), "Crank")
        self.config = engConfig.configuration() if config is None else config
        self.do = self.config['do']
        self.display = lsstDebug.Info(__name__).display
        return

    def turn(self, exposure, ccd, detrends):
        self.isr(exposure, ccd, detrends)
        exposure = self.ccdAssembly(exposure)
        exposure, psf, sources, matches, wcs = self.imageChar(exposure)
        return exposure, psf, sources, matches, wcs

    def isr(self,
            exposure,                   # Exposure to correct
            ccd,                        # Ccd from camera
            detrends,                   # Dict of detrends
            ):
        """Instrument signature removal: generate mask and variance;
        subtract overscan, bias, dark; divide by flat-field;
        subtract fringes.
        """
        self._display("raw", exposure)
        if self.do['saturation']:
            self._saturation(exposure)
        if self.do['overscan']:
            self._overscan(exposure)
        self._trim(exposure, ccd)
        if self.do['bias']:
            self._bias(exposure, detrends)
        self._variance(exposure)
        if self.do['dark']:
            self._dark(exposure, detrends)
        if self.do['flat']:
            self._flat(exposure, detrends)
        if self.do['fringe']:
            self._fringe(exposure, detrends)
        self._display("isr", exposure)
        return


    def ccdAssembly(self, exposureList):
        """Assembly of amplifiers into CCDs.
        Also applies defects (static mask)."""
        exposure = self._assembly(exposureList)
        return exposure


    def imageChar(self, exposure):
        """Image characterisation: background subtraction,
        cosmic-ray rejection, source detection and measurement,
        PSF determination, and photometric and astrometric
        calibration."""

        # Default return values
        bgSubExp = None
        psf = None
        apCorr = None
        sources = None
        matches = None
        wcs = exposure.getWcs()

        # Initial PSF
        bootstrap = self.config['bootstrap']
        model = bootstrap['model']
        fwhm = bootstrap['fwhm'] / wcs.pixelScale()
        size = bootstrap['size']
        bsPsf = afwDet.createPsf(model, size, size, fwhm/(2*math.sqrt(2*math.log(2))))

        if self.do['defects']:
            defects = self._defects(exposure, fwhm)
        else:
            defects = None
        if self.do['interpolate']:
            # Doing this in order to measure the PSF may not be necessary
            self._interpolate(exposure, defects, bsPsf)
        if self.do['background']:
            bgSubExp = self._background(exposure)
        else:
            bgSubExp = exposure

        if self.do['cr']:
            # Doing this in order to measure the PSF may not be necessary
            self._cosmicray(bgSubExp, bsPsf, True)

        if self.do['phot']:
            bsThreshold = bootstrap['thresholdValue']
            posSources, negSources = self._detect(bgSubExp, threshold=bsThreshold)
            sources = self._measure(bgSubExp, posSources, negSources, psf=bsPsf, wcs=wcs, apCorr=apCorr)
            self._display("bootstrap", bgSubExp, sources)
            psf, cellSet = self._psfMeasurement(bgSubExp, sources)
            apCorr = self._apCorr(bgSubExp, cellSet)
            if self.do['interpolate']:
                # Repeating this with the proper PSF may not be necessary
                self._interpolate(exposure, defects, psf)
            if self.do['cr']:
                # Repeating this with the proper PSF may not be necessary
                mask = bgSubExp.getMaskedImage().getMask()
                crBit = mask.getMaskPlane("CR")
                mask.clearMaskPlane(crBit)
                self._cosmicray(bgSubExp, psf, False)
            posSources, negSources = self._detect(bgSubExp, psf=psf)
            sources = self._measure(bgSubExp, posSources, negSources, psf=psf, wcs=wcs, apCorr=apCorr)
            self._display("phot", bgSubExp, sources)
        if self.do['ast'] and sources is not None:
            matches, wcs = self._astrometry(bgSubExp, sources)
        if self.do['cal'] and matches is not None and len(matches) > 0:
            self._photcal(bgSubExp, matches)

        return bgSubExp, psf, sources, matches, wcs




##############################################################################################################
# ISR methods
##############################################################################################################

    def _saturation(self, exposure):
        ccd = exposure.getDetector()
        mi = exposure.getMaskedImage()
        Exposure = type(exposure)
        MaskedImage = type(mi)
        for amp in cameraGeom.cast_Ccd(ccd):
            saturation = amp.getElectronicParams().getSaturationLevel()
            miAmp = MaskedImage(mi, amp.getDataSec())
            expAmp = Exposure(miAmp)
            bboxes = ipIsr.saturationDetection(expAmp, saturation, doMask = True)
            self.log.log(self.log.INFO, "Masked %d saturated pixels on amp %s: %f" %
                         (len(bboxes), amp.getId(), saturation))
        return

    def _overscan(self, exposure):
        fittype = "MEDIAN"                # XXX policy argument
        ccd = exposure.getDetector()
        for amp in cameraGeom.cast_Ccd(ccd):
            biassec = amp.getDiskBiasSec()
            self.log.log(self.log.INFO, "Doing overscan correction on amp %s: %s" % (amp.getId(), biassec))
            ipIsr.overscanCorrection(exposure, biassec, fittype)
        return

    def _trim(self, exposure, ccd):
        miBefore = exposure.getMaskedImage()
        MaskedImage = type(miBefore)
        miAfter = MaskedImage(ccd.getAllPixels(True).getDimensions())
        for amp in ccd:
            datasecBefore = amp.getDataSec(False)
            datasecAfter = amp.getDataSec(True)
            self.log.log(self.log.INFO, "Trimming amp %s: %s --> %s" %
                         (amp.getId(), datasecBefore, datasecAfter))
            trimAmp = MaskedImage(miBefore, datasecBefore)
            trimImage = MaskedImage(miAfter, datasecAfter)
            trimImage <<= trimAmp
            amp.setTrimmed(True)
        exposure.setMaskedImage(miAfter)
        return


    def _bias(self, exposure, detrends):
        bias = detrends['bias']
        self.log.log(self.log.INFO, "Debiasing image")
        ipIsr.biasCorrection(exposure, bias)
        return

    def _variance(self, exposure):
        ccd = exposure.getDetector()
        mi = exposure.getMaskedImage()
        MaskedImage = type(mi)
        for amp in cameraGeom.cast_Ccd(ccd):
            gain = amp.getElectronicParams().getGain()
            self.log.log(self.log.INFO, "Setting variance for amp %s: %f" % (amp.getId(), gain))
            miAmp = MaskedImage(mi, amp.getDataSec())
            variance = miAmp.getVariance()
            variance <<= miAmp.getImage()
            variance /= gain
        return

    def _dark(self, exposure, detrends):
        dark = detrends['dark']
        expTime = float(exposure.getCalib().getExptime())
        darkTime = float(dark.getCalib().getExptime())
        self.log.log(self.log.INFO, "Removing dark (%f sec vs %f sec)" % (expTime, darkTime))
        ipIsr.darkCorrection(exposure, dark, expTime, darkTime)
        return

    def _flat(self, exposure, detrends):
        flat = detrends['flat']
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

    def _fringe(self, exposure, detrends):
        fringe = detrends['fringe']
        raise NotimplementedError, "Fringe subtraction is not yet implemented."

##############################################################################################################
# CCD assembly method
##############################################################################################################

    def _assembly(self, exposureList):
        if not hasattr(exposureList, "__getitem__"):
            # This is not a list; presumably it's a single item needing no assembly
            return exposureList
        rmKeys = ["CCDID", "AMPID", "E2AOCHI", "E2AOFILE",
                  "DC3BPATH", "GAIN", "BIASSEC", "DATASEC"]    # XXX policy argument
        amp = cameraGeom.cast_Amp(exposureList[0].getDetector())
        ccd = cameraGeom.cast_Ccd(amp.getParent())
        exposure = ipIsr.ccdAssemble.assembleCcd(exposureList, ccd, keysToRemove=rmKeys)
        return exposure

##############################################################################################################
# Image characterisation methods
##############################################################################################################

    def _defects(self, exposure, fwhm):
        policy = self.config['defects']
        defects = measAlg.DefectListT()
        statics = cameraGeom.cast_Ccd(exposure.getDetector()).getDefects() # Static defects
        for defect in statics:
            bbox = defect.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)
        ipIsr.maskBadPixelsDef(exposure, defects, fwhm, interpolate=False, maskName='BAD')
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

    def _interpolate(self, exposure, defects, psf):
        mi = exposure.getMaskedImage()
        fallbackValue = afwMath.makeStatistics(mi.getImage(), afwMath.MEANCLIP).getValue()
        measAlg.interpolateOverDefects(mi, psf, defects, fallbackValue)
        self.log.log(self.log.INFO, "Interpolated over %d defects." % len(defects))
        return

    def _background(self, exposure):
        policy = self.config['background'].getPolicy()
        bg, subtracted = muDetection.estimateBackground(exposure, policy, subtract=True)
        # XXX Dropping bg on the floor
        return subtracted

    def _cosmicray(self, exposure, psf, keepCRs=True):
        policy = self.config['cr'].getPolicy()
        mi = exposure.getMaskedImage()
        bg = afwMath.makeStatistics(mi, afwMath.MEDIAN).getValue()
        crs = measAlg.findCosmicRays(mi, psf, bg, policy, keepCRs)
        num = 0
        if crs is not None:
            mask = mi.getMask()
            crBit = mask.getPlaneBitMask("CR")
            afwDet.setMaskFromFootprintList(mask, crs, crBit)
            num = len(crs)
        self.log.log(self.log.INFO, "Identified %d cosmic rays." % num)
        return

    def _detect(self, exposure, psf=None, threshold=None):
        policy = self.config['detect']
        if threshold is not None:
            oldThreshold = policy['thresholdValue']
            policy['thresholdValue'] = threshold
        posSources, negSources = muDetection.detectSources(exposure, psf, policy.getPolicy())
        numPos = len(posSources.getFootprints()) if posSources is not None else 0
        numNeg = len(negSources.getFootprints()) if negSources is not None else 0
        self.log.log(self.log.INFO, "Detected %d positive and %d negative sources to %f." %
                     (numPos, numNeg, policy['thresholdValue']))
        if threshold is not None:
            policy['thresholdValue'] = oldThreshold
        return posSources, negSources

    def _measure(self, exposure, posSources, negSources=None, psf=None, wcs=None, apCorr=None):
        policy = self.config['measure'].getPolicy()
        footprints = []                    # Footprints to measure
        if posSources:
            num = len(posSources.getFootprints())
            self.log.log(self.log.INFO, "Measuring %d positive sources" % num)
            footprints.append([posSources.getFootprints(), False])
        if negSources:
            num = len(negSources.getFootprints())
            self.log.log(self.log.INFO, "Measuring %d positive sources" % num)
            footprints.append([negSources.getFootprints(), True])

        sources = muMeasurement.sourceMeasurement(exposure, psf, footprints, policy)

        if wcs is not None:
            muMeasurement.computeSkyCoords(wcs, sources)

        if apCorr is not None:
            for source in sources:
                x, y = source.getXAstrom(), source.getYAstrom()
                flux = source.getPsfFlux()
                fluxErr = source.getPsfFluxErr()
                corr, corrErr = apCorr.computeAt(x, y)
                source.setPsfFlux(flux * corr)
                source.setPsfFluxErr(math.sqrt(corr**2 * fluxErr**2 + corrErr**2 * flux**2))

        return sources

    def _psfMeasurement(self, exposure, sources):
        psfPolicy = self.config['psf']
        selPolicy = psfPolicy['select'].getPolicy()
        algPolicy = psfPolicy['algorithm'].getPolicy()
        sdqaRatings = sdqa.SdqaRatingSet()
        self.log.log(self.log.INFO, "Measuring PSF")
        psfStars, cellSet = maPsfSel.selectPsfSources(exposure, sources, selPolicy)
        psf, cellSet, psfStars = maPsfAlg.getPsf(exposure, psfStars, cellSet, algPolicy, sdqaRatings)
        return psf, cellSet

    def _apCorr(self, exposure, cellSet):
        policy = self.config['apcorr'].getPolicy()
        control = maApCorr.ApertureCorrectionControl(policy)
        sdqaRatings = sdqa.SdqaRatingSet()
        corr = maApCorr.ApertureCorrection(exposure, cellSet, sdqaRatings, control, self.log)
        sdqaRatings = dict(zip([r.getName() for r in sdqaRatings], [r for r in sdqaRatings]))
        x, y = exposure.getWidth() / 2.0, exposure.getHeight() / 2.0
        value, error = corr.computeAt(x, y)
        self.log.log(self.log.INFO, "Aperture correction using %d/%d stars: %f +/- %f" %
                     (sdqaRatings["phot.apCorr.numAvailStars"].getValue(),
                      sdqaRatings["phot.apCorr.numGoodStars"].getValue(),
                      value, error))
        return corr

    def _astrometry(self, exposure, sources):
        policy = self.config['ast']
        path=os.path.join(os.environ['ASTROMETRY_NET_DATA_DIR'], "metadata.paf")
        solver = astromNet.GlobalAstrometrySolution(path)
        #solver.allowDistortion(self.policy.get('allowDistortion'))
        #solver.setMatchThreshold(self.policy.get('matchThreshold'))
        self.log.log(self.log.INFO, "Solving astrometry")

        if True:
            solver.setMatchThreshold(policy['matchThreshold'])
            solver.setStarlist(sources)
            solver.setNumBrightObjects(min(policy['numBrightStars'], len(sources)))
            solver.setImageSize(exposure.getWidth(), exposure.getHeight())
            if not solver.solve(exposure.getWcs()):
                raise RuntimeError("Unable to solve astrometry")
            wcs = solver.getWcs()
            matches = solver.getMatchedSources(policy['defaultFilterName'])
            sipFitter = astromSip.CreateWcsWithSip(matches, wcs, policy['sipOrder'])
            wcs = sipFitter.getNewWcs()
            exposure.setWcs(wcs)
        else:
            matches, wcs = measAst.determineWcs(policy.getPolicy(), exposure, sources,
                                                solver=solver, log=self.log)
            if matches is not None or len(matches) == 0:
                raise RuntimeError("Unable to find any matches")

        verify = dict()                    # Verification parameters
        verify.update(astromSip.sourceMatchStatistics(matches))
        verify.update(astromVerify.checkMatches(matches, exposure, self.log))
        for k, v in verify.items():
            exposure.getMetadata().set(k, v)
        return matches, wcs

    def _photcal(self, exposure, matches):
        zp = photocal.calcPhotoCal(matches, log=self.log, goodFlagValue=0)
        self.log.log(self.log.INFO, "Photometric zero-point: %f" % zp.getMag(1.0))
        exposure.getCalib().setFluxMag0(zp.getFlux(0))
        return


    def _display(self, name, exposure=None, sources=None):
        if not self.display or not self.display.has_key(name) or self.display[name] <= 0:
            return
        frame = self.display[name]

        if exposure:
            mi = exposure.getMaskedImage()
            ds9.mtv(mi, frame=frame, title=name)
            x0, y0 = mi.getX0(), mi.getY0()
        else:
            x0, y0 = 0, 0

        if sources:
            for source in sources:
                xc, yc = source.getXAstrom() - x0, source.getYAstrom() - y0
                ds9.dot("o", xc, yc, size=4, frame=frame)
                #try:
                #    mag = 25-2.5*math.log10(source.getPsfFlux())
                #    if mag > 15: continue
                #except: continue
                #ds9.dot("%.1f" % mag, xc, yc, frame=frame, ctype="red")

        #raw_input("Press [ENTER] when ready....")
        return

