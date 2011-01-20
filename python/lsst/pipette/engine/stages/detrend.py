#!/usr/bin/env python

from lsst.pipette.engine.stage import BaseStage
from lsst.pipette.engine.stages.trim import Trim

class Detrend(BaseStage):
    """A base class for stages that apply a detrend image."""
    def __init__(self, *args, **kwargs):
        super(Detrend, self).__init__(requires=['exposure', 'detrends'], provides='exposure', *args, **kwargs)
        return

    def _checkDimensions(self, exposure, detrend):
        """Check that dimensions of detrend matches that of exposure
        of interest; trim if necessary.

        @param exposure Exposure being processed
        @param detrend Detrend exposure to check
        @returns Exposure with matching dimensions
        """
        if detrend.getMaskedImage().getDimensions() == exposure.getMaskedImage().getDimensions():
            return detrend
        self.log.log(self.log.INFO, "Trimming %s to match dimensions" % self.name)
        trim = Trim('detrend.trim', log=self.log)
        trim.run(exposure=detrend)
        if detrend.getMaskedImage().getDimensions() != exposure.getMaskedImage().getDimensions():
            raise RuntimeError("Detrend %s is of wrong size: %s vs %s" %
                               (self.name, detrend.getMaskedImage().getDimensions(),
                                exposure.getMaskedImage().getDimensions()))
        return detrend
