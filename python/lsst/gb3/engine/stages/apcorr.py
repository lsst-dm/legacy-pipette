#!/usr/bin/env python

import lsst.sdqa as sdqa
import lsst.meas.algorithms.ApertureCorrection as maApCorr
from lsst.gb3.engine.stage import BaseStage

class Apcorr(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Apcorr, self).__init__(requires=['exposure', 'cells'], provides=['apcorr'], *args, **kwargs)
        return

    def run(self, exposure=None, cells=None, **kwargs):
        """Measure aperture correction

        @param exposure Exposure to process
        @param cells cellSet of PSF stars
        """
        assert exposure, "No exposure provided"
        policy = self.config['apcorr'].getPolicy()
        control = maApCorr.ApertureCorrectionControl(policy)
        sdqaRatings = sdqa.SdqaRatingSet()
        corr = maApCorr.ApertureCorrection(exposure, cells, sdqaRatings, control, self.log)
        sdqaRatings = dict(zip([r.getName() for r in sdqaRatings], [r for r in sdqaRatings]))
        x, y = exposure.getWidth() / 2.0, exposure.getHeight() / 2.0
        value, error = corr.computeAt(x, y)
        self.log.log(self.log.INFO, "Aperture correction using %d/%d stars: %f +/- %f" %
                     (sdqaRatings["phot.apCorr.numAvailStars"].getValue(),
                      sdqaRatings["phot.apCorr.numGoodStars"].getValue(),
                      value, error))
        return {'apcorr': corr}
