#!/usr/bin/env python

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.pipette.isr as pipIsr
import lsst.pipette.calibrate as pipCalibrate
import lsst.pipette.util as pipUtil
import lsst.pipette.processCcd as pipProcCcd

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
            bbox = afwGeom.Box2I(afwGeom.Point2I(0, maskLimit - 1),
                                 afwGeom.Point2I(mask.getWidth() - 1, height - 1))
            badMask = mask.Factory(mask, bbox, afwImage.LOCAL)
            
            mask.addMaskPlane("GUIDER")
            badBitmask = mask.getPlaneBitMask("GUIDER")
            
            badMask |= badBitmask
        else:
            # XXX Temporary solution until a mask plane is respected by downstream processes
            self.log.log(self.log.INFO, "Removing pixels affected by autoguider shadow at y > %d" % maskLimit)
            bbox = afwGeom.Box2I(afwGeom.Point2I(0, 0), afwGeom.Extent2I(mi.getWidth(), maskLimit))
            good = mi.Factory(mi, bbox, afwImage.LOCAL)
            exposure.setMaskedImage(good)

        return


class CalibrateSuprimeCam(pipCalibrate.Calibrate):
    def astrometry(self, exposure, distSources, distortion=None, llc=(0,0), size=None):
        """Solve astrometry to produce WCS

        @param exposure Exposure to process
        @param distSources Sources with undistorted (actual) positions
        @param distortion Distortion model
        @param llc Lower left corner (minimum x,y)
        @param size Size of exposure
        @return Star matches, World Coordinate System
        """
        assert exposure, "No exposure provided"
        assert distSources, "No sources provided"

        self.log.log(self.log.INFO, "Solving astrometry")

        try:
            import hsc.meas.astrom as hscAst
        except:
            hscAst = None

        wcs = exposure.getWcs()
        if wcs is None or hscAst is None:
            self.log.log(self.log.WARN, "Unable to use hsc.meas.astrom; reverting to lsst.meas.astrom")
            return pipCalibrate.Calibrate.astrometry(self, exposure, distSources, distortion=distortion,
                                                     llc=llc, size=size)

        if size is None:
            size = (exposure.getWidth(), exposure.getHeight())

        try:
            menu = self.config['filters']
            filterName = menu[exposure.getFilter().getName()]
            self.log.log(self.log.INFO, "Using catalog filter: %s" % filterName)
        except:
            self.log.log(self.log.WARN, "Unable to determine catalog filter from lookup table using %s" %
                         exposure.getFilter().getName())
            filterName = None

        if distortion is not None:
            # Removed distortion, so use low order
            oldOrder = self.config['astrometry']['sipOrder']
            self.config['astrometry']['sipOrder'] = 2

        log = pexLog.Log(self.log, "astrometry")
        wcs.shiftReferencePixel(-llc[0], -llc[1])
        astrom = hscAst.determineWcs(self.config['astrometry'].getPolicy(), exposure, distSources,
                                     log=log, forceImageSize=size, filterName=filterName)
        wcs.shiftReferencePixel(llc[0], llc[1])
        
        if distortion is not None:
            self.config['astrometry']['sipOrder'] = oldOrder

        if astrom is None:
            raise RuntimeError("Unable to solve astrometry for %s", exposure.getDetector().getId())

        wcs = astrom.getWcs()
        matches = astrom.getMatches()
        matchMeta = astrom.getMatchMetadata()
        if matches is None or len(matches) == 0:
            raise RuntimeError("No astrometric matches for %s", exposure.getDetector().getId())
        self.log.log(self.log.INFO, "%d astrometric matches for %s" % \
                     (len(matches), exposure.getDetector().getId()))
        exposure.setWcs(wcs)

        # Apply WCS to sources
        for index, source in enumerate(sources):
            distSource = distSources[index]
            sky = wcs.pixelToSky(distSource.getXAstrom(), distSource.getYAstrom())
            source.setRaDec(sky)

        self.display('astrometry', exposure=exposure, sources=sources, matches=matches)

        return matches, matchMeta


class ProcessCcdSuprimeCam(pipProcCcd.ProcessCcd):
    def __init__(*args, **kwargs):
        super(ProcessCcdSuprimeCam, self).__init__(Isr=IsrSuprimeCam, Calibrate=CalibrateSuprimeCam,
                                                   *args, **kwargs)
    
