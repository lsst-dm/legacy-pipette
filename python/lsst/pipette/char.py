#!/usr/bin/env python

import os
import lsst.pex.logging as pexLog
import lsst.afw.geom as afwGeom
import lsst.meas.astrom as measAst
import lsst.meas.astrom.net as astromNet
import lsst.meas.astrom.sip as astromSip
import lsst.meas.astrom.verifyWcs as astromVerify
import lsst.meas.photocal as photocal
import lsst.pipette.util as pipUtil
import lsst.pipette.distortion as pipDist
import lsst.pipette.process as pipProc
import lsst.pipette.phot as pipPhot
import lsst.pipette.fix as pipFix

class Char(pipProc.Process):
    def __init__(self, Fix=pipFix.Fix, Phot=pipPhot.Phot, *args, **kwargs):
        super(Char, self).__init__(*args, **kwargs)
        self._Fix = Fix
        self._Phot = Phot
        
    
    def run(self, exposure, psf, apcorr, defects=None, wcs=None):
        """Characterise an exposure: photometry and astrometry

        @param exposure Exposure to process
        @param psf Point spread function
        @param apcorr Aperture correction
        @param defects Defects to interpolate, or None
        @param wcs World Coordinate System, or None
        @return Sources, Source Matches
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        assert apcorr, "No apcorr provided"

        do = self.config['do']

        self.fix(exposure, psf, defects=defects)

        if do['phot']:
            sources = self.phot(exposure, psf, apcorr=apcorr, wcs=wcs)
        else:
            sources = None

        if do['distortion']:
            dist = self.distortion(exposure)
        else:
            dist = None

        if do['ast'] and sources is not None:
            matches, wcs = self.ast(exposure, sources, distortion=dist)
        else:
            matches, wcs = None, None

        if do['cal'] and matches is not None:
            self.cal(exposure, matches)

        self.display('char', exposure=exposure, sources=sources, matches=matches)
        return sources, matches

    def fix(self, exposure, psf, defects=None):
        """Fix instrumental problems (defects, CRs)

        @param exposure Exposure to process
        @param psf Point spread function
        @param defects Defect list, or None
        """
        fix = self._Fix(config=self.config, log=self.log, keepCRs=False)
        fix.run(exposure, psf, defects=defects)

    def phot(self, exposure, psf, apcorr=None, wcs=None):
        """Perform photometry

        @param exposure Exposure to process
        @param psf Point spread function
        @param apcorr Aperture correction
        @param wcs World Coordinage System
        @return Source list
        """
        phot = self._Phot(config=self.config, log=self.log)
        return phot.run(exposure, psf, apcorr=apcorr, wcs=wcs)

    def distortion(self, exposure):
        """Generate appropriate optical distortion

        @param exposure Exposure from which to get CCD
        @return Distortion
        """
        assert exposure, "No exposure provided"
        ccd = pipUtil.getCcd(exposure)
        dist = pipDist.createDistortion(ccd, self.config['distortion'])
        return dist

    def ast(self, exposure, sources, distortion=None):
        """Solve astrometry to produce WCS

        @param exposure Exposure to process
        @param sources Sources with undistorted (actual) positions
        @param distortion Distortion to apply
        @return Star matches, World Coordinate System
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        
        self.log.log(self.log.INFO, "Solving astrometry")

        try:
            menu = self.config['filters']
            filterName = menu[exposure.getFilter().getName()]
            self.log.log(self.log.INFO, "Using catalog filter: %s" % filterName)
        except:
            self.log.log(self.log.WARN, "Unable to determine catalog filter from lookup table using %s" %
                         exposure.getFilter().getName())
            filterName = None

        if distortion is not None:
            self.log.log(self.log.INFO, "Applying distortion correction.")
            distSources = distortion.actualToIdeal(sources)

            # Get distorted image size, and remove offset
            xMin, xMax, yMin, yMax = 0, exposure.getWidth(), 0, exposure.getHeight()
            for x, y in ((0.0, 0.0), (0.0, exposure.getHeight()), (exposure.getWidth(), 0.0),
                         (exposure.getWidth(), exposure.getHeight())):
                point = afwGeom.makePointD(x, y)
                point = distortion.actualToIdeal(point)
                x, y = point.getX(), point.getY()
                if x < xMin: xMin = x
                if x > xMax: xMax = x
                if y < yMin: yMin = y
                if y > yMax: yMax = y
            xMin = int(xMin)
            yMin = int(yMin)
            offsetSources(distSources, -xMin, -yMin)
            size = (int(xMax - xMin + 0.5), int(yMax - yMin + 0.5))
        else:
            distSources = sources
            size = (exposure.getWidth(), exposure.getHeight())

        log = pexLog.Log(self.log, "ast")
        astrom = measAst.determineWcs(self.config['ast'].getPolicy(), exposure, distSources,
                                      log=log, forceImageSize=size, filterName=filterName)
        if astrom is None:
            raise RuntimeError("Unable to solve astrometry")
        wcs = astrom.wcs
        matches = astrom.matches
        if matches is None or len(matches) == 0:
            raise RuntimeError("No astrometric matches")
        self.log.log(self.log.INFO, "%d astrometric matches" % len(matches))

        # Apply WCS to sources
        for index, source in enumerate(sources):
            distSource = distSources[index]
            sky = wcs.pixelToSky(distSource.getXAstrom(), distSource.getYAstrom())
            source.setRa(sky[0])
            source.setDec(sky[1])

        # Undo distortion in matches
        if distortion is not None:
            self.log.log(self.log.INFO, "Removing distortion correction.")
            first = map(lambda match: match.first, matches)
            second = map(lambda match: match.second, matches)
            offsetSources(first, xMin, yMin)
            offsetSources(second, xMin, yMin)
            distortion.idealToActual(first, copy=False)
            distortion.idealToActual(second, copy=False)

        # Re-fit the WCS with the distortion undone
        if self.config['ast']['calculateSip']:
            sip = astromSip.CreateWcsWithSip(matches, wcs, self.config['ast']['sipOrder'])
            wcs = sip.getNewWcs()
            self.log.log(self.log.INFO, "Astrometric scatter: %f (%s non-linear terms)" %
                         (sip.getScatterInArcsec(), "with" if wcs.hasDistortion() else "without"))

        verify = dict()                    # Verification parameters
        verify.update(astromSip.sourceMatchStatistics(matches))
        verify.update(astromVerify.checkMatches(matches, exposure, log=log))
        for k, v in verify.items():
            exposure.getMetadata().set(k, v)

        exposure.setWcs(wcs)

        return matches, wcs

    def cal(self, exposure, matches):
        """Photometric calibration

        @param exposure Exposure to process
        @param matches Matched sources
        """
        assert exposure, "No exposure provided"
        assert matches, "No matches provided"

        print "Doing photocal"
        zp = photocal.calcPhotoCal(matches, log=self.log, goodFlagValue=0)
        self.log.log(self.log.INFO, "Photometric zero-point: %f" % zp.getMag(1.0))
        exposure.getCalib().setFluxMag0(zp.getFlux(0))
        return



def offsetSources(sources,              # List of sources to offset
                  dx,                   # x offset
                  dy,                   # y offset
                  ):
    for source in sources:
        x, y = source.getXAstrom(), source.getYAstrom()
        source.setXAstrom(x + dx)
        source.setYAstrom(y + dy)
    return

