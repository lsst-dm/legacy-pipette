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
import lsst.pipette.util as pipUtil
import lsst.pipette.process as pipProc
import lsst.pipette.fix as pipFix
import lsst.pipette.phot as pipPhot


class Bootstrap(pipProc.Process):
    def __init__(self, Fix=pipFix.Fix, Phot=pipPhot.Phot,
                 *args, **kwargs):
        super(Bootstrap, self).__init__(*args, **kwargs)
        self._Fix = Fix
        self._Phot = Phot
    
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

        psf, wcs = self.fakePsf(exposure, wcs)

        self.fix(exposure, psf, defects=defects)

        if do['phot']:
            sources = self.phot(exposure, psf, wcs=wcs)

            psf, cellSet = self.psf(exposure, sources)
            apcorr = self.apCorr(exposure, cellSet)
        else:
            sources = None
            psf = None
            apcorr = None

        self.display('bootstrap', exposure=exposure, sources=sources)
        return exposure, defects, psf, apcorr



    def fakePsf(self, exposure, wcs=None):
        """Initialise the bootstrap procedure by setting the PSF and WCS

        @param exposure Exposure to process
        @param wcs World coordinate system to use, or None
        @return PSF, WCS
        """
        assert exposure, "No exposure provided"
        if wcs is None:
            wcs = exposure.getWcs()
        assert wcs is not None, "No wcs provided"

        bootstrap = self.config['bootstrap']
        model = bootstrap['model']
        fwhm = bootstrap['fwhm'] / wcs.pixelScale()
        size = bootstrap['size']
        psf = afwDet.createPsf(model, size, size, fwhm/(2*math.sqrt(2*math.log(2))))
        return psf, wcs


    def fix(self, exposure, psf, defects=None):
        """Fix CCD problems (defects, CRs)

        @param exposure Exposure to process
        @param psf Point Spread Function
        @param defects Defect list, or None
        """
        fix = self._Fix(config=self.config, log=self.log, keepCRs=True)
        fix.run(exposure, psf, defects=defects)

    def phot(self, exposure, psf, apcorr=None, wcs=None):
        """Perform photometry

        @param exposure Exposure to process
        @param psf Point Spread Function
        @param apcorr Aperture correction, or None
        @param wcs World Coordinate System, or None
        @return Source list
        """
        threshold = self.config['bootstrap']['thresholdValue']
        phot = self._Phot(config=self.config, log=self.log, threshold=threshold)
        return phot.run(exposure, psf, wcs=wcs)


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
