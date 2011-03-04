#!/usr/bin/env python

import lsst.ip.isr as ipIsr
import lsst.meas.algorithms as measAlg

import lsst.pipette.process as pipProcess
import lsst.pipette.phot as pipPhot
import lsst.pipette.calibrate as pipCalibrate

class MultiPhot(pipProcess.Process):
    """Matched photometry on multiple exposures"""
    def __init__(self, Phot=pipPhot.Photometry, Calibrate=pipCalibrate.Calibrate, **kwargs):
        super(MultiPhot, self).__init__(**kwargs)
        self._Phot = Phot(**kwargs)
        self._Calibrate = Calibrate(**kwargs)
    
    def run(self, refExposure, exposureList):
        """Perform matched photometry on multiple exposures

        @param refExposure Reference exposure (for detection)
        @param exposureList List of exposures (for measurements)
        @return List of sourceSet
        """
        assert refExposure, "refExposure not provided"
        assert exposureList and len(exposureList) > 0, "exposureList not provided"
        
        refPsf, refApcorr = self.psf(refExposure)
        footprintSet = self.detect(refExposure, refPsf)
        sourceList = list()
        for exp in exposureList:
            self.display("isr", exposure=exp)
            exp.writeFits("test.fits")

            psf, apcorr = self.psf(exp)
            wcs = exp.getWcs()
            # Assumptions:
            # * Measurement uses the positions provided without tweaking
            # * Measurement creates sources for all footprints in order
            # These assumptions seem to be met at the moment...
            sources = self.measure(exp, footprintSet, psf, apcorr=apcorr, wcs=wcs)
            sourceList.append(sources)

        return sourceList

    def psf(self, exposure):
        psf, wcs = self._Calibrate.fakePsf(exposure)

        # Need to clobber NANs...
        # XXX Use a Pipette process for this
        exposure.getMaskedImage().getMask().addMaskPlane("UNMASKEDNAN")
        nanMasker = ipIsr.UnmaskedNanCounterF()
        nanMasker.apply(exposure.getMaskedImage())
        nans = ipIsr.defectListFromMask(exposure, maskName='UNMASKEDNAN')
        measAlg.interpolateOverDefects(exposure.getMaskedImage(), psf, nans, 0.0)
        
        sources = self._Calibrate.phot(exposure, psf)
        psf, cellSet = self._Calibrate.psf(exposure, sources)
        apcorr = self._Calibrate.apCorr(exposure, cellSet)
        return psf, apcorr
        
    def detect(self, exposure, psf):
        return self._Phot.detect(exposure, psf)


    def measure(self, exposure, footprintSet, psf, apcorr=None, wcs=None):
        return self._Phot.measure(exposure, footprintSet, psf, apcorr=apcorr, wcs=wcs)
