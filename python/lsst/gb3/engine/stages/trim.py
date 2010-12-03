#!/usr/bin/env python

import lsst.pipette.engine.util as engUtil
from lsst.pipette.engine.stage import BaseStage

class Trim(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Trim, self).__init__(requires='exposure', *args, **kwargs)
        return

    def run(self, exposure=None, **kwargs):
        """Trim overscan out of exposure

        @param exposure Exposure to process
        """
        assert exposure, "No exposure provided"
        mi = exposure.getMaskedImage()
        MaskedImage = type(mi)
        if engUtil.detectorIsCcd(exposure):
            # Effectively doing CCD assembly since we have all amplifiers
            ccd = engUtil.getCcd(exposure)
            miCcd = MaskedImage(ccd.getAllPixels(True).getDimensions())
            for amp in ccd:
                diskDataSec = amp.getDiskDataSec()
                trimDataSec = amp.getDataSec(True)
                miTrim = MaskedImage(mi, diskDataSec)
                miTrim = MaskedImage(amp.prepareAmpData(miTrim.getImage()),
                                     amp.prepareAmpData(miTrim.getMask()),
                                     amp.prepareAmpData(miTrim.getVariance()))
                miAmp = MaskedImage(miCcd, trimDataSec)
                self.log.log(self.log.INFO, "Trimming amp %s: %s --> %s" %
                             (amp.getId(), diskDataSec, trimDataSec))
                miAmp <<= miTrim
                amp.setTrimmed(True)
            exposure.setMaskedImage(miCcd)
        else:
            # AFW doesn't provide a useful target datasec, so we just make an image that has the useful pixels
            amp = cameraGeom.cast_Amp(exposure.getDetector())
            diskDataSec = amp.getDiskDataSec()
            self.log.log(self.log.INFO, "Trimming amp %s: %s" % (amp.getId(), diskDataSec))
            miAmp = MaskedImage(mi, diskDataSec)
            amp.setTrimmed(True)
            exposure.setMaskedImage(miAmp)
        return

    def _trimAmp(self, miTo, miFrom, amp, toDatasec):
        """Trim overscan from amplifier

        @param miTo Target MaskedImage
        @param miFrom Source MaskedImage
        @param amp Amplifier being trimmed
        @param toDatasec Data section on target
        """
        MaskedImage = type(miTo)
        fromDatasec = amp.getDiskDataSec()
        self.log.log(self.log.INFO, "Trimming amp %s: %s --> %s" % (amp.getId(), fromDatasec, toDatasec))
        trimAmp = amp.prepareAmpData(MaskedImage(miFrom, fromDatasec))
        trimImage = MaskedImage(miTo, toDatasec)
        trimImage <<= trimAmp
        amp.setTrimmed(True)
        return
