#!/usr/bin/env python

import math

import lsst.meas.utils.sourceDetection as muDetection
import lsst.meas.utils.sourceMeasurement as muMeasurement

import lsst.pipette.process as pipProc


class Photometry(pipProc.Process):
    def __init__(self, threshold=None, *args, **kwargs):
        super(Photometry, self).__init__(*args, **kwargs)
        self._threshold = threshold
        return
    
    def run(self, exposure, psf, apcorr=None, wcs=None):
        """Run photometry

        @param exposure Exposure to process
        @param psf PSF for photometry
        @param apcorr Aperture correction to apply
        @param wcs WCS to apply
        @return Positive sources on exposure
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        footprintSet = self.detect(exposure, psf)
        sources = self.measure(exposure, footprintSet, psf, apcorr=apcorr, wcs=wcs)

        self.display('phot', exposure=exposure, sources=sources, pause=True)
        return sources, footprintSet


    def detect(self, exposure, psf):
        """Detect sources

        @param exposure Exposure to process
        @param psf PSF for detection
        @return Positive source footprints
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        policy = self.config['detect']
        if self._threshold is not None:
            oldThreshold = policy['thresholdValue']
            policy['thresholdValue'] = self._threshold
        posSources, negSources = muDetection.detectSources(exposure, psf, policy.getPolicy())
        numPos = len(posSources.getFootprints()) if posSources is not None else 0
        numNeg = len(negSources.getFootprints()) if negSources is not None else 0
        if numNeg > 0:
            self.log.log(self.log.WARN, "%d negative sources found and ignored" % numNeg)
        self.log.log(self.log.INFO, "Detected %d sources to %f." % (numPos, policy['thresholdValue']))
        if self._threshold is not None:
            policy['thresholdValue'] = oldThreshold
        return posSources

    def measure(self, exposure, footprintSet, psf, apcorr=None, wcs=None):
        """Measure sources

        @param exposure Exposure to process
        @param footprintSet Set of footprints to measure
        @param psf PSF for measurement
        @param apcorr Aperture correction to apply
        @param wcs WCS to apply
        @return Source list
        """
        assert exposure, "No exposure provided"
        assert footprintSet, "No footprintSet provided"
        assert psf, "No psf provided"
        policy = self.config['measure'].getPolicy()
        footprints = []                    # Footprints to measure
        num = len(footprintSet.getFootprints())
        self.log.log(self.log.INFO, "Measuring %d positive sources" % num)
        footprints.append([footprintSet.getFootprints(), False])
        sources = muMeasurement.sourceMeasurement(exposure, psf, footprints, policy)

        if wcs is not None:
            muMeasurement.computeSkyCoords(wcs, sources)

        if apcorr is not None:
            for source in sources:
                x, y = source.getXAstrom(), source.getYAstrom()
                flux = source.getPsfFlux()
                fluxErr = source.getPsfFluxErr()
                corr, corrErr = apcorr.computeAt(x, y)
                source.setPsfFlux(flux * corr)
                source.setPsfFluxErr(math.sqrt(corr**2 * fluxErr**2 + corrErr**2 * flux**2))

        return sources


class Rephotometry(Photometry):
    def run(self, exposure, footprints, psf, apcorr=None, wcs=None):
        """Photometer footprints that have already been detected

        @param exposure Exposure to process
        @param footprints Footprints to rephotometer
        @param psf PSF for photometry
        @param apcorr Aperture correction to apply
        @param wcs WCS to apply
        """
        return self.measure(exposure, footprints, psf, apcorr=apcorr, wcs=wcs)
        

    def detect(self, exposure, psf):
        raise NotImplementedError("This method is deliberately not implemented: it should never be run!")
