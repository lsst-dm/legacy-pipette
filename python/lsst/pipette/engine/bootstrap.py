#!/usr/bin/env python

import math

import lsst.afw.detection as afwDet
import lsst.afw.image as afwImage
import lsst.sdqa as sdqa
import lsst.ip.isr as ipIsr
import lsst.meas.algorithms as measAlg
import lsst.meas.algorithms.psfSelectionRhl as maPsfSel
import lsst.meas.algorithms.psfAlgorithmRhl as maPsfAlg
import lsst.meas.algorithms.ApertureCorrection as maApCorr
import lsst.meas.utils.sourceDetection as muDetection
import lsst.pipette.engine.util as engUtil
import lsst.pipette.engine.process as pipProc
import lsst.pipette.engine.background as pipBackground
import lsst.pipette.engine.fix as pipFix
import lsst.pipette.engine.phot as pipPhot


class Bootstrap(pipProc.Process):
    def run(self, exposureList, wcs=None):
        """Bootstrap a PSF from the exposure

        @param exposureList List of exposures (each is an amp from the same exposure)
        @param wcs World Coordinate System for exposure, or None
        @return Exposure, Defects, PSF, Aperture correction
        """
        assert exposureList is not None, "No exposureList provided"

        do = self.config['do']

        if do['assembly']:
            exposure = self.assembly(exposureList)
        else:
            exposure = exposureList[0]
            
        if do['defects']:
            defects = self.defects(exposure)
        else:
            defects = None

        if do['background']:
            bgProc = pipBackground.Background(config=self.config, log=self.log)
            bg, exposure = bgProc.run(exposure)

        psf, wcs = self.fakePsf(exposure, wcs)

        pipFix.Fix(config=self.config, log=self.log, keepCRs=True).run(exposure, psf, defects=defects)

        if do['phot']:
            threshold = self.config['bootstrap']['thresholdValue']
            phot = pipPhot.Phot(config=self.config, log=self.log, threshold=threshold)
            sources = phot.run(exposure, psf, wcs=wcs)

            psf, cellSet = self.psf(exposure, sources)
            apcorr = self.apCorr(exposure, cellSet)
        else:
            psf = None
            apcorr = None

        self.display('bootstrap', exposure=exposure, sources=sources)
        return exposure, defects, psf, apcorr


    def assembly(self, exposureList):
        """Assembly of amplifiers into a CCD

        @param exposure List of exposures to be assembled (each is an amp from the same exposure)
        @return Assembled exposure
        """
        if not hasattr(exposureList, "__iter__"):
            # This is not a list; presumably it's a single item needing no assembly
            return exposureList
        if len(exposureList) == 1:
            # Special case
            return exposureList[0]
        
        egExp = exposureList[0]         # The (assumed) model for exposures
        egMi = egExp.getMaskedImage()   # The (assumed) model for masked images
        Exposure = type(egExp)
        MaskedImage = type(egMi)
        ccd = engUtil.getCcd(egExp)
        miCcd = MaskedImage(ccd.getAllPixels(True).getDimensions())
        for exp in exposureList:
            amp = engUtil.getAmp(exp)
            mi = exp.getMaskedImage()
            miAmp = MaskedImage(miCcd, amp.getDataSec(True))
            miAmp <<= mi
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

    def defects(self, exposure):
        """Mask defects

        @param exposure Exposure to process
        @return Defect list
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

        return defects

    def fakePsf(self, exposure, wcs=None):
        """Initialise the bootstrap procedure by setting the PSF and WCS

        @param exposure Exposure to process
        @param wcs World coordinate system to use, or None
        @return PSF, WCS
        """
        assert exposure, "No exposure provided"
        if not wcs:
            wcs = exposure.getWcs()
        assert wcs, "No wcs provided"

        bootstrap = self.config['bootstrap']
        model = bootstrap['model']
        fwhm = bootstrap['fwhm'] / wcs.pixelScale()
        size = bootstrap['size']
        psf = afwDet.createPsf(model, size, size, fwhm/(2*math.sqrt(2*math.log(2))))
        return psf, wcs

    def psf(self, exposure, sources):
        """Measure the PSF

        @param exposure Exposure to process
        @param sources Measured sources on exposure
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        psfPolicy = self.config['psf']
        selPolicy = psfPolicy['select'].getPolicy()
        algPolicy = psfPolicy['algorithm'].getPolicy()
        sdqaRatings = sdqa.SdqaRatingSet()
        self.log.log(self.log.INFO, "Measuring PSF")
        psfStars, cellSet = maPsfSel.selectPsfSources(exposure, sources, selPolicy)
        psf, cellSet, psfStars = maPsfAlg.getPsf(exposure, psfStars, cellSet, algPolicy, sdqaRatings)
        return psf, cellSet

    def apCorr(self, exposure, cellSet):
        """Measure aperture correction

        @param exposure Exposure to process
        @param cellSet Set of cells of PSF stars
        """
        assert exposure, "No exposure provided"
        assert cellSet, "No cellSet provided"
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
