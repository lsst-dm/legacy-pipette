#!/usr/bin/env python

import lsst.afw.math as afwMath
import lsst.meas.algorithms as measAlg
from lsst.pipette.engine.stage import BaseStage

class Interpolate(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Interpolate, self).__init__(requires=['exposure', 'defects', 'psf'], *args, **kwargs)
        return

    def run(self, exposure=None, defects=None, psf=None, **kwargs):
        """Interpolate over defects

        @param exposure Exposure to process
        @param defects Defect list
        @param psf PSF for interpolation
        """
        assert exposure, "No exposure provided"
        assert defects, "No defects provided"
        assert psf, "No psf provided"
        mi = exposure.getMaskedImage()
        fallbackValue = afwMath.makeStatistics(mi.getImage(), afwMath.MEANCLIP).getValue()
        measAlg.interpolateOverDefects(mi, psf, defects, fallbackValue)
        self.log.log(self.log.INFO, "Interpolated over %d defects." % len(defects))
        return
