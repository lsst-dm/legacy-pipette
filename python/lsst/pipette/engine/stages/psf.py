#!/usr/bin/env python

import lsst.sdqa as sdqa
import lsst.meas.algorithms.psfSelectionRhl as maPsfSel
import lsst.meas.algorithms.psfAlgorithmRhl as maPsfAlg
from lsst.pipette.engine.stage import BaseStage

class Psf(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Psf, self).__init__(requires=['exposure', 'sources'], provides=['psf', 'cells'],
                                  *args, **kwargs)
        return

    def run(self, exposure=None, sources=None, **kwargs):
        """Measure the PSF

        @param exposure Exposure to process
        @param sources Measured sources on exposure
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        psfPolicy = self.config['psf']
        selPolicy = psfPolicy['select'].getPolicy()
        algPolicy = psfPolicy['algorithm'].getPolicy()
        sdqaRatings = sdqa.SdqaRatingSet()
        self.log.log(self.log.INFO, "Measuring PSF")
        psfStars, cellSet = maPsfSel.selectPsfSources(exposure, sources, selPolicy)
        psf, cellSet, psfStars = maPsfAlg.getPsf(exposure, psfStars, cellSet, algPolicy, sdqaRatings)
        return {'psf': psf,
                'cells': cellSet
                }
