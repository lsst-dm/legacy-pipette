#!/usr/bin/env python

import lsst.pipette.process as pipProcess
import lsst.pipette.phot as pipPhot

class MultiPhot(pipPhot.Phot):
    def run(self, refExposure, exposureList, apcorrList=None):

        assert refExposure, "refExposure not provided"
        assert exposureList and len(exposureList) > 0, "exposureList not provided"
        
        refPsf = refExposure.getPsf()
        footprintSet = self.detect(refExposure, refPsf)
        sourceList = list()
        for index, exp in enumerate(exposureList):
            apcorr = apcorrList[index] if apcorrList is not None else None
            psf = exp.getPsf()
            wcs = exp.getWcs()
            sources = self.measure(exp, footprintSet, psf, apcorr=apcorr, wcs=wcs)
            sourceList.append(sources)

        return sourceList
