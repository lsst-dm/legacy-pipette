#!/usr/bin/env python

import lsst.meas.utils.sourceDetection as muDetection
from lsst.pipette.stage import BaseStage

class Background(BaseStage):
    def __init__(self, name, requires='exposure', provides=['background', 'exposure'], *args, **kwargs):
        super(Background, self).__init__(name, requires=requires, provides=provides, *args, **kwargs)
        self.subtract = True;
        return

    def run(self, exposure=None, **kwargs):
        """Background subtraction

        @param exposure Exposure to process
        """
        policy = self.config['background'].getPolicy()
        bg, subtracted = muDetection.estimateBackground(exposure, policy, subtract=self.subtract)

        results = {'background': bg}
        if self.subtract:
            results['exposure'] = subtracted
        
        return results


class BackgroundMeasure(Background):
    def __init__(self, *args, **kwargs):
        super(BackgroundMeasure, self).__init__(requires='exposure', provides=['background'], *args, **kwargs)
        self.subtract = False;
        return

