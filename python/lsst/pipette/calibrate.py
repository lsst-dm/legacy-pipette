#!/usr/bin/env python

import math

import lsst.pex.logging as pexLog
import lsst.afw.detection as afwDet
import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.sdqa as sdqa
import lsst.meas.algorithms as measAlg
import lsst.meas.algorithms.apertureCorrection as maApCorr
import lsst.meas.astrom as measAst
import lsst.meas.astrom.sip as astromSip
import lsst.meas.astrom.verifyWcs as astromVerify
import lsst.meas.photocal as photocal
import lsst.pipette.util as pipUtil
import lsst.pipette.process as pipProc
import lsst.pipette.repair as pipRepair
import lsst.pipette.phot as pipPhot
import lsst.pipette.background as pipBackground
import lsst.pipette.distortion as pipDist

from lsst.pipette.timer import timecall

class Calibrate(pipProc.Process):
    def __init__(self, Repair=pipRepair.Repair, Photometry=pipPhot.Photometry,
                 Background=pipBackground.Background, Rephotometry=pipPhot.Rephotometry,
                 *args, **kwargs):
        super(Calibrate, self).__init__(*args, **kwargs)
        self._Repair = Repair
        self._Photometry = Photometry
        self._Background = Background
        self._Rephotometry = Rephotometry

    def run(self, exposure, defects=None, background=None):
        """Calibrate an exposure: PSF, astrometry and photometry

        @param exposure Exposure to calibrate
        @param defects List of defects on exposure
        @param background Background model
        @return
        - psf: Point spread function
        - apcorr: Aperture correction
        - sources: Sources used in calibration
        - matches: Astrometric matches
        - matchMeta: Metadata for astrometric matches
        """
        assert exposure is not None, "No exposure provided"

        do = self.config['do']['calibrate']

        psf, wcs = self.fakePsf(exposure)

        self.repair(exposure, psf, defects=defects, preserve=True)

        if do['psf'] or do['astrometry'] or do['zeropoint']:
            sources, footprints = self.phot(exposure, psf)
        else:
            sources, footprints = None, None

        if do['psf']:
            psf, cellSet = self.psf(exposure, sources)
        else:
            psf, cellSet = None, None

        if do['psf'] and do['apcorr']:
            apcorr = self.apCorr(exposure, cellSet) # calculate the aperture correction; we may use it later
        else:
            apcorr = None

        # Wash, rinse, repeat with proper PSF

        if do['psf']:
            self.repair(exposure, psf, defects=defects, preserve=False)

        if do['background']:
            self.background(exposure, footprints=footprints, background=background)

        if do['psf'] and (do['astrometry'] or do['zeropoint']):
            newSources = self.rephot(exposure, footprints, psf, apcorr=apcorr)
            for old, new in zip(sources, newSources):
                if old.getFlagForDetection() & measAlg.Flags.STAR:
                    newFlag = new.getFlagForDetection() | measAlg.Flags.STAR
                    new.setFlagForDetection(newFlag)
            sources = newSources;  del newSources

        if do['distortion']:
            dist = self.distortion(exposure)
        else:
            dist = None

        if do['astrometry'] or do['zeropoint']:
            distSources, llc, size = self.distort(exposure, sources, distortion=dist)
            matches, matchMeta = self.astrometry(exposure, sources, distSources,
                                                 distortion=dist, llc=llc, size=size)
            self.undistort(exposure, sources, matches, distortion=dist)
            self.verifyAstrometry(exposure, matches)
        else:
            matches, matchMeta = None, None

        if do['zeropoint']:
            self.zeropoint(exposure, matches)

        self.display('calibrate', exposure=exposure, sources=sources, matches=matches)
        return psf, apcorr, sources, matches, matchMeta



    def fakePsf(self, exposure):
        """Initialise the calibration procedure by setting the PSF and WCS

        @param exposure Exposure to process
        @return PSF, WCS
        """
        assert exposure, "No exposure provided"
        
        wcs = exposure.getWcs()
        assert wcs, "No wcs in exposure"

        calibrate = self.config['calibrate']
        model = calibrate['model']
        fwhm = calibrate['fwhm'] / wcs.pixelScale()
        size = calibrate['size']
        psf = afwDet.createPsf(model, size, size, fwhm/(2*math.sqrt(2*math.log(2))))
        return psf, wcs


    @timecall
    def repair(self, exposure, psf, defects=None, preserve=False):
        """Repair CCD problems (defects, CRs)

        @param exposure Exposure to process
        @param psf Point Spread Function
        @param defects Defect list, or None
        @param preserve Preserve bad pixels?
        """
        repair = self._Repair(keepCRs=preserve, config=self.config, log=self.log)
        repair.run(exposure, psf, defects=defects)


    @timecall
    def phot(self, exposure, psf, apcorr=None):
        """Perform photometry

        @param exposure Exposure to process
        @param psf Point Spread Function
        @param apcorr Aperture correction, or None
        @param wcs World Coordinate System, or None
        @return Source list
        """
        threshold = self.config['calibrate']['thresholdValue']
        phot = self._Photometry(config=self.config, log=self.log, threshold=threshold)
        return phot.run(exposure, psf)


    @timecall
    def psf(self, exposure, sources):
        """Measure the PSF

        @param exposure Exposure to process
        @param sources Measured sources on exposure
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        psfPolicy = self.config['psf']
        selName   = psfPolicy['selectName']
        selPolicy = psfPolicy['select'].getPolicy()
        algName   = psfPolicy['algorithmName']
        algPolicy = psfPolicy['algorithm'].getPolicy()
        sdqaRatings = sdqa.SdqaRatingSet()
        self.log.log(self.log.INFO, "Measuring PSF")

        starSelector = measAlg.makeStarSelector(selName, selPolicy)
        psfCandidateList = starSelector.selectStars(exposure, sources)

        psfDeterminer = measAlg.makePsfDeterminer(algName, algPolicy)
        psf, cellSet = psfDeterminer.determinePsf(exposure, psfCandidateList, sdqaRatings)
        sdqaRatings = dict(zip([r.getName() for r in sdqaRatings], [r for r in sdqaRatings]))
        self.log.log(self.log.INFO, "PSF determination using %d/%d stars." % 
                     (sdqaRatings["phot.psf.numGoodStars"].getValue(),
                      sdqaRatings["phot.psf.numAvailStars"].getValue()))

        # The PSF candidates contain a copy of the source, and so we need to explicitly propagate new flags
        for cand in psfCandidateList:
            cand = measAlg.cast_PsfCandidateF(cand)
            src = cand.getSource()
            if src.getFlagForDetection() & measAlg.Flags.PSFSTAR:
                ident = src.getId()
                src = sources[ident]
                assert src.getId() == ident
                src.setFlagForDetection(src.getFlagForDetection() | algorithmsLib.Flags.PSFSTAR)

        exposure.setPsf(psf)
        return psf, cellSet


    @timecall
    def apCorr(self, exposure, cellSet):
        """Measure aperture correction

        @param exposure Exposure to process
        @param cellSet Set of cells of PSF stars
        """
        assert exposure, "No exposure provided"
        assert cellSet, "No cellSet provided"
        policy = self.config['apcorr'].getPolicy()
        control = maApCorr.ApertureCorrectionControl(policy)
        sdqaRatings = sdqa.SdqaRatingSet()
        corr = maApCorr.ApertureCorrection(exposure, cellSet, sdqaRatings, control, self.log)
        sdqaRatings = dict(zip([r.getName() for r in sdqaRatings], [r for r in sdqaRatings]))
        x, y = exposure.getWidth() / 2.0, exposure.getHeight() / 2.0
        value, error = corr.computeAt(x, y)
        self.log.log(self.log.INFO, "Aperture correction using %d/%d stars: %f +/- %f" %
                     (sdqaRatings["phot.apCorr.numAvailStars"].getValue(),
                      sdqaRatings["phot.apCorr.numGoodStars"].getValue(),
                      value, error))
        return corr


    @timecall
    def background(self, exposure, footprints=None, background=None):
        """Subtract background from exposure.

        @param exposure Exposure to process
        @param footprints Source footprints to mask
        @param background Background to restore before subtraction
        """
        if background is not None:
            if isinstance(background, afwMath.mathLib.Background):
                background = value.getImageF()
            exposure += background

        # Mask footprints on exposure
        if footprints is not None:
            # XXX Not implemented --- not sure how to do this in a way background subtraction will respect
            pass
        
        # Subtract background
        bg = self._Background(config=self.config, log=self.log)
        bg.run(exposure)


    @timecall
    def rephot(self, exposure, footprints, psf, apcorr=None):
        """Rephotometer exposure

        @param exposure Exposure to process
        @param footprints Footprints to rephotometer
        @param psf Point Spread Function
        @param apcorr Aperture correction, or None
        @param wcs World Coordinate System, or None
        @return Source list
        """
        rephot = self._Rephotometry(config=self.config, log=self.log)
        return rephot.run(exposure, footprints, psf, apcorr)


    def distortion(self, exposure):
        """Generate appropriate optical distortion

        @param exposure Exposure from which to get CCD
        @return Distortion
        """
        assert exposure, "No exposure provided"
        ccd = pipUtil.getCcd(exposure)
        dist = pipDist.createDistortion(ccd, self.config['distortion'])
        return dist


    @timecall
    def distort(self, exposure, sources, distortion=None):
        """Distort source positions before solving astrometry

        @param exposure Exposure to process
        @param sources Sources with undistorted (actual) positions
        @param distortion Distortion to apply
        @return Distorted sources, lower-left corner, size of distorted image
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"

        if distortion is not None:
            self.log.log(self.log.INFO, "Applying distortion correction.")
            distSources = distortion.actualToIdeal(sources)
            
            # Get distorted image size so that astrometry_net does not clip.
            xMin, xMax, yMin, yMax = float("INF"), float("-INF"), float("INF"), float("-INF")
            for x, y in ((0.0, 0.0), (0.0, exposure.getHeight()), (exposure.getWidth(), 0.0),
                         (exposure.getWidth(), exposure.getHeight())):
                point = afwGeom.Point2D(x, y)
                point = distortion.actualToIdeal(point)
                x, y = point.getX(), point.getY()
                if x < xMin: xMin = x
                if x > xMax: xMax = x
                if y < yMin: yMin = y
                if y > yMax: yMax = y
            xMin = int(xMin)
            yMin = int(yMin)
            llc = (xMin, yMin)
            size = (int(xMax - xMin + 0.5), int(yMax - yMin + 0.5))
            for s in distSources:
                s.setXAstrom(s.getXAstrom() - xMin)
                s.setYAstrom(s.getYAstrom() - yMin)
        else:
            distSources = sources
            size = (exposure.getWidth(), exposure.getHeight())
            llc = (0, 0)

        self.display('distortion', exposure=exposure, sources=distSources, pause=True)
        return distSources, llc, size


    @timecall
    def astrometry(self, exposure, sources, distSources, distortion=None, llc=(0,0), size=None):
        """Solve astrometry to produce WCS

        @param exposure Exposure to process
        @param sources Sources as measured (actual) positions
        @param distSources Sources with undistorted (ideal) positions
        @param distortion Distortion model
        @param llc Lower left corner (minimum x,y)
        @param size Size of exposure
        @return Star matches, match metadata
        """
        assert exposure, "No exposure provided"
        assert distSources, "No sources provided"

        self.log.log(self.log.INFO, "Solving astrometry")

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
        astrom = measAst.determineWcs(self.config['astrometry'].getPolicy(), exposure, distSources,
                                      log=log, forceImageSize=size, filterName=filterName)

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
            sky = wcs.pixelToSky(distSource.getXAstrom() - llc[0], distSource.getYAstrom() - llc[1])
            source.setRaDec(sky)

        self.display('astrometry', exposure=exposure, sources=sources, matches=matches)

        return matches, matchMeta


    @timecall
    def undistort(self, exposure, sources, matches, distortion=None):
        """Undistort matches after solving astrometry, resolving WCS

        @param exposure Exposure of interest
        @param sources Sources on image (no distortion applied)
        @param matches Astrometric matches
        @param distortion Distortion model
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        assert matches, "No matches provided"

        if distortion is None:
            # No need to do anything
            return

        # Undo distortion in matches
        self.log.log(self.log.INFO, "Removing distortion correction.")
        # Undistort directly, assuming:
        # * astrometry matching propagates the source identifier (to get original x,y)
        # * distortion is linear on very very small scales (to get x,y of catalogue)
        for m in matches:
            dx = m.first.getXAstrom() - m.second.getXAstrom()
            dy = m.first.getYAstrom() - m.second.getYAstrom()
            orig = sources[m.second.getId()]
            m.second.setXAstrom(orig.getXAstrom())
            m.second.setYAstrom(orig.getYAstrom())
            m.first.setXAstrom(m.second.getXAstrom() + dx)
            m.first.setYAstrom(m.second.getYAstrom() + dy)

        # Re-fit the WCS with the distortion undone
        if self.config['astrometry']['calculateSip']:
            self.log.log(self.log.INFO, "Refitting WCS with distortion removed")
            sip = astromSip.CreateWcsWithSip(matches, exposure.getWcs(), self.config['astrometry']['sipOrder'])
            wcs = sip.getNewWcs()
            self.log.log(self.log.INFO, "Astrometric scatter: %f arcsec (%s non-linear terms)" %
                         (sip.getScatterInArcsec(), "with" if wcs.hasDistortion() else "without"))
            exposure.setWcs(wcs)
            
            # Apply WCS to sources
            for index, source in enumerate(sources):
                sky = wcs.pixelToSky(source.getXAstrom(), source.getYAstrom())
                source.setRa(sky[0])
                source.setDec(sky[1])
        else:
            self.log.log(self.log.WARN, "Not calculating a SIP solution; matches may be suspect")
        
        self.display('astrometry', exposure=exposure, sources=sources, matches=matches)


    def verifyAstrometry(self, exposure, matches):
        """Verify astrometry solution

        @param exposure Exposure of interest
        @param matches Astrometric matches
        """
        verify = dict()                    # Verification parameters
        verify.update(astromSip.sourceMatchStatistics(matches))
        verify.update(astromVerify.checkMatches(matches, exposure, log=self.log))
        for k, v in verify.items():
            exposure.getMetadata().set(k, v)


    @timecall
    def zeropoint(self, exposure, matches):
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


class CalibratePsf(Calibrate):
    """Calibrate only the PSF for an image.
    Explicitly turns off other functions.
    """
    def run(*args, **kwargs):
        oldDo = self.config['do']['calibrate'].copy()
        newDo = self.config['do']['calibrate']

        newDo['background'] = False
        newDo['distortion'] = False
        newDo['astrometry'] = False
        newDo['zeropoint'] = False

        values = super(CalibratePsf, self).run(*args, **kwargs)

        self.config['do']['calibrate'] = oldDo

        return values
