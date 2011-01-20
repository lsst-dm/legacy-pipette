#!/usr/bin/env python

import math
import lsst.afw.detection as afwDet
from lsst.pipette.engine.stage import BaseStage

class FakePsf(BaseStage):
    def __init__(self, *args, **kwargs):
        super(FakePsf, self).__init__(requires='exposure', provides=['psf', 'wcs'], *args, **kwargs)
        return

    def run(self, exposure=None, wcs=None, **kwargs):
        """Initialise the bootstrap procedure by setting the PSF and WCS

        @param exposure Exposure to process
        @param wcs World coordinate system to use
        """
        assert exposure, "No exposure provided"
        if not wcs:
            wcs = exposure.getWcs()
        assert wcs, "No wcs provided"

        bootstrap = self.config['bootstrap']
        model = bootstrap['model']
        fwhm = bootstrap['fwhm'] / wcs.pixelScale()
        size = bootstrap['size']
        psf = afwDet.createPsf(model, size, size, fwhm/(2*math.sqrt(2*math.log(2))))
        return {'psf': psf,
                'wcs': wcs
                }
