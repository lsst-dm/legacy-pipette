#!/usr/bin/env python

import math
import lsst.afw.detection as afwDet
import lsst.meas.algorithms.psfSelectionRhl as maPsfSel
import lsst.meas.algorithms.psfAlgorithmRhl as maPsfAlg
import lsst.meas.algorithms.ApertureCorrection as maApCorr
import lsst.sdqa as sdqa

from lsst.pipette.engine.charCrank import CharCrank
from lsst.pipette.engine.photCrank import PhotCrank
from lsst.pipette.engine.stage import Stage

class BootstrapPhotCrank(PhotCrank):
    def _detect(self, **kwargs):
        bootstrap = self.config['bootstrap']
        return super(BootstrapPhotCrank, self)._detect(threshold=bootstrap['thresholdValue'], **kwargs)


class BootstrapCrank(CharCrank):
    def __init__(self, name=None, config=None, *args, **kwargs):
        super(BootstrapCrank, self).__init__(name=name, config=config, *args, **kwargs)
        bsStages = [Stage('init', depends='exposure', always=True),
                    ]
        # Propagate inherited definitions
        for stage in self.stages:
            if stage.name in ['defects', 'interpolate', 'cr']:
                bsStages.append(stage)
            if stage.name == 'phot':
                bsStages.append(Stage('phot', depends=stage.depends, always=True,
                                      crank=BootstrapPhotCrank(name=name, config=config)))
        bsStages.append(Stage('psf', depends=['exposure', 'sources'], always=True))
        bsStages.append(Stage('apcorr', depends=['exposure', 'cells'], always=True))
        self.stages = bsStages
        return


    def _init(self, exposure=None, wcs=None, **kwargs):
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

    def _cr(self, **kwargs):
        return super(BootstrapCrank, self)._cr(keepCRs=True, **kwargs)


    def _psf(self, exposure=None, sources=None, **kwargs):
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

    def _apcorr(self, exposure=None, cells=None, **kwargs):
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
