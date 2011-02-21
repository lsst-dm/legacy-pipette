#!/usr/bin/env python

import lsst.afw.image as afwImage
import lsst.pipette.isr as pipIsr
import lsst.pipette.util as pipUtil

class IsrSuprimeCam(pipIsr.Isr):
    def defects(self, exposure):
        """Mask defects and trim guider shadow

        @param exposure Exposure to process
        @return Defect list
        """
        assert exposure, "No exposure provided"

        defects = super(IsrSuprimeCam, self).defects(exposure)

        ccd = pipUtil.getCcd(exposure)
        ccdNum = ccd.getId().getSerial()
        if ccdNum not in [0, 1, 2, 6, 7]:
            # No need to mask
            return

        md = exposure.getMetadata()
        if not md.exists("S_AG-X"):
            self.log.log(self.log.WARN, "No autoguider position in exposure metadata.")
            return

        xGuider = md.get("S_AG-X")
        if ccdNum in [1, 2, 7]:
            maskLimit = int(60.0 * xGuider - 2300.0) # From SDFRED
        elif ccdNum in [0, 6]:
            maskLimit = int(60.0 * xGuider - 2000.0) # From SDFRED

        
        mi = exposure.getMaskedImage()
        height = mi.getHeight()
        if height < maskLimit:
            # Nothing to mask!
            return

        if False:
            # XXX This mask plane isn't respected by background subtraction or source detection or measurement
            self.log.log(self.log.INFO, "Masking autoguider shadow at y > %d" % maskLimit)
            mask = mi.getMask()
            bbox = afwImage.BBox(afwImage.PointI(0, maskLimit - 1),
                                 afwImage.PointI(mask.getWidth() - 1, height - 1))
            badMask = mask.Factory(mask, bbox)
            
            mask.addMaskPlane("GUIDER")
            badBitmask = mask.getPlaneBitMask("GUIDER")
            
            badMask |= badBitmask
        else:
            # XXX Temporary solution until a mask plane is respected by downstream processes
            self.log.log(self.log.INFO, "Removing pixels affected by autoguider shadow at y > %d" % maskLimit)
            bbox = afwImage.BBox(afwImage.PointI(0, 0), mi.getWidth(), maskLimit)
            good = mi.Factory(mi, bbox)
            exposure.setMaskedImage(good)

        return

class ProcessCcdSuprimeCam(pipProcCcd.ProcessCcd):
    def __init__(*args, **kwargs):
        super(ProcessCcdSuprimeCam, self).__init__(Isr=IsrSuprimeCam, *args, **kwargs)
    
