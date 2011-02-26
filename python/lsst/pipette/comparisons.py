#!/usr/bin/env python

import numpy
import numpy.ma as ma

import lsst.afw.detection as afwDet

def magnitude(value):
    try:
        value = -2.5 * math.log10(value)
    except OverflowError:
        value = float('NAN')
    return value

class Comparisons(object):
    def __init__(self, sources1, sources2, matchTol=1.0):
        self.keys = ['distance', 'ra1', 'ra2', 'dec1', 'dec2', 'x1', 'y1', 'x2', 'y2',
                     'psf1', 'psf2', 'ap1', 'ap2', 'flags1', 'flags2', 'index']
        matches = afwDet.matchRaDec(sources1, sources2, matchTol)
        self.num = len(matches)

        # Set up arrays
        for name, method in (('ra', 'getRa'),
                             ('dec', 'getDec'),
                             ('x', 'getXAstrom'),
                             ('y', 'getYAstrom'),
                             ('psf', 'getPsfFlux'),
                             ('ap', 'getApFlux'),
                             ('flags', 'getFlagForDetection'),
                             ):
            name1 = name + '1'
            name2 = name + '2'
            array1 = numpy.ndarray(self.num)
            array2 = numpy.ndarray(self.num)
            for i, m in enumerate(matches):
                first = match.first
                second = match.second
                array1[i] = getattr(first, method)()
                array2[i] = getattr(second, method)()
            setattr(self, name1, array1)
            setattr(self, name2, array2)

        self.distance = numpy.array([m.distance for m in matches])
        self.index = ma.MaskedArray(numpy.arange(self.num))

    def __getitem__(self, key):
        if isinstance(key, basestring) and key in self.keys:
            return getattr(self, key)
        elif isinstance(key, int):
            values = dict()
            for k in self.keys:
                value = self[k]
                values[k] = value[key]
            return values
        else:
            raise KeyError("Unrecognised key: %s" % key)

    def __setitem__(self, key, value):
        raise NotImplementedError("Not yet mutable.")
