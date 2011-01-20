#!/usr/bin/env python

import lsst.meas.utils.sourceDetection as muDetection
from lsst.pipette.stage import BaseStage

class Detect(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Detect, self).__init__(requires=['exposure', 'psf'], provides='sources', *args, **kwargs)
        self.threshold = None
        return
    
    def run(self, exposure=None, psf=None, **kwargs):
        """Detect sources

        @param exposure Exposure to process
        @param psf PSF for detection
        @param threshold Detection threshold
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        policy = self.config['detect']
        if self.threshold is not None:
            oldThreshold = policy['thresholdValue']
            policy['thresholdValue'] = self.threshold
        posSources, negSources = muDetection.detectSources(exposure, psf, policy.getPolicy())
        numPos = len(posSources.getFootprints()) if posSources is not None else 0
        numNeg = len(negSources.getFootprints()) if negSources is not None else 0
        if numNeg > 0:
            self.log.log(self.log.WARN, "%d negative sources found and ignored" % numNeg)
        self.log.log(self.log.INFO, "Detected %d sources to %f." % (numPos, policy['thresholdValue']))
        if self.threshold is not None:
            policy['thresholdValue'] = oldThreshold
        return {'sources': posSources}

class DetectBright(Detect):
    """Stage to detect sources using a different threshold than standard.
    This allows us to find bright sources for PSF estimation.
    """
    def __init__(self, *args, **kwargs):
        super(DetectBright, self).__init__(*args, **kwargs)
        self.threshold = self.config['bootstrap']['thresholdValue']
        return
    
