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

import lsstDebug
import lsst.pex.logging as pexLog
import lsst.afw.display.ds9 as ds9
import lsst.gb3.engine.config as engConfig


"""This module defines the Crank base class for LSST Algorithms testing (Green Blob 3)."""

class Crank(object):

    """Crank is a base class for LSST Algorithms testing (Green Blob 3).


    Public method: turn
    """

    def __init__(self,                  # Crank
                 name=None,             # Base name for outputs
                 config=None,           # Configuration
                 **kwargs               # Keyword arguments
                 ):
        self.name = name
        self.log = pexLog.Log(pexLog.getDefaultLog(), "Crank")
        self.config = engConfig.configuration() if config is None else config
        self.stages = []                # List of stages that may be performed
        self.do = self.config['do']     # Dict of stages and desire that they be performed
        self.display = lsstDebug.Info(__name__).display
        self._clipboard = kwargs        # Arguments for crank methods
        return

    def turn(self, **clipboard):
        clipboard.update(self._clipboard)
        for stage in self.stages:
            if not stage.always and not self.do[stage.name]:
                self.log.log(self.log.DEBUG, "Not performing stage %s (%s,%s)" % (stage.name, stage.always, self.do[stage.name]))
                continue
            if not stage.checkDepend(clipboard):
                self.log.log(self.log.DEBUG, "Dependencies not met for stage %s" % stage.name)
                continue
            self._turn(stage, clipboard)
        return clipboard


    def _turn(self, stage, clipboard):
        self.log.log(self.log.DEBUG, "Performing stage %s" % stage.name)
        method = '_' + stage.name       # Name of method to run
        if hasattr(self, method):
            func = getattr(self, method)
            ret = func(**clipboard)
        elif stage.crank is not None:
            ret = stage.crank.turn(**clipboard)
        else:
            raise RuntimeError("Can't determine how to execute stage %s" % stage.name)
        if ret is not None:
            if isinstance(ret, dict):
                clipboard.update(ret)
            else:
                raise RuntimeError("Unrecognised return value for stage %s: %s" % (stage.name, ret))
        self._display(stage, **clipboard)
        return


    def _display(self, name, exposure=None, sources=None, matches=None, pause=False, **kwargs):
        """Display image and/or sources

        @param name Name for display dict
        @param exposure Exposure to display, or None
        @param sources Sources to display, or None
        """
        if not self.display or not self.display.has_key(name) or self.display[name] <= 0:
            return
        frame = self.display[name]

        if exposure:
            mi = exposure.getMaskedImage()
            ds9.mtv(mi, frame=frame, title=name)
            x0, y0 = mi.getX0(), mi.getY0()
        else:
            x0, y0 = 0, 0

        if sources:
            for source in sources:
                xc, yc = source.getXAstrom() - x0, source.getYAstrom() - y0
                ds9.dot("o", xc, yc, size=4, frame=frame)
                #try:
                #    mag = 25-2.5*math.log10(source.getPsfFlux())
                #    if mag > 15: continue
                #except: continue
                #ds9.dot("%.1f" % mag, xc, yc, frame=frame, ctype="red")

        if matches:
            for match in matches:
                first = match.first
                x1, y1 = first.getXAstrom() - x0, first.getYAstrom() - y0
                ds9.dot("+", x1, y1, size=8, frame=frame, ctype="yellow")
                second = match.second
                x2, y2 = second.getXAstrom() - x0, second.getYAstrom() - y0
                ds9.dot("x", x2, y2, size=8, frame=frame, ctype="red")

        if pause:
            raw_input("Press [ENTER] when ready....")
        return

