#!/usr/bin/env python

import lsst.meas.utils.sourceDetection as muDetection
from lsst.gb3.engine.stage import BaseStage

class Detect(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Detect, self).__init__(requires=['exposure', 'psf'], provides='sources', *args, **kwargs)
        return
    
    def run(self, exposure=None, psf=None, threshold=None, **kwargs):
        """Detect sources

        @param exposure Exposure to process
        @param psf PSF for detection
        @param threshold Detection threshold
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        policy = self.config['detect']
        if threshold is not None:
            oldThreshold = policy['thresholdValue']
            policy['thresholdValue'] = threshold
        posSources, negSources = muDetection.detectSources(exposure, psf, policy.getPolicy())
        numPos = len(posSources.getFootprints()) if posSources is not None else 0
        numNeg = len(negSources.getFootprints()) if negSources is not None else 0
        if numNeg > 0:
            self.log.log(self.log.WARN, "%d negative sources found and ignored" % numNeg)
        self.log.log(self.log.INFO, "Detected %d sources to %f." % (numPos, policy['thresholdValue']))
        if threshold is not None:
            policy['thresholdValue'] = oldThreshold
        return {'sources': posSources}
