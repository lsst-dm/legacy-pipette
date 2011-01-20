#!/usr/bin/env python

import lsst.pipette.process as pipProc
import lsst.pipette.isr as isrProc
import lsst.pipette.bootstrap as bsProc
import lsst.pipette.char as charProc

class Ccd(pipProc.Process):
    def __init__(self, Isr=None):
        self.Isr = isrProc.isr
        
    def run(self, exposureList, detrendsList=None):
        """Process a CCD.

        @param exposureList List of exposures (each is an amp from the same exposure)
        @param detrendsList List of detrend dicts (each for an amp in the CCD; with bias, dark, flat, fringe)
        @return Exposure, PSF, Aperture correction, Sources, Matched sources
        """
        assert exposureList and len(exposureList) > 0, "exposureList not provided"

        exposure = self.isr(exposureList, detrends)

        exposure, defects, psf, apcorr = bsProc.Bootstrap(config=self.config, log=self.log).run(exposureList)

        sources, matches = charProc.Char(config=self.config, log=self.log).run(exposure, psf, apcorr, defects)

        return exposure, psf, apcorr, sources, matches
            
    def isr(self, exposureList, detrends):
        for index, exp in enumerate(exposureList):
            detrends = detrendsList[index] if detrendsList else None
            self.isr(exp, detrends)

        isr = self.Isr(config=self.config, log=self.log)
        return isr.run(exp, detrends)
