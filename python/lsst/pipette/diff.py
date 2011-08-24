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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import lsst.afw.math as afwMath
import lsst.afw.image as afwImage
import lsst.ip.diffim as diffim
import lsst.pipette.process as pipProc


from lsst.pipette.calibrate import CalibratePsf
from lsst.pipette.phot import Photometry

class Diff(pipProc.Process):
    def __init__(self, Calibrate=CalibratePsf, Photometry=Photometry, *args, **kwargs):
        super(Diff, self).__init__(*args, **kwargs)
        self._Calibrate = Calibrate
        self._Photometry = Photometry

    def run(self, inputExp, templateExp, inverse=False):
        """Subtract a template exposure from an input exposure.
        The exposures are assumed to be aligned already

        @param[in] inputExp Input exposure (minuend)
        @param[in] templateExp Template exposure (subtrahend)        
        @param[in] inverse Invert sense of subtraction?
        @return Subtracted exposure
        """

        do = self.config['do']['diff']

        if True:
            if do['match'] and do['convolve']:
                convolved = self.match(templateExp, inputExp)
            else:
                convolved = templateExp
        else:
            # XXX The ip_diffim API has changed substantially since whenever I wrote this...
            if do['match']:
                cellSet = self.stamps(inputExp, templateExp)
                kernel = self.kernel(inputExp, templateExp, cellSet)
            else:
                kernel = None

            if do['match'] and do['convolve']:
                convolved = self.convolve(templateExp, kernel)
            else:
                convolved = templateExp
        
        diff = inputExp.Factory(inputExp, True)
        diffImage = diff.getMaskedImage()
        convImage = convolved.getMaskedImage()
        diffImage -= convImage
        if inverse:
            diffImage *= -1

        combined = inputExp.Factory(inputExp, True)
        combinedImage = combined.getMaskedImage()
        combinedImage += convImage
        combinedImage *= 0.5            # Get scaling right!

        psf, apcorr, brightSources = self.calibrate(combined)

        sources, footprints = self.phot(diff, psf, apcorr)

        self.display('diff', exposure=diff, sources=sources)

        return diff, sources, psf, apcorr, brightSources

    def match(self, template, input):
        """Convolve template to match input

        @param[in] template Template exposure
        @param[in] input Input exposure
        @output convolved template exposure
        """
        policy = self.config['diff'].getPolicy()
        matcher = diffim.ImagePsfMatch(policy)
        convolved, kernel, bg, cells = matcher.matchExposures(template, input, doWarping=False)
        # XXX dropping kernel, bg, cells on the floor
        return convolved


    def stamps(self, exp1, exp2):
        """Find suitable stamps

        @param[in] exp1 First exposure of interest
        @param[in] exp2 Second exposure of interest
        @output Cell set
        """
        policy = self.config['diff'].getPolicy()

        # XXX The following was cut from lsst.ip.diffim.createPsfMatchingKernel, since that does the stamp
        # identification and kernel solution within the same function, while one might imagine overriding one
        # of these with some other method.

        # Object to store the KernelCandidates for spatial modeling
        kernelCellSet = afwMath.SpatialCellSet(exp1.getBBox(afwImage.PARENT),
                                               policy.getInt("sizeCellX"),
                                               policy.getInt("sizeCellY"))

        # Candidate source footprints to use for Psf matching
        footprints = diffim.getCollectionOfFootprintsForPsfMatching(exp2, exp1, policy)

        # Place candidate footprints within the spatial grid
        for fp in footprints:
            bbox = fp.getBBox()

            # Grab the centers in the parent's coordinate system
            xC   = 0.5 * ( bbox.getMinX() + bbox.getMaxX() )
            yC   = 0.5 * ( bbox.getMinY() + bbox.getMaxY() )

            # Since the footprint is in the parent's coordinate system,
            # while the BBox uses the child's coordinate system.
            bbox.shift(-afwGeom.Extent2I(exp2.getXY0()))

            tmi  = afwImage.MaskedImageF(exp2, bbox)
            smi  = afwImage.MaskedImageF(exp1, bbox)

            cand = diffim.makeKernelCandidate(xC, yC, tmi, smi)
            kernelCellSet.insertCandidate(cand)

        return kernelCellSet

    def kernel(self, targetExp, sourceExp, stamps):
        """Calculate PSF-matching kernel

        @param[in] targetExp Target exposure (to match to)
        @param[in] sourceExp Source exposure (to be matched)
        @param[in] stamps Stamps to use
        @output Convolution kernel, background difference model
        """
        policy = self.config['diff'].getPolicy()

        # XXX The following was cut from lsst.ip.diffim.createPsfMatchingKernel, since that does the stamp
        # identification and kernel solution within the same function, while one might imagine overriding one
        # of these with some other method.

        # Object to perform the Psf matching on a source-by-source basis
        kFunctor = createKernelFunctor(policy)

        # Create the Psf matching kernel
        try:
            kb = diffim.fitSpatialKernelFromCandidates(kFunctor, kernelCellSet, policy)
        except pexExcept.LsstCppException, e:
            pexLog.Trace("lsst.ip.diffim.createPsfMatchingKernel", 1,
                         "ERROR: Unable to calculate psf matching kernel")
            pexLog.Trace("lsst.ip.diffim.createPsfMatchingKernel", 2,
                         e.args[0].what())
            raise
        else:
            spatialKernel = kb.first
            spatialBg     = kb.second

        # What is the status of the processing?
        nGood = 0
        for cell in kernelCellSet.getCellList():
            for cand in cell.begin(True):
                cand = diffim.cast_KernelCandidateF(cand)
                if cand.getStatus() == afwMath.SpatialCellCandidate.GOOD:
                    nGood += 1
        if nGood == 0:
            pexLog.Trace("lsst.ip.diffim.createPsfMatchingKernel", 1, "WARNING")
        pexLog.Trace("lsst.ip.diffim.createPsfMatchingKernel", 1,
                     "Used %d kernels for spatial fit" % (nGood))

        return spatialKernel, spatialBg

        pass

    def convolve(self, exposure, kernel):
        """Convolve image with kernel

        @param[in] exposure Exposure to convolve
        @param[in] kernel Kernel with which to convolve
        @output Convolved exposure
        """
        convolved = exposure.Factory(exposure)
        afwMath.convolve(convolved.getMaskedImage(), exposure.getMaskedImage(), kernel, false)
        return convolved

    def calibrate(self, exposure):
        """PSF and photometric calibration
        
        @param[in] exposure Exposure to calibrate
        @output PSF, Aperture correction, Sources
        """
        return self._Calibrate(config=self.config, log=self.log).run(exposure)

    def phot(self, exposure, psf, apcorr):
        """Perform photometry on exposure

        @param[in] exposure Exposure to photometer
        @param[in] psf Point-spread function
        @param[in] apcorr Aperture correction
        @output Sources
        """
        return self._Photometry(config=self.config, log=self.log).run(exposure, psf, apcorr)
