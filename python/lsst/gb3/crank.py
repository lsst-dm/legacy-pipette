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

import lsst.gb3.config as gb3Config

import lsst.pex.logging as pexLog
import lsst.daf.persistence as dafPersist
import lsst.afw.cameraGeom as cameraGeom
import lsst.afw.cameraGeom.utils as cameraGeomUtils
import lsst.afw.image as afwImage
import lsst.afw.image.utils as imageUtils
import lsst.ip.isr as ipIsr



"""This module defines the Crank base class for LSST Algorithms testing (Green Blob 3)."""

class Crank(object):

    """Crank is a base class for LSST Algorithms testing (Green Blob 3).


    Public methods: read, isr, ccdAssembly, imgChar, write
    """

    def __init__(self,                  # Crank
                 name,                  # Base name for outputs
                 mapperClass,           # Mapper class to use
                 config=None,           # Configuration
                 ):
        self.name = name
        self.log = pexLog.Log(pexLog.getDefaultLog(), "Crank")

        self.config = gb3Config.configuration() if config is None else config
        roots = self.config['roots']
        self.mapper = mapperClass(root=roots['data'], calibRoot=roots['calib'])
        self.bf = dafPersist.ButlerFactory(mapper=self.mapper)
        self.butler = self.bf.create()

        self.do = self.config['do']
        return

    def turn(self,
             dataId                     # Data identifier
             ):
        exposure = self.read(dataId)
        self.isr(exposure, dataId)
        exposure = self.ccdAssembly(exposure, dataId)
        exposure, psf, sources, matches, wcs = self.imageChar(exposure, dataId)
        self.write(exposure, dataId, psf, sources, matches)
        return

    def read(self,
             dataId                     # Data identifier
             ):
        """Read raw data."""
        self.log.log(self.log.INFO, "Reading: %s" % (dataId))
        exposure = self.butler.get('raw', dataId)
        mImg = exposure.getMaskedImage()
        if isinstance(exposure, afwImage.ExposureU):
            exposure = exposure.convertF()
        return exposure

    def isr(self,
            exposure,                   # Exposure to correct
            dataId                      # Data identifier
            ):
        """Instrument signature removal: generate mask and variance;
        subtract overscan, bias, dark; divide by flat-field;
        subtract fringes.
        """
        if self.do['saturation']:
            self._saturation(exposure, dataId)
        if self.do['overscan']:
            self._overscan(exposure, dataId)
        self._trim(exposure, dataId)
        if self.do['bias']:
            self._bias(exposure, dataId)
        self._variance(exposure, dataId)
        if self.do['dark']:
            self._dark(exposure, dataId)
        if self.do['flat']:
            self._flat(exposure, dataId)
        if self.do['fringe']:
            self._fringe(exposure, dataId)
        return


    def ccdAssembly(self, exposureList, dataId):
        """Assembly of amplifiers into CCDs.
        Also applies defects (static mask)."""
        exposure = self._assembly(exposureList, dataId)
        return exposure


    def imageChar(self, exposure, dataId):
        """Image characterisation: background subtraction,
        cosmic-ray rejection, source detection and measurement,
        PSF determination, and photometric and astrometric
        calibration."""

        # Default return values
        bgSubExp = None
        psf = None
        sources = None
        matches = None
        wcs = exposure.getWcs()

        if self.do['defects']:
            self._defects(exposure, dataId)
        if self.do['background']:
            bgSubExp = self._background(exposure, dataId)
        else: bgSubExp = exposure
        if self.do['phot']:
            posSources, negSources = self._detect(bgSubExp, dataId)
            sources = self._measure(bgSubExp, dataId, posSources, negSources)
            psf = self._psfMeasurement(bgSubExp, dataId, sources)
            if self.do['cr']:
                self._cosmicray(bgSubExp, dataId)
            posSources, negSources = self._detect(bgSubExp, dataId, psf=psf)
            sources = self._measure(bgSubExp, dataId, posSources, negSources, psf=psf, wcs=wcs)
        if self.do['ast']:
            matches, wcs = self._astrometry(bgSubExp, dataId, sources)
        if self.do['cal'] and matches is not None and len(matches) > 0:
            self._photcal(bgSubExp, dataId, matches)

        return bgSubExp, psf, sources, matches, wcs


    def write(self, exposure, dataId, psf, sources, matches):
        """Write processed data."""
        self.butler.put(exposure, 'postISRCCD', dataId)
        if psf is not None:
            self.butler.put(psf, 'psf', dataId)
        if sources is not None:
            self.butler.put(lsst.afw.detection.PersistableSourceVector(sources), 'src', dataId)
        if matches is not None:
            self.butler.put(matches, 'matches', dataId)
        return


##############################################################################################################
# ISR methods
##############################################################################################################

    def _saturation(self, expsure, dataId):
        exposure = ipIsr.convertImageForIsr(exposure)
        amp = cameraGeom.cast_Amp(exposure.getDetector())
        saturation = amp.getElectronicParams().getSaturationLevel()
        bboxes = ipIsr.saturationDetection(exposure, int(saturation), doMask = True)
        self.log.log(self.log.INFO, "Found %d saturated regions." % len(bboxes))
        return

    def _overscan(self, exposure, dataId):
        self.log.log(self.log.INFO, "Performing overscan correction...")
        fittype = "MEDIAN"                # XXX policy argument
        ccd = exposure.getDetector()
        for amp in cameraGeom.cast_Ccd(ccd):
            biassec = amp.getDiskBiasSec()
            self.log.log(self.log.INFO, "Doing overscan correction on amp %s: %s" % (amp.getId(), biassec))
            ipIsr.overscanCorrection(exposure, biassec, fittype)
        return

    def _trim(self, exposure, dataId):
        ccd = cameraGeomUtils.findCcd(self.mapper.camera, cameraGeom.Id(dataId['ccd']))
        miBefore = exposure.getMaskedImage()
        MaskedImage = type(miBefore)
        miAfter = MaskedImage(ccd.getAllPixels(True).getDimensions())
        for amp in ccd:
            datasecBefore = amp.getDataSec(False)
            datasecAfter = amp.getDataSec(True)
            self.log.log(self.log.INFO, "Trimming amp %s: %s --> %s" %
                         (amp.getId(), datasecBefore, datasecAfter))
            trimAmp = MaskedImage(miBefore, datasecBefore)
            trimImage = MaskedImage(miAfter, datasecAfter)
            trimImage <<= trimAmp
            amp.setTrimmed(True)
        exposure.setMaskedImage(miAfter)
        return


    def _bias(self, exposure, dataId):
        bias = self.butler.get("bias", dataId)
        ipIsr.biasCorrection(exposure, bias)
        return

    def _variance(self, exposure, dataId):
        ccd = exposure.getDetector()
        mi = exposure.getMaskedImage()
        MaskedImage = type(mi)
        for amp in cameraGeom.cast_Ccd(ccd):
            gain = amp.getElectronicParams().getGain()
            self.log.log(self.log.INFO, "Setting variance for amp %s: %f" % (amp.getId(), gain))
            miAmp = MaskedImage(mi, amp.getDataSec())
            variance = miAmp.getVariance()
            variance <<= miAmp.getImage()
            variance /= gain
        return

    def _dark(self, exposure, dataId):
        dark = self.butler.get("dark", dataId)
        expTime = float(exposure.getCalib().getExptime())
        darkTime = float(dark.getCalib().getExptime())
        ipIsr.darkCorrection(exposure, dark, expTime, darkTime)
        return

    def _flat(self, exposure, dataId):
        flat = self.butler.get("flat", dataId)
        mi = exposure.getMaskedImage()
        image = mi.getImage()
        variance = mi.getVariance()
        flatImage = flat.getMaskedImage().getImage()
        # XXX This looks awful because AFW doesn't define useful functions.  Need to fix this.
        image /= flatImage
        variance /= flatImage
        variance /= flatImage
        ### This API is bad --- you NEVER want to rescale your flat on the fly.
        ### Scale it properly when you make it and never rescale again.
        #ipIsr.flatCorrection(exposure, flat, "USER", 1.0)
        return

    def _fringe(self, exposure, dataId):
        flat = self.butler.get("fringe", dataId)
        raise NotimplementedError, "Fringe subtraction is not yet implemented."

##############################################################################################################
# CCD assembly method
##############################################################################################################

    def _assembly(self, exposureList, dataid):
        if not hasattr(exposureList, "__getitem__"):
            # This is not a list; presumably it's a single item needing no assembly
            return exposureList
        rmKeys = ["CCDID", "AMPID", "E2AOCHI", "E2AOFILE",
                  "DC3BPATH", "GAIN", "BIASSEC", "DATASEC"]    # XXX policy argument
        amp = cameraGeom.cast_Amp(exposureList[0].getDetector())
        ccd = cameraGeom.cast_Ccd(amp.getParent())
        exposure = ipIsr.ccdAssemble.assembleCcd(exposureList, ccd, keysToRemove=rmKeys)
        return exposure

##############################################################################################################
# Image characterisation methods
##############################################################################################################

    def _defects(self, exposure, dataId):
        defects = measAlg.DefectListT()
        statics = cameraGeom.cast_Ccd(exposure.getDetector()).getDefects() # Static defects
        for defect in statics:
            bbox = defect.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)
        fwhm = 3.0                        # XXX policy argument
        ipIsr.maskBadPixelsDef(exposure, defects, fwhm, interpolate=False, maskName='BAD')
        self.log.log(self.log.INFO, "Masked %d static defects." % len(statics))

        sat = ipIsr.defectListFromMask(exposure, growFootprints=1, maskName='SAT') # Saturated defects
        for defect in sat:
            bbox = d.getBBox()
            new = measAlg.Defect(bbox)
            defects.append(new)
        ipIsr.interpolateDefectList(exposure, defects, fwhm)
        self.log.log(self.log.INFO, "Interpolated over %d static+saturated defects." % len(defects))

        nans = ipIsr.UnmaskedNanCounterF() # Search for unmasked NaNs
        nans.apply(exposure.getMaskedImage())
        self.log.log(self.log.INFO, "Fixed %d unmasked NaNs." % nans.getNpix())
        return

    def _background(self, exposure, dataId):
        bgPolicy = self.policy.getPolicy("background") # XXX needs work
        bg, subtracted = sourceDetection.estimateBackground(exposure, bgPolicy, subtract=True)
        # XXX Dropping bg on the floor
        return subtracted

    def _cosmicray(self, exposure, dataId):
        fwhm = 1.0                        # XXX policy argument: seeing in arcsec
        keepCRs = True                    # Keep CR list?
        crs = ipUtils.cosmicRays.findCosmicRays(exposure, self.crRejectPolicy, defaultFwhm, keepCRs)
        self.log.log(self.log.INFO, "Identified %d cosmic rays." % len(crs))
        return

    def _detect(self, exposure, dataId, psf=None):
        policy = self.policy.getPolicy("detect") # XXX needs work
        posSources, negSources = sourceDetection.detectSources(exposure, psf, policy)
        self.log.log(self.log.INFO, "Detected %d positive and %d negative sources." % \
                     (len(posSources), len(negSources)))
        return posSources, negSources

    def _measure(self, exposure, dataId, posSources, negSources=None, psf=None, wcs=None):
        policy = self.policy.getPolicy("measure") # XXX needs work
        footprints = []                    # Footprints to measure
        if posSources:
            self.log.log(self.log.INFO, "Measuring %d positive sources" % len(posSources))
            footprints.append([posSources.getFootprints(), False])
        if negSources:
            self.log.log(self.log.INFO, "Measuring %d positive sources" % len(posSources))
            footprints.append([negSources.getFootprints(), True])

        sources = srcMeas.sourceMeasurement(exposure, psf, footprints, policy)

        if wcs is not None:
            sourceMeasurement.computeSkyCoords(wcs, sources)

        return sources

    def _psfMeasurement(self, exposure, dataId, sources):
        policy = self.policy.getPolicy("psf") # XXX needs work
        sdqaRatings = sdqa.SdqaRatingSet()
        psf, cellSet = Psf.getPsf(exposure, sources, policy, sdqaRatings)
        # XXX Dropping cellSet on the floor
        return psf

    def _astrometry(self, exposure, dataId, sources):
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

    def _photcal(self, exposure, dataId, matches):
        zp = photocal.calcPhotoCal(matches, log=self.log)
        exposure.getCalib().setFluxMag0(zp.getFlux(0))
        self.log.log(self.log.INFO, "Flux of magnitude 0: %g" % zp.getFlux(0))
        return
