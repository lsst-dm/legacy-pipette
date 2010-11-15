#!/usr/bin/env python

import os, math
import numpy
import lsst.afw.detection as afwDet
import lsst.afw.geom as afwGeom

"""This module defines the CameraDistortion class, which calculates the effects of optical distortions."""

class CameraDistortion(object):
    """This is a base class for calculating the effects of optical distortions on a camera."""

    def _distortPosition(self, x, y, *args, **kwargs):
        """Distort/undistort a single position.

        @param x X coordinate to distort
        @param y Y coordinate to distort
        """
        raise NotImplementedError("Method for %s not implemented" % __name__)

    def _distortSources(self, input, *args, **kwargs):
        """Common method to distort/undistort a source or sources.

        @param input Source or iterable of sources to distort
        @returns Copy of source or sources with modified coordinates
        """
        if hasattr(input, "__iter__"):
            # Presumably an iterable of Sources
            output = type(input)()
            for inSource in input:
                outSource = type(inSource)(inSource)
                xIn, yIn = inSource.getXAstrom(), inSource.getYAstrom()
                xOut, yOut = self._distortPosition(xIn, yIn, *args, **kwargs)
                outSource.setXAstrom(xOut)
                outSource.setYAstrom(yOut)
                output.append(outSource)
        elif isinstance(input, afwDet.Source):
            output = type(input)(input)
            xIn, yIn = input.getXAstrom(), input.getYAstrom()
            xOut, yOut = self._distortPosition(xIn, yIn, *args, **kwargs)
            output.setXAstrom(xOut)
            output.setYAstrom(yOut)
        elif isinstance(input, afwGeom.Point2D):
            output = type(input)(input)
            xIn, yIn = input.getX(), input.getY()
            xOut, yOut = self._distortPosition(xIn, yIn, *args, **kwargs)
            output.setX(xOut)
            output.setY(yOut)
        else:
            raise RuntimeError("Unrecognised type: %s" % str(type(input)))
        return output

    def actualToIdeal(self, actual):
        """Transform source or sources from actual coordinates to ideal coodinates.

        @param measured Source or sources with actual (detector) coordinates
        @returns Copy of source or sources with ideal coordinates
        """
        return self._distortSources(actual)

    def idealToActual(self, ideal):
        """Transform source or sources from ideal coordinates to actual coodinates.

        @param measured Source or sources with ideal coordinates
        @returns Copy of source or sources with actual (detector) coordinates
        """
        return self._distortSources(ideal)

def createDistortion(ccd, distConfig):
    """Create a suitable CameraDistortion object

    @param ccd Ccd for distortion (sets position relative to center)
    @param config Configuration for distortion
    @returns CameraDistortion specified by ccd and configuration
    """
    if distConfig.has_key('radial'):
        return RadialDistortion(ccd, distConfig['radial'])
    else:
        return NullDistortion()

class NullDistortion(CameraDistortion):
    """Class to implement no optical distortion."""
    def _distortPosition(self, x, y):
        """(Not really) distort a position.
        """
        return x, y


class RadialDistortion(CameraDistortion):
    def __init__(self, ccd, config):
        """Constructor

        @param ccd Ccd for distortion (sets position relative to center)
        @param config Configuration for distortion
        """
        self.coeffs = config['coeffs']
        self.a2i = config['actualToIdeal']
        self.step = config['step']

        position = ccd.getCenter()        # Centre of CCD on focal plane
        center = ccd.getSize() / ccd.getPixelSize() / 2.0 # Central pixel
        # Pixels from focal plane center to CCD corner
        self.x0 = position.getX() - center.getX()
        self.y0 = position.getY() - center.getY()

        bbox = ccd.getAllPixels()
        corners = ((bbox.getX0(), bbox.getY0()),
                   (bbox.getX0(), bbox.getY1()),
                   (bbox.getX1(), bbox.getY0()),
                   (bbox.getX1(), bbox.getY1()))
        cornerRadii = list()
        for c in corners:
            cornerRadii.append(math.hypot(c[0] + self.x0, c[1] + self.y0))
        self.minRadius = min(min(cornerRadii) - self.step, 0)
        self.maxRadius = max(cornerRadii) + self.step

        self._init()
        return

    def __getstate__(self):
        """Get state for pickling"""
        state = dict(self.__dict__)
        # Remove big, easily regenerated components
        del state['actual']
        del state['ideal']
        return state

    def __setstate__(self, state):
        """Restore state for unpickling"""
        for key, value in state.items():
            self.__dict__[key] = value
        self._init()
        return

    def _init(self):
        """Set up distortion lookup table"""
        poly = numpy.poly1d(self.coeffs, variable='r')
        fromRadii = numpy.arange(self.minRadius, self.maxRadius, self.step, dtype=float)
        toRadii = numpy.polyval(poly, fromRadii)

        if self.a2i:
            # Actual --> ideal
            self.actual = fromRadii
            self.ideal = toRadii
        else:
            # Ideal --> actual
            self.actual = toRadii
            self.ideal = fromRadii
            # Extend to cover minRadius --> maxRadius in actual space
            while self.actual[0] > self.minRadius:
                ideal = self.ideal[0] - self.step
                actual = numpy.polyval(poly, ideal)
                numpy.insert(self.ideal, 0, ideal)
                numpy.insert(self.actual, 0, actual)
            while self.actual[-1] < self.maxRadius:
                ideal = self.ideal[-1] + self.step
                actual = numpy.polyval(poly, ideal)
                numpy.insert(self.ideal, -1, ideal)
                numpy.insert(self.actual, -1, actual)
        return

    def _distortPosition(self, x, y, fromRadii, toRadii):
        """Distort/undistort a position.

        @param x X coordinate to distort
        @param y Y coordinate to distort
        @param fromRadii Vector of lookup table providing the source radii
        @param toRadii Vector of lookup table providing the target radii
        @returns Copy of input source with distorted/undistorted coordinates
        """
        x += self.x0
        y += self.y0
        theta = math.atan2(y, x)
        radius = math.hypot(x, y)
        if radius < fromRadii[0] or radius > fromRadii[-1]:
            raise RuntimeError("Radius (%f from %f,%f) is outside lookup table bounds (%f,%f)" %
                               (radius, x, y, fromRadii[0], fromRadii[-1]))
        r = numpy.interp(radius, fromRadii, toRadii)
        return r * math.cos(theta) - self.x0, r * math.sin(theta) - self.y0

    def actualToIdeal(self, sources):
        return self._distortSources(sources, self.actual, self.ideal)

    def idealToActual(self, sources):
        return self._distortSources(sources, self.ideal, self.actual)

