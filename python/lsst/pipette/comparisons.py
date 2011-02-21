#!/usr/bin/env python

import numpy

def magnitude(value):
    try:
        value = -2.5 * math.log10(value)
    except OverflowError:
        value = float('NAN')
    return value

class Comparisons(object):
    def __init__(self, matches):
        self.keys = ['distance', 'ra', 'dec', 'psfDiff', 'psfAvg', 'apDiff',
                     'apAvg', 'flags', 'first', 'second', 'index']
        self.num = len(matches)
        self.first = list()
        self.second = list()
        self.distance = numpy.ndarray(self.num)
        self.ra1 = numpy.ndarray(self.num)
        self.dec1 = numpy.ndarray(self.num)
        self.ra2 = numpy.ndarray(self.num)
        self.dec2 = numpy.ndarray(self.num)
        self.psf1  = numpy.ndarray(self.num)
        self.psf2 = numpy.ndarray(self.num)
        self.ap1 = numpy.ndarray(self.num)
        self.ap2 = numpy.ndarray(self.num)
        self.flags1 = numpy.ndarray(self.num, dtype=int)
        self.flags2 = numpy.ndarray(self.num, dtype=int)

        for index, match in enumerate(matches):
            first = match.first
            second = match.second
            distance = match.distance
            self.ra1[index], self.dec1[index] = first.getRa(), first.getDec()
            self.ra2[index], self.dec2[index] = second.getRa(), second.getDec()
            self.psf1[index] = first.getPsfFlux()
            self.psf2[index] = second.getPsfFlux()
            self.ap1[index] = first.getApFlux()
            self.ap2[index] = second.getApFlux()
            self.flags1[index] = first.getFlagForDetection()
            self.flags2[index] = second.getFlagForDetection()

        self.index = numpy.arange(len(matches))
        self.ra = (self.ra1 + self.ra2) / 2.0
        self.dec = (self.dec1 + self.dec2) / 2.0
        self.psf1 = -2.5 * numpy.log10(self.psf1)
        self.psf2 = -2.5 * numpy.log10(self.psf2)
        self.ap1 = -2.5 * numpy.log10(self.ap1)
        self.ap2 = -2.5 * numpy.log10(self.ap2)
        self.psfAvg = (self.psf1 + self.psf2) / 2.0
        self.psfDiff = self.psf1 - self.psf2
        self.apAvg = (self.ap1 + self.ap2) / 2.0
        self.apDiff = self.ap1 - self.ap2
        self.flags = self.flags1 | self.flags2
        return

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
