#!/usr/bin/env python
#
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import os
import re
from lsst.daf.persistence import ButlerLocation, LogicalLocation, Mapping, CalibrationMapping
import lsst.daf.butlerUtils as butlerUtils
import lsst.daf.base as dafBase
import lsst.afw.image as afwImage
import lsst.afw.cameraGeom as afwCameraGeom
import lsst.afw.cameraGeom.utils as cameraGeomUtils
import lsst.afw.image.utils as imageUtils
import lsst.pex.logging as pexLog
import lsst.pex.policy as pexPolicy
import lsst.ip.isr as ipIsr


"""This module defines the Crank base class for LSST Algorithms testing (Green Blob 3)."""

class Crank(object):

    """Crank is a base class for LSST Algorithms testing (Green Blob 3).


    Public methods: read, isr, ccdAssembly, imgChar, write
    """

    def __init__(self,                  # Crank
                 name,                  # Base name for outputs
                 mapper,                # Mapper for data butler
                 policy=None,           # Policy for configuration
                 ):
        self.name = name
        self.mapper = mapper
        self.config = Config(policy)
        self.log = pexLog.Log(pexLog.getDefaultLog(), "Crank")



        # Policy setup
        if policy is None:
            self.policy = pexPolicy.Policy()
        elif isinstance(policy, pexPolicy.Policy):
            self.policy = policy
        elif isinstance(policy, pexPolicy.PolicyFile):
            self.policy = pexPolicy.Policy.createPolicy(policy, policy.getRepositoryPath())
        else:
            raise RuntimeError, "Can't interpret provided policy"
        dictFile = pexPolicy.DefaultPolicyFile("sia", "Processor.paf", "policy")
        dictPolicy = pexPolicy.Policy.createPolicy(dictFile, dictFile.getRepositoryPath()) # Dictionary
        self.policy.mergeDefaults(dictPolicy)

        self.do = dict()                # Things to do
        self.do["isr"] = self.policy.getBool("isr")
        self.do["imgchar"] = self.policy.getBool("imgchar")
        self.do["ap"] = self.policy.getBool("ap")

        self.bf = dafPersist.ButlerFactory(mapper=mapper)
        self.butler = self.bf.create()

        return


    def read(dataId                        # Data identifier
             ):
        """Read raw data."""
        camera = butler.get('camera', dataId)
        ccd = cameraGeomUtils.findCcd(camera, cameraGeom.Id(dataId['ccd']))
        print "Loading: ccd: ", ccd.getId().getSerial(), ", ccdName: ", ccdName = ccd.getId().getName()

        exposure = butler.get('raw', dataId)
        mImg = exposure.getMaskedImage()
        mImg.setVarianceFromGain()
        return exposure


    def isr(exposure,                    # Exposure to correct
            dataId                        # Data identifier
            ):
        """Instrument signature removal: generate mask and variance;
        subtract overscan, bias, dark; divide by flat-field;
        subtract fringes.
        """
        self._saturation(exposure, dataId)
        self._overscan(exposure, dataId)
        self._bias(exposure, dataId)
        self._variance(exposure, dataId)
        self._dark(exposure, dataId)
        self._flat(exposure, dataId)
        #self._fringe(exposure, dataId)
        return


    def ccdAssembly(exposures, dataId):
        """Assembly of amplifiers into CCDs.
        Also applies defects (static mask)."""
        exposure = self._assembly(exposure, dataId)
        return exposure


    def imageChar(exposure, dataId):
        """Image characterisation: background subtraction,
        cosmic-ray rejection, source detection and measurement,
        PSF determination, and photometric and astrometric
        calibration."""
        self._defects(exposure, dataId)
        bgSubExp = self._background(exposure, dataId)
        self._cosmicray(bgSubExp, dataId)
        posSources, negSources = self._detect(bgSubExp, dataId)
        sources = self._measure(bgSubExp, dataId, posSources, negSources)
        psf = self._psfMeasurement(bgSubExp, dataId, sources)
        matches, wcs = self._astrometry(bgSubExp, dataId, sources)
        self._photcal(bgSubExp, dataId, matches)
        # Repeat with proper PSF
        posSources, negSources = self._detect(bgSubExp, dataId, psf=psf)
        sources = self._measure(bgSubExp, dataId, posSources, negSources, psf=psf, wcs=wcs)

        return bgSubExp, psf, sources, matches


    def write(exposure, dataId, psf, sources, matches):
        """Write processed data."""
        butler.put('processed', exposure, dataId)
        if psf is not None:
            butler.put('psf', psf, dataId)
        if sources is not None:
            butler.put('src', lsst.afw.detection.PersistableSourceVector(sources), dataId)
        if matches is not None:
            butler.put('matches', matches, dataId)
        return


##############################################################################################################
# ISR methods
##############################################################################################################

    def _saturation(expsure, dataId):
        exposure = ipIsr.convertImageForIsr(exposure)
        amp = cameraGeom.cast_Amp(exposure.getDetector())
        saturation = amp.getElectronicParams().getSaturationLevel()
        bboxes = ipIsr.saturationDetection(exposure, int(saturation), doMask = True)
        self.log.log(Log.INFO, "Found %d saturated regions." % len(bboxes))
        return

    def _overscan(exposure, dataId):
        fittype = "MEDIAN"                # XXX policy argument
        amp = cameraGeom.cast_Amp(exposure.getDetector())
        overscanBbox = amp.getDiskBiasSec()
        dataBbox = amp.getDiskDataSec()
        ipIsr.overscanCorrection(exposure, overscanBbox, fittype)
        return

    def _bias(exposure, dataId):
        bias = self.butler.get("bias", dataId)
        ipIsr.biasCorrection(exposure, bias)
        return

    def _variance(exposure, dataId):
        ipIsr.updateVariance(exposure)
        return

    def _dark(exposure, dataId):
        dark = self.butler.get("dark", dataId)
        expTime = float(exposure.getCalib().getExptime())
        darkTime = float(dark.getCalib().getExptime())
        ipIsr.darkCorrection(exposure, dark, expTime, darkTime)
        return

    def _flat(exposure, dataId):
        flat = self.butler.get("flat", dataId)
        # This API is bad --- you NEVER want to rescale your flat on the fly.
        # Scale it properly and never rescale again.
        ipIsr.flatCorrection(exposure, dark, "USER", 1.0)
        return

    def _fringe(exposure, dataId):
        flat = self.butler.get("fringe", dataId)
        raise NotimplementedError, "Fringe subtraction is not yet implemented."

##############################################################################################################
# CCD assembly method
##############################################################################################################

    def _assembly(exposures, dataid):
        rmKeys = ["CCDID", "AMPID", "E2AOCHI", "E2AOFILE",
                  "DC3BPATH", "GAIN", "BIASSEC", "DATASEC"]    # XXX policy argument
        amp = cameraGeom.cast_Amp(exposureList[0].getDetector())
        ccd = cameraGeom.cast_Ccd(amp.getParent())
        exposure = ipIsr.ccdAssemble.assembleCcd(exposures, ccd, keysToRemove=rmKeys)
        return exposure

##############################################################################################################
# Image characterisation methods
##############################################################################################################

    def _defects(exposure, dataId):
        defects = measAlg.DefectListT()
        statics = cameraGeom.cast_Ccd(exposure.getDetector()).getDefects() # Static defects
        for defect in statics:
            bbox = defect.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)
        fwhm = 3.0                        # XXX policy argument
        ipIsr.maskBadPixelsDef(exposure, defects, fwhm, interpolate=False, maskName='BAD')
        self.log.log(Log.INFO, "Masked %d static defects." % len(statics))

        sat = ipIsr.defectListFromMask(exposure, growFootprints=1, maskName='SAT') # Saturated defects
        for defect in sat:
            bbox = d.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)
        ipIsr.interpolateDefectList(exposure, defects, fwhm)
        self.log.log(Log.INFO, "Interpolated over %d static+saturated defects." % len(defects))

        nans = ipIsr.UnmaskedNanCounterF() # Search for unmasked NaNs
        nans.apply(exposure.getMaskedImage())
        self.log.log(Log.INFO, "Fixed %d unmasked NaNs." % nans.getNpix())
        return

    def _background(exposure, dataId):
        bgPolicy = self.policy.getPolicy("background") # XXX needs work
        bg, subtracted = sourceDetection.estimateBackground(exposure, bgPolicy, subtract=True)
        # XXX Dropping bg on the floor
        return subtracted

    def _cosmicray(exposure, dataId):
        fwhm = 1.0                        # XXX policy argument: seeing in arcsec
        keepCRs = True                    # Keep CR list?
        crs = ipUtils.cosmicRays.findCosmicRays(exposure, self.crRejectPolicy, defaultFwhm, keepCRs)
        self.log.log(Log.INFO, "Identified %d cosmic rays." % len(crs))
        return

    def _detect(exposure, dataId, psf=None):
        policy = self.policy.getPolicy("detect") # XXX needs work
        posSources, negSources = sourceDetection.detectSources(exposure, psf, policy)
        self.log.log(Log.INFO, "Detected %d positive and %d negative sources." % \
                     (len(posSources), len(negSources))
        return posSources, negSources

    def _measure(exposure, dataId, posSources, negSources, psf=None, wcs=None):
        policy = self.policy.getPolicy("measure") # XXX needs work
        footprints = []                    # Footprints to measure
        if posSources:
            self.log.log(Log.INFO, "Measuring %d positive sources" % len(posSources))
            footprints.append([posSources.getFootprints(), False])
        if negSources:
            self.log.log(Log.INFO, "Measuring %d positive sources" % len(posSources))
            footprints.append([negSources.getFootprints(), True])

        sources = srcMeas.sourceMeasurement(exposure, psf, footprints, policy)

        if wcs is not None:
            sourceMeasurement.computeSkyCoords(wcs, sources)

        return sources

    def _psfMeasurement(exposure, dataId, sources):
        policy = self.policy.getPolicy("psf") # XXX needs work
        sdqaRatings = sdqa.SdqaRatingSet()
        psf, cellSet = Psf.getPsf(exposure, sources, policy, sdqaRatings)
        # XXX Dropping cellSet on the floor
        return psf

    def _astrometry(exposure, dataId, sources):
        policy = self.policy.getPolicy("astrometry") # XXX needs work
        path=os.path.join(os.environ['ASTROMETRY_NET_DATA_DIR'], "metadata.paf")
        solver = astromNet.GlobalAstrometrySolution(path)
        # solver.allowDistortion(self.policy.get('allowDistortion'))
        solver.setMatchThreshold(self.policy.get('matchThreshold'))
        matches, wcs = measAstrom.determineWcs(policy, exposure, sources, solver=solver, log=self.log)

        verify = dict()                    # Verification parameters
        verify.update(sip.sourceMatchStatistics(matches))
        verify.update(verifyWcs.checkMatches(matches, exposure, self.log))
        self.log.log(self.log.DEBUG, "cells nobj min = %(minObjectsPerCell)s max = %(maxObjectsPerCell)s mean = %(meanObjectsPerCell)s std = %(stdObjectsPerCell)s" % verify)
        for k, v in outputDict.items():
            exposure.getMetadata().set(k, v)
        return matches, wcs

    def _photcal(exposure, dataId, matches):
        zp = photocal.calcPhotoCal(matches, log=self.log)
        exposure.getCalib().setFluxMag0(zp.getFlux(0))
        self.log.log(Log.INFO, "Flux of magnitude 0: %g" % zp.getFlux(0))
        return
