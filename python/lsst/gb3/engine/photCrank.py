#!/usr/bin/env python

import math

import lsst.meas.utils.sourceDetection as muDetection
import lsst.meas.utils.sourceMeasurement as muMeasurement

import lsst.gb3.engine.distortion as engDist
import lsst.gb3.engine.crank as engCrank
from lsst.gb3.engine.stage import Stage

class PhotCrank(engCrank.Crank):
    def __init__(self, *args, **kwargs):
        super(PhotCrank, self).__init__(*args, **kwargs)
        self.stages = [Stage('detect', depends=['exposure', 'psf'], always=True),
                       Stage('measure', depends=['exposure', 'sources', 'psf'], always=True),
                       ]
        return

    def _detect(self, exposure=None, psf=None, threshold=None, **kwargs):
        """Detect sources

        @param exposure Exposure to process
        @param psf PSF for detection
        @param threshold Detection threshold
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        policy = self.config['detect']
        if threshold is not None:
            oldThreshold = policy['thresholdValue']
            policy['thresholdValue'] = threshold
        posSources, negSources = muDetection.detectSources(exposure, psf, policy.getPolicy())
        numPos = len(posSources.getFootprints()) if posSources is not None else 0
        numNeg = len(negSources.getFootprints()) if negSources is not None else 0
        if numNeg > 0:
            self.log.log(self.log.WARN, "%d negative sources found and ignored" % numNeg)
        self.log.log(self.log.INFO, "Detected %d sources to %f." % (numPos, policy['thresholdValue']))
        if threshold is not None:
            policy['thresholdValue'] = oldThreshold
        return {'sources': posSources}

    def _measure(self, exposure=None, sources=None, psf=None, wcs=None, apcorr=None, **kwargs):
        """Measure sources

        @param exposure Exposure to process
        @param sources Sources to measure
        @param psf PSF for measurement
        @param wcs WCS to apply
        @param apcorr Aperture correction to apply
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        assert psf, "No psf provided"
        policy = self.config['measure'].getPolicy()
        footprints = []                    # Footprints to measure
        num = len(sources.getFootprints())
        self.log.log(self.log.INFO, "Measuring %d positive sources" % num)
        footprints.append([sources.getFootprints(), False])
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

        return {'sources': sources}
