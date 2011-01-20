#!/usr/bin/env python

import re
import os
import numpy

import lsst.pipette.config as pipConfig

"""This module is for writing catalog files from source lists"""

class Catalog(object):
    """A Catalog is for writing catalog files from source lists"""
    def __init__(self, config, allowNonfinite=True):
        """Initialisation

        @param config Configuration specifying format styles
        @param allowNonfinite Boolean indicating whether non-finite values should be written as NaN
        """
        if not isinstance(config, pipConfig.Config):
            config = pipConfig.Config(config)
        self.config = config
        self.allowNonfinite = allowNonfinite
        return

    def writeSourcesHeader(self, style, header=None):
        """Write header for source catalog

        @param style Format style
        @param header Dict with header information
        """
        s = ""
        if header is not None:
            for key, value in header.items():
                s += "# %s = %s\n" % (key, str(value))
        s += "# "
        columns = self.config[style]
        for column in columns.keys():
            s += column + ' '
        return s

    def writeSources(self, filename, sources, style, header=None):
        """Write source catalog

        @param filename File name for output
        @param sources Sources to write
        @param style Format style
        @param header Header information
        """
        fd = self._open(filename)
        print >> fd, self.writeSourcesHeader(style, header=header)

        columns = self.config[style]
        for source in sources:
            s = ""
            print >> fd, self._writeSource(source, columns)
        return

    def writeMatchesHeader(self, style, header=None):
        """Write match catalog header

        @param style Format style
        @param header Dict with header information
        """
        s = ""
        if header is not None:
            for key, value in header.items():
                s += "# %s = %s\n" % (key, str(value))
        s += "# "
        columns = self.config[style]
        for extra in ['_1', '_2']:
            for column in columns.keys():
                s += column + extra + ' '
        return s

    def writeMatches(self, filename, matches, style, header=None):
        """Write match catalog

        @param filename File name for output
        @param matches Matches to write
        @param style Format style
        @param header Header information
        """
        fd = self._open(filename)
        print >> fd, self.writeMatchesHeader(style, header=header)

        columns = self.config[style]
        for match in matches:
            s = ""
            for source in [match.first, match.second]:
                s += self._writeSource(source, columns)
            print >> fd, s
        return

    def _open(self, filename):
        """Open file for writing

        @param filename File name for output
        """
        directory = os.path.dirname(filename)
        if not os.path.exists(directory):
            os.makedirs(directory)
        fd = open(filename, "w")
        return fd

    def _writeSource(self, source, columns):
        """Write source values (to string)

        @param source Source for writing
        @param columns Dict with column specifications
        @returns string with source values
        """
        s = ""
        for column in columns.keys():
            colData = columns[column]
            getFunc = getattr(source, colData['get'])
            formatSpec = colData['format']
            value = getFunc()
            if numpy.isfinite(value) or self.allowNonfinite:
                s += formatSpec % getFunc() + " "
            else:
                s += '\"\" '
        return s
