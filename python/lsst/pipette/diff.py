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

import lsst.pipette.process as pipProc


class Diff(pipProc.Process):
    def run(self, inputExp, templateExp, inverse=False):
        """Subtract a template exposure from an input exposure.
        The exposures are assumed to be aligned already

        @param[in] inputExp Input exposure (minuend)
        @param[in] templateExp Template exposure (subtrahend)        
        @param[in] inverse Invert sense of subtraction?
        @return Subtracted exposure
        """

        if do['match']:
            cellSet = self.stamps(inputExp, templateExp)
            kernel = self.kernel(inputExp, templateExp, cellSet)
        else:
            kernel = None

        if do['match'] and do['convolve']:
            convolved = self.convolve(templateExp, kernel)
        else:
            convolved = templateExp
        
        if not inverse:
            diff = inputExp - convolved
        else:
            diff = convolved - inputExp

        combined = inputExp + convolved
        combined /= 0.5                 # Get scaling right!

        psf, apcorr, brightSources = self.calibrate(combined)

        sources = self.phot(diff, psf, apcorr)

        return diff, sources, psf, apcorr, brightSources


    def stamps(exp1, exp2):
        """Find suitable stamps

        @param[in] exp1 First exposure of interest
        @param[in] exp2 Second exposure of interest
        @output Cell set
        """
        pass

    def kernel(targetExp, sourceExp, stamps):
        """Calculate PSF-matching kernel

        @param[in] targetExp Target exposure (to match to)
        @param[in] sourceExp Source exposure (to be matched)
        @param[in] stamps Stamps to use
        @output Convolution kernel
        """
        pass

    def convolve(exposure, kernel):
        """Convolve image with kernel

        @param[in] exposure Exposure to convolve
        @param[in] kernel Kernel with which to convolve
        @output Convolved exposure
        """
        pass

    def calibrate(exposure):
        """PSF and photometric calibration
        
        @param[in] exposure Exposure to calibrate
        @output PSF, Aperture correction, Sources
        """
        pass

    def phot(exposure, psf, apcorr):
        """Perform photometry on exposure

        @param[in] exposure Exposure to photometer
        @param[in] psf Point-spread function
        @param[in] apcorr Aperture correction
        @output Sources
        """
        pass
