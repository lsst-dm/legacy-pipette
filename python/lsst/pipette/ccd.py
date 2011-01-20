#!/usr/bin/env python

import lsst.pipette.process as pipProc
import lsst.pipette.isr as isrProc
import lsst.pipette.bootstrap as bsProc
import lsst.pipette.char as charProc

class Ccd(pipProc.Process):
    def __init__(self, Isr=isrProc.Isr, Bootstrap=bsProc.Bootstrap, Char=charProc.Char, *args, **kwargs):
        """Initialise

        @param Isr Process to do ISR
        @param Bootstrap Process to do Bootstrap
        @param Char Process to do Char
        """
        super(Ccd, self).__init__(*args, **kwargs)
        self._Isr = Isr
        self._Bootstrap = Bootstrap
        self._Char = Char
        
        
    def run(self, exposureList, detrendsList=None):
        """Process a CCD.

        @param exposureList List of exposures (each is an amp from the same exposure)
        @param detrendsList List of detrend dicts (each for an amp in the CCD; with bias, dark, flat, fringe)
        @return Exposure, PSF, Aperture correction, Sources, Matched sources
        """
        assert exposureList and len(exposureList) > 0, "exposureList not provided"

        self.isr(exposureList, detrendsList)

        exposure, defects, psf, apcorr = self.bootstrap(exposureList)

        sources, matches = self.char(exposure, psf, apcorr, defects)

        return exposure, psf, apcorr, sources, matches
            
    def isr(self, exposureList, detrendsList):
        """Perform Instrumental Signature Removal

        @param exposureList List of exposures (each is an amp from the same exposure)
        @param detrendsList List of detrend dicts (each for an amp in the CCD; with bias, dark, flat, fringe)
        """
        isr = self._Isr(config=self.config, log=self.log)
        for index, exp in enumerate(exposureList):
            detrends = detrendsList[index] if detrendsList else None
            isr.run(exp, detrends)

    def bootstrap(self, exposureList):
        bootstrap = self._Bootstrap(config=self.config, log=self.log)
        return bootstrap.run(exposureList)

    def char(self, exposure, psf, apcorr, defects):
        char = self._Char(config=self.config, log=self.log)
        return char.run(exposure, psf, apcorr, defects)
