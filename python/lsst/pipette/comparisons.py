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
    def __init__(self, sources1, sources2, calib=None, matchTol=1.0, flags=0x80, bright=None):
        self.keys = ['distance', 'ra', 'dec', 'ra1', 'ra2', 'dec1', 'dec2', 'x1', 'y1', 'x2', 'y2',
                     'psfDiff', 'psfAvg', 'psf1', 'psf2',
                     'apDiff', 'apAvg', 'ap1', 'ap2',
                     'flags', 'index']

        matches = afwDet.matchRaDec(sources1, sources2, matchTol)
        self.num = len(matches)

        # Set up arrays
        for name in ('distance', 'ra1', 'dec1', 'ra2', 'dec2', 'x1', 'y1', 'x2', 'y2',
                     'psf1', 'psf2', 'ap1', 'ap2'):
            array = numpy.ndarray(self.num)
            array = ma.MaskedArray(array)
            setattr(self, name, array)
        for name in ('flags1', 'flags2'):
            array = numpy.ndarray(self.num, dtype=int)
            array = ma.MaskedArray(array)
            setattr(self, name, array)

        if bright is not None and calib is not None:
            bright = 10.0**(-0.4*bright)

        # Fill arrays
        index = 0
        for match in matches:
            first = match.first
            second = match.second
            flags1 = first.getFlagForDetection()
            flags2 = second.getFlagForDetection()
            if not (flags1 & flags) or not (flags2 & flags):
                continue

            ap1 = first.getApFlux()
            ap2 = second.getApFlux()
            psf1 = first.getPsfFlux()
            psf2 = second.getPsfFlux()
            if calib is not None:
                try:
                    ap1 = calib.getMagnitude(ap1)
                    ap2 = calib.getMagnitude(ap2)
                    psf1 = calib.getMagnitude(psf1)
                    psf2 = calib.getMagnitude(psf2)
                except:
                    continue
                if bright is not None and (ap1 > bright or ap2 > bright):
                    continue
            elif if bright is not None and (ap1 < bright or ap2 < bright):
                continue

            self.flags1[index] = flags1
            self.flags2[index] = flags2
            self.ap1[index] = ap1
            self.ap2[index] = ap2
            self.psf1[index] = psf1
            self.psf2[index] = psf2

            self.distance[index] = match.distance
            self.ra1[index], self.dec1[index] = first.getRa(), first.getDec()
            self.ra2[index], self.dec2[index] = second.getRa(), second.getDec()
            self.x1[index], self.y1[index] = first.getXAstrom(), first.getYAstrom()
            self.x2[index], self.y2[index] = second.getXAstrom(), second.getYAstrom()

            index += 1
        self.num = index

        # Set up derived quantities
        self.index = ma.MaskedArray(numpy.arange(self.num))
        self.flags = self.flags1 | self.flags2
        self.ra = (self.ra1 + self.ra2) / 2.0
        self.dec = (self.dec1 + self.dec2) / 2.0

        if calib is None:
            self.psf1 = -2.5 * numpy.log10(self.psf1)
            self.psf2 = -2.5 * numpy.log10(self.psf2)
            self.ap1 = -2.5 * numpy.log10(self.ap1)
            self.ap2 = -2.5 * numpy.log10(self.ap2)

        self.psfAvg = (self.psf1 + self.psf2) / 2.0
        self.psfDiff = self.psf1 - self.psf2
        self.apAvg = (self.ap1 + self.ap2) / 2.0
        self.apDiff = self.ap1 - self.ap2

        # Mask out uninteresting data
        mask = (self.flags & flags)
        mask = ma.masked_equal(mask, 0)
        if bright is not None:
            good = ma.masked_greater(numpy.ma.MaskedArray(self.apAvg), bright)
            mask = ma.mask_or(mask.mask, good.mask)
        for name in self.keys:
            array = getattr(self, name)
            array.mask = mask
            setattr(self, name, array.compressed())

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
