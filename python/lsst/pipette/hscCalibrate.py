#!/usr/bin/env python

import lsst.sdqa as sdqa
import lsst.meas.algorithms as measAlg
#if True:
#    import lsst.meas.algorithms.psfSelectionRhl as maPsfSel
#else:
#    import lsst.meas.algorithms.psfSelectionFromMatchList as maPsfSel
#import lsst.meas.algorithms.psfAlgorithmRhl as maPsfAlg

from lsst.pipette.calibrate import Calibrate

class HscCalibrate(Calibrate):
    def __init__(self, *args, **kwargs):
        super(HscCalibrate, self).__init__(*args, **kwargs)
    
    def run(self, exposure, defects=None, background=None):
        """Calibrate an exposure: PSF, astrometry and photometry

        @param exposure Exposure to calibrate
        @param defects List of defects on exposure
        @param background Background model
        @return Psf, Aperture correction, Sources, Matches
        """
        assert exposure is not None, "No exposure provided"

        do = self.config['do']['calibrate']

        psf, wcs = self.fakePsf(exposure)

        self.repair(exposure, psf, defects=defects, preserve=True)

        if do['psf'] or do['astrometry'] or do['zeropoint']:
            sources, footprints = self.phot(exposure, psf)
        else:
            sources, footprints = None, None

        if do['distortion']:
            dist = self.distortion(exposure)
        else:
            dist = None

        if do['astrometry'] or do['zeropoint'] or do['psf']:
            # Solving the astrometry prevents us from re-solving for astrometry again later, so save the wcs...
            wcs0 = exposure.getWcs().clone()
            matches = self.astrometry(exposure, sources, distortion=dist)[0] # for the PSF determination
            exposure.setWcs(wcs0)                                            # ... and restore it
        else:
            matches = None

        if do['psf']:
            psf, cellSet = self.psf(exposure, sources, matches)
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
            sources = self.rephot(exposure, footprints, psf, apcorr=apcorr)

        if do['astrometry'] or do['zeropoint']:
            matches, matchMeta, wcs = self.astrometry(exposure, sources, distortion=dist)
        else:
            matches, matchMeta, wcs = None, None, None

        if do['zeropoint']:
            self.zeropoint(exposure, matches)

        self.display('calibrate', exposure=exposure, sources=sources, matches=matches)
        return psf, apcorr, sources, matches, matchMeta

    def psf(self, exposure, sources, matches):
        """Measure the PSF

        @param exposure Exposure to process
        @param sources Measured sources on exposure
        @param matches (optional) A matchlist as returned by self.astrometry
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

        if matches:
            if True:
                #
                # The matchList copies of the sources are not identical to the input sources,
                # so replace them with our pristine originals
                #
                matchesIn = matches
                matches = []
                for ref, source, distance in matchesIn:
                    mySources = [s for s in sources if s.getId() == source.getId()]
                    if len(mySources) != 1:
                        raise RuntimeError("Failed to find matchList source ID == %d in input source list" %
                                           source.getId())
                    mySource = mySources[0]
                    
                    matches.append((ref, mySource, distance))

                    if False:
                        print mySource.getXAstrom(), source.getXAstrom() - mySource.getXAstrom(), \
                              mySource.getYAstrom(), source.getYAstrom() - mySource.getYAstrom()



        starSelector = measAlg.makeStarSelector(selName, selPolicy)
        psfCandidateList = starSelector.selectStars(exposure, sources)

        psfDeterminer = measAlg.makePsfDeterminer(algName, algPolicy)
        psf, cellSet = psfDeterminer.determinePsf(exposure, psfCandidateList, sdqaRatings)

                        
        #try:                            # probe the required arguments
        #    needMatchList = maPsfSel.args[1] == "MatchList"
        #except AttributeError:
        #    needMatchList = False

        #if needMatchList:
        #    print "hscCal: yikes"
        #    psfStars, cellSet = maPsfSel.selectPsfSources(exposure, matches, selPolicy)
        #else:
        #    print "hscCal: ok"
        #    psfStars, cellSet = maPsfSel.selectPsfSources(exposure, sources, selPolicy)

        #psf, cellSet, psfStars = maPsfAlg.getPsf(exposure, psfStars, cellSet, algPolicy, sdqaRatings)
        exposure.setPsf(psf)
        return psf, cellSet
