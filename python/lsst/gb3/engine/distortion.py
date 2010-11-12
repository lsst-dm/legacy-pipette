#!/usr/bin/env python

import os, math
import numpy
import lsst.afw.detection as afwDet

"""This module defines the CameraDistortion class, which calculates the effects of optical distortions."""

class CameraDistortion(object):
    """This is a base class for calculating the effects of optical distortions on a camera."""

    def _distortSource(self, inSource, *args, **kwargs):
        """Distort/undistort a single source.

        @param inSource Source to distort
        """
        raise NotImplementedError("Method for %s not implemented" % __name__)

    def _distortSources(self, inList, *args, **kwargs):
        """Common method to distort/undistort a source or sources.

        @param inList Source or iterable of sources to distort
        @returns Copy of source or sources with modified coordinates
        """
        if hasattr(inList, "__iter__"):
            outList = type(inList)()
            for inSource in inList:
                outList.append(self._distortSource(inSource, *args, **kwargs))
            return outList
        else:
            return self._distortSource(inList, *args, **kwargs)

    def measuredToDistorted(self, measured):
        """Transform source or sources from measured/detector coordinates to distorted coodinates.

        @param measured Source or sources with measured (detector) coordinates
        @returns Copy of source or sources with distorted coordinates
        """
        return self._distortSources(measured)

    def distortedToMeasured(self, distorted):
        """Transform source or sources from distorted coordinates to measured/detector coodinates.

        @param measured Source or sources with distorted coordinates
        @returns Copy of source or sources with 'measured' (detector) coordinates
        """
        return self._distortSources(distorted)


class NullDistortion(CameraDistortion):
    """Class to implement no optical distortion."""
    def _distortSource(self, source):
        """Distort a single source.

        @param source Source to apply no distortion to
        @returns Copy of source
        """
        return afwDet.Source(source)


class RadialDistortion(CameraDistortion):
    def __init__(self, coeffs, ccd, step=10.0):
        """Constructor

        @param coeffs Polynomial coefficients, from highest power to constant
        @param ccd Ccd for distortion (sets position relative to center)
        @param step Step size (pixels) for distortion lookup table
        """
        self.coeffs = coeffs

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
        self.minRadius = min(min(cornerRadii) - step, 0)
        self.maxRadius = max(cornerRadii) + step
        self.step = step

        self._init()
        return

    def __getstate__(self):
        """Get state for pickling"""
        state = dict(self.__dict__)
        # Remove big, easily regenerated components
        del state['radii']
        del state['distortions']
        return state

    def __setstate__(self, state):
        """Restore state for unpickling"""
        for key, value in state.items():
            self.__dict__[key] = value
        self._init()
        return

    def _init(self):
        """Set up distortion lookup table"""
        self.radii = numpy.arange(self.minRadius, self.maxRadius, self.step, dtype=float)
        poly = numpy.poly1d(self.coeffs, variable='r')
        self.distortions = numpy.polyval(poly, self.radii)
        return

    def _distortSource(self, inSource, fromRadii, toRadii):
        """Distort/undistort a single source.

        @param inSource Source to distort
        @param fromRadii Vector of lookup table providing the source radii
        @param toRadii Vector of lookup table providing the target radii
        @returns Copy of input source with distorted/undistorted coordinates
        """
        outSource = afwDet.Source(inSource)
        x = inSource.getXAstrom() + self.x0
        y = inSource.getYAstrom() + self.y0
        theta = math.atan2(y, x)
        r = numpy.interp(math.hypot(x, y), fromRadii, toRadii)
        outSource.setXAstrom(r * math.cos(theta) - self.x0)
        outSource.setYAstrom(r * math.sin(theta) - self.y0)
        return outSource

    def measuredToDistorted(self, measured):
        return self._distortSources(measured, self.radii, self.distortions)

    def distortedToMeasured(self, distorted):
        return self._distortSources(distorted, self.distortions, self.radii)

