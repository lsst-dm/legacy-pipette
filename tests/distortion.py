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


import unittest
import lsst.utils.tests as utilsTests

import math

import lsst.pex.policy as pexPolicy
import lsst.afw.detection as afwDet
import lsst.afw.cameraGeom as cameraGeom
import lsst.afw.cameraGeom.utils as cameraGeomUtils
import lsst.gb3.engine.distortion as distortion
import lsst.gb3.engine.config as engConfig

REVERSE_TOL = 0.01                      # Tolerance for difference after reversing, pixels
ABSOLUTE_TOL = 2.0                      # Tolerance for difference with 'correct' version, pixels
COEFFS = [1.0, 7.16417e-08, 3.03146e-10, 5.69338e-14, -6.61572e-18] # Coefficients for Bick version


# Steve Bickerton's version of the forward transformation for Subaru/SuprimeCam
# The CCD positions here and in the policy file differ (besides the fact that these are for the corner, while
# the policy file uses the centre) so probably don't need to get too worried about a moderately different
# distortion (a couple pixels) at the very edge (e.g., chip 3 "sophie")
def bickDistortion(x, y, ccdNum):
    x0 = [3197, 1075, -1043, 3197, 1081, -1045, -5285, -3165, -5283, -3163]
    y0 = [82,     82,    83,-4170,-4168, -4173,    83,    82, -4171, -4167]

    x += x0[ccdNum]
    y += y0[ccdNum]

    theta = math.atan2(y, x)
    r = math.sqrt(x*x + y*y)

    r_distort = 0.0
    for i in range(1,6):
        r_distort += COEFFS[i-1] * r**i

    x_distort, y_distort = r_distort*math.cos(theta), r_distort*math.sin(theta)

    return (x_distort - x0[ccdNum], y_distort - y0[ccdNum])

def compare(xTest, yTest, xTruth, yTruth, tol):
    distance = math.hypot(xTruth - xTest, yTruth - yTest)
    return True if distance < tol else False


class ConfigTestCase(unittest.TestCase):
    """A test case for configuration"""

    def setUp(self):
        policy = pexPolicy.Policy("tests/SuprimeCam_Geom.paf")
        geomPolicy = cameraGeomUtils.getGeomPolicy(policy)
        self.camera = cameraGeomUtils.makeCamera(geomPolicy)
        coeffs = list(COEFFS)
        coeffs.reverse()           # NumPy's poly1d wants coeffs in descending order of powers
        coeffs.append(0.0)         # NumPy's poly1d goes all the way down to zeroth power
        self.config = engConfig.Config()
        distConfig = engConfig.Config()
        distConfig['coeffs'] = coeffs
        distConfig['step'] = 10.0
        self.config['radial'] = distConfig

    def tearDown(self):
        del self.camera
        del self.config

    def testRadialDistortion(self):
        for raft in self.camera:
            for ccdIndex, ccd in enumerate(cameraGeom.cast_Raft(raft)):
                dist = distortion.createDistortion(ccd, self.config)
                size = ccd.getSize()
                height, width = size.getX(), size.getY()
                for x, y in ((0.0,0.0), (0.0, height), (0.0, width), (height, width), (height/2.0,width/2.0)):
                    src = afwDet.Source()
                    src.setXAstrom(x)
                    src.setYAstrom(y)
                    forward = dist.measuredToDistorted(src)
                    backward = dist.distortedToMeasured(forward)
                    trueForward = bickDistortion(x, y, ccdIndex)

                    self.assertTrue(compare(backward.getXAstrom(), backward.getYAstrom(), x, y, REVERSE_TOL),
                                    "Undistorted distorted position is not original: %f,%f vs %f,%f for %d" %
                                    (backward.getXAstrom(), backward.getYAstrom(), x, y, ccdIndex))
                    self.assertTrue(compare(forward.getXAstrom(), forward.getYAstrom(),
                                            trueForward[0], trueForward[1], ABSOLUTE_TOL),
                                    "Distorted position is not correct: %f,%f vs %f,%f for %d %f,%f" %
                                    (forward.getXAstrom(), forward.getYAstrom(),
                                     trueForward[0], trueForward[1],
                                     ccdIndex, x, y))

def suite():
    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(ConfigTestCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)
    return unittest.TestSuite(suites)

def run(shouldExit = False):
    utilsTests.run(suite(), shouldExit)

if __name__ == '__main__':
    run(True)
