#!/usr/bin/env python

import os
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

        pipFix.Fix(config=self.config, log=self.log, keepCRs=False).run(exposure, psf, defects=defects)
        if do['phot']:
            phot = pipPhot.Phot(config=self.config, log=self.log)
            sources = phot.run(exposure, psf, apcorr=apcorr, wcs=wcs)
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
        
        policy = self.config['ast']
        path = os.path.join(os.environ['ASTROMETRY_NET_DATA_DIR'], "metadata.paf")
        solver = astromNet.GlobalAstrometrySolution(path)
        #solver.allowDistortion(self.policy.get('allowDistortion'))
        self.log.log(self.log.INFO, "Solving astrometry")

        try:
            menu = self.config['filters']
            filterName = menu[exposure.getFilter().getName()]
        except:
            self.log.log(self.log.WARN, "Unable to determine catalog filter from lookup table using %s" %
                         exposure.getFilter().getName())
            filterName = policy['defaultFilterName']
        self.log.log(self.log.INFO, "Using catalog filter: %s" % filterName)

        if distortion is not None:
            self.log.log(self.log.INFO, "Applying distortion correction.")
            distSources = distortion.actualToIdeal(sources)

            # Get distorted image size, and remove offset
            xMin, xMax, yMin, yMax = 0, exposure.getWidth(), 0, exposure.getHeight()
            for x, y in ((0.0, 0.0), (0.0, exposure.getHeight()), (exposure.getWidth(), 0.0),
                         (exposure.getHeight(), exposure.getWidth())):
                point = afwGeom.makePointD(x, y)
                x, y = point.getX(), point.getY()
                if x < xMin: xMin = x
                if x > xMax: xMax = x
                if y < yMin: yMin = y
                if y > yMax: yMax = y
            xMin = int(xMin)
            yMin = int(yMin)
            offsetSources(distSources, -xMin, -yMin)
            size = afwGeom.makePointI(int(xMax - xMin + 0.5), int(yMax - yMin + 0.5))
        else:
            distSources = sources
            size = afwGeom.makePointI(exposure.getWidth(), exposure.getHeight())

        if True:
            solver.setMatchThreshold(policy['matchThreshold'])
            solver.setStarlist(distSources)
            solver.setNumBrightObjects(min(policy['numBrightStars'], len(distSources)))
            solver.setImageSize(size.getX(), size.getY())
            if not solver.solve(exposure.getWcs()):
                raise RuntimeError("Unable to solve astrometry")
            wcs = solver.getWcs()
            matches = solver.getMatchedSources(filterName)
            sipFitter = astromSip.CreateWcsWithSip(matches, wcs, policy['sipOrder'])
            wcs = sipFitter.getNewWcs()
            scatter = sipFitter.getScatterInArcsec()
            self.log.log(self.log.INFO, "Astrometric scatter: %f" % scatter)
        else:
            matches, wcs = measAst.determineWcs(policy.getPolicy(), exposure, distSources,
                                                solver=solver, log=self.log)
            if matches is not None or len(matches) == 0:
                raise RuntimeError("Unable to find any matches")

        exposure.setWcs(wcs)
        for index, source in enumerate(sources):
            distSource = distSources[index]
            sky = wcs.pixelToSky(distSource.getXAstrom(), distSource.getYAstrom())
            source.setRa(sky[0])
            source.setDec(sky[1])


        verify = dict()                    # Verification parameters
        verify.update(astromSip.sourceMatchStatistics(matches))
        verify.update(astromVerify.checkMatches(matches, exposure, self.log))
        for k, v in verify.items():
            exposure.getMetadata().set(k, v)

        if distortion is not None:
            # Undo distortion in matches
            self.log.log(self.log.INFO, "Removing distortion correction.")
            first = map(lambda match: match.first, matches)
            second = map(lambda match: match.second, matches)
            offsetSources(first, xMin, yMin)
            offsetSources(second, xMin, yMin)
            distortion.idealToActual(first, copy=False)
            distortion.idealToActual(second, copy=False)

        return matches, wcs

    def cal(self, exposure, matches):
        """Photometric calibration

        @param exposure Exposure to process
        @param matches Matched sources
        """
        assert exposure, "No exposure provided"
        assert matches, "No matches provided"
        
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

