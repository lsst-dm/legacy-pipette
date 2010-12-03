#!/usr/bin/env python

import lsst.meas.utils.sourceDetection as muDetection
from lsst.gb3.engine.stage import BaseStage

class Background(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Background, self).__init__(requires='exposure', provides=['background', 'exposure'],
                                         *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Background subtraction

        @param exposure Exposure to process
        """
        policy = self.config['background'].getPolicy()
        bg, subtracted = muDetection.estimateBackground(exposure, policy, subtract=True)
        return {'background': bg,
                'exposure': subtracted}
