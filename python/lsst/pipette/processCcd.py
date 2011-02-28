#!/usr/bin/env python

import lsst.pipette.process as pipProc
import lsst.pipette.isr as pipIsr
import lsst.pipette.calibrate as pipCalib
import lsst.pipette.phot as pipPhot

class ProcessCcd(pipProc.Process):
    def __init__(self, Isr=pipIsr.Isr, Calibrate=pipCalib.Calibrate, Photometry=pipPhot.Photometry,
                 *args, **kwargs):
        """Initialise

        @param Isr Process to do ISR
        @param Calibrate Process to do calibration
        @param Photometry Process to do photometry
        """
        super(ProcessCcd, self).__init__(*args, **kwargs)
        self._Isr = Isr
        self._Calibrate = Calibrate
        self._Photometry = Photometry
        
        
    def run(self, exposureList, detrendsList=None):
        """Process a CCD.

        @param exposureList List of exposures (each is an amp from the same exposure)
        @param detrendsList List of detrend dicts (each for an amp in the CCD; with bias, dark, flat, fringe)
        @return Exposure, PSF, Aperture correction, Sources, Matched sources
        """
        assert exposureList and len(exposureList) > 0, "exposureList not provided"

        exposure, defects, background = self.isr(exposureList, detrendsList)

        psf, apcorr, sources, matches, matchMeta = self.calibrate(exposure, defects=defects)

        if self.config['do']['phot']:
            sources, footprints = self.phot(exposure, psf, apcorr, wcs=exposure.getWcs())
        else:
            sources, footprints = None, None

        return exposure, psf, apcorr, sources, matches, matchMeta
            
    def isr(self, exposureList, detrendsList):
        """Perform Instrumental Signature Removal

        @param exposureList List of exposures (each is an amp from the same exposure)
        @param detrendsList List of detrend dicts (each for an amp in the CCD; with bias, dark, flat, fringe)
        """
        isr = self._Isr(config=self.config, log=self.log)
        return isr.run(exposureList, detrendsList)

    def calibrate(self, *args, **kwargs):
        calibrate = self._Calibrate(config=self.config, log=self.log)
        return calibrate.run(*args, **kwargs)

    def phot(self, exposure, psf, apcorr, wcs=None):
        phot = self._Photometry(config=self.config, log=self.log)
        return phot.run(exposure, psf, apcorr, wcs=wcs)
