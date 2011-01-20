#!/usr/bin/env python

import lsst.meas.utils.sourceDetection as muDetection
import lsst.pipette.process as pipProc

class Background(pipProc.Process):
    def __init__(self, subtract=True, *args, **kwargs):
        super(Background, self).__init__(*args, **kwargs)
        self._subtract = subtract
        return

    def run(self, exposure):
        """Background subtraction

        @param exposure Exposure to process
        """
        policy = self.config['background'].getPolicy()
        bg, subtracted = muDetection.estimateBackground(exposure, policy, subtract=self._subtract)

        if not self._subtract:
            return bg

        self.display('background', exposure=subtracted)
        return bg, subtracted


class BackgroundMeasure(Background):
    def __init__(self, *args, **kwargs):
        super(BackgroundMeasure, self).__init__(subtract=False, *args, **kwargs)
        return

