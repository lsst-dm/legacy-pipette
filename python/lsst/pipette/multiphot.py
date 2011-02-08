#!/usr/bin/env python

import lsst.pipette.process as pipProcess
import lsst.pipette.phot as pipPhot
import lsst.pipette.bootstrap as pipBootstrap

class MultiPhot(pipProcess.Process):
    """Matched photometry on multiple exposures"""
    def __init__(self, Phot=pipPhot.Phot, Bootstrap=pipBootstrap.Bootstrap, **kwargs):
        super(MultiPhot, self).__init__(**kwargs)
        self._Phot = Phot(**kwargs)
        self._Bootstrap = Bootstrap(**kwargs)
    
    def run(self, refExposure, exposureList):
        """Perform matched photometry on multiple exposures

        @param refExposure Reference exposure (for detection)
        @param exposureList List of exposures (for measurements)
        @return List of sourceSet
        """
        assert refExposure, "refExposure not provided"
        assert exposureList and len(exposureList) > 0, "exposureList not provided"
        
        refPsf, refApcorr = self.psf(refExposure)
        footprintSet = self.detect(refExposure, refPsf, apcorr=refApcorr)
        sourceList = list()
        for exp in exposureList:
            psf, apcorr = self.psf(exp)
            wcs = exp.getWcs()
            # Assumptions:
            # * Measurement uses the positions provided without tweaking
            # * Measurement creates sources for all footprints in order
            sources = self.measure(exp, footprintSet, psf, apcorr=apcorr, wcs=wcs)
            sourceList.append(sources)

        return sourceList

    def psf(self, exposure):
        psf, wcs = self._Bootstrap.fakePsf(exposure)
        sources = self._Bootstrap.phot(exposure, psf, wcs=wcs)
        psf, cellSet = self._Bootstrap.psf(exposure, sources)
        apcorr = self._Bootstrap.apCorr(exposure, cellSet)
        return psf, apcorr
        
    def detect(self, exposure, psf):
        return self._Phot.detect(exposure, psf)


    def measure(self, exposure, footprintSet, psf, apcorr=None, wcs=None):
        return self._Phot.measure(exposure, footprintSet, psf, apcorr=apcorr, wcs=wcs)
