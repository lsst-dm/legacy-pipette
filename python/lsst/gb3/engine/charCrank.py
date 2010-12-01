#!/usr/bin/env python

import os

import lsst.afw.detection as afwDet
import lsst.afw.geom as afwGeom
import lsst.afw.math as afwMath
import lsst.meas.utils.sourceDetection as muDetection
import lsst.meas.utils.sourceMeasurement as muMeasurement
import lsst.meas.algorithms as measAlg
import lsst.meas.astrom as measAst
import lsst.meas.astrom.net as astromNet
import lsst.meas.astrom.sip as astromSip
import lsst.meas.astrom.verifyWcs as astromVerify
import lsst.meas.photocal as photocal

import lsst.gb3.engine.util as engUtil
import lsst.gb3.engine.distortion as engDist
import lsst.gb3.engine.crank as engCrank
from lsst.gb3.engine.photCrank import PhotCrank
from lsst.gb3.engine.stage import Stage

class CharCrank(engCrank.Crank):
    def __init__(self, name=None, config=None, *args, **kwargs):
        super(CharCrank, self).__init__(name=name, config=config, *args, **kwargs)
        self.stages = [Stage('interpolate', depends=['exposure', 'defects', 'psf']),
                       Stage('cr', depends=['exposure', 'psf']),
                       Stage('phot', depends=['exposure', 'psf'], crank=PhotCrank(config=config)),
                       Stage('distortion', depends=['exposure']),
                       Stage('ast', depends=['exposure', 'sources']),
                       Stage('cal', depends=['exposure', 'matches']),
                       ]
        return

    def _interpolate(self, exposure=None, defects=None, psf=None, **kwargs):
        """Interpolate over defects

        @param exposure Exposure to process
        @param defects Defect list
        @param psf PSF for interpolation
        """
        assert exposure, "No exposure provided"
        assert defects, "No defects provided"
        assert psf, "No psf provided"
        mi = exposure.getMaskedImage()
        fallbackValue = afwMath.makeStatistics(mi.getImage(), afwMath.MEANCLIP).getValue()
        measAlg.interpolateOverDefects(mi, psf, defects, fallbackValue)
        self.log.log(self.log.INFO, "Interpolated over %d defects." % len(defects))
        return

    def _cr(self, exposure=None, psf=None, keepCRs=False, **kwargs):
        """Cosmic ray masking

        @param exposure Exposure to process
        @param psf PSF
        @param keepCRs Keep CRs on image?
        """
        assert exposure, "No exposure provided"
        assert psf, "No psf provided"
        # Blow away old mask
        try:
            mask = bgSubExp.getMaskedImage().getMask()
            crBit = mask.getMaskPlane("CR")
            mask.clearMaskPlane(crBit)
        except: pass
        
        policy = self.config['cr'].getPolicy()
        mi = exposure.getMaskedImage()
        bg = afwMath.makeStatistics(mi, afwMath.MEDIAN).getValue()
        crs = measAlg.findCosmicRays(mi, psf, bg, policy, keepCRs)
        num = 0
        if crs is not None:
            mask = mi.getMask()
            crBit = mask.getPlaneBitMask("CR")
            afwDet.setMaskFromFootprintList(mask, crs, crBit)
            num = len(crs)
        self.log.log(self.log.INFO, "Identified %d cosmic rays." % num)
        return


    def _distortion(self, exposure=None, **kwargs):
        """Generate appropriate optical distortion

        @param exposure Exposure from which to get CCD
        """
        assert exposure, "No exposure provided"
        ccd = engUtil.getCcd(exposure)
        dist = engDist.createDistortion(ccd, self.config['distortion'])
        return {'distortion': dist}

    def _ast(self, exposure=None, sources=None, distortion=None, **kwargs):
        """Solve WCS

        @param exposure Exposure to process
        @param sources Sources with undistorted (actual) positions
        @param distortion Distortion to apply
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        
        policy = self.config['ast']
        path=os.path.join(os.environ['ASTROMETRY_NET_DATA_DIR'], "metadata.paf")
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
            for source in distSources:
                x, y = source.getXAstrom(), source.getYAstrom()
                source.setXAstrom(x - xMin)
                source.setYAstrom(y - yMin)

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
        return {'matches': matches,
                'wcs': wcs
                }

    def _cal(self, exposure=None, matches=None, **kwargs):
        """Photometry calibration

        @param exposure Exposure to process
        @param matches Matched sources
        """
        assert exposure, "No exposure provided"
        assert matches, "No matches provided"
        
        zp = photocal.calcPhotoCal(matches, log=self.log, goodFlagValue=0)
        self.log.log(self.log.INFO, "Photometric zero-point: %f" % zp.getMag(1.0))
        exposure.getCalib().setFluxMag0(zp.getFlux(0))
        return

