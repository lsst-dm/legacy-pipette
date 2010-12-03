#!/usr/bin/env python

import math
import lsst.meas.utils.sourceMeasurement as muMeasurement
from lsst.gb3.engine.stage import BaseStage

class Measure(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Measure, self).__init__(requires=['exposure', 'sources', 'psf'], provides='sources',
                                      *args, **kwargs)
        return
    
    def run(self, exposure=None, sources=None, psf=None, wcs=None, apcorr=None, **kwargs):
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
