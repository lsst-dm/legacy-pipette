#!/usr/bin/env python

import lsstDebug
import lsst.pex.logging as pexLog
import lsst.afw.detection as afwDet
import lsst.afw.image as afwImage
import lsst.afw.display.ds9 as ds9
import lsst.ip.isr as ipIsr
import lsst.pipette.engine.util as engUtil

"""This module defines the base class for processes."""

class Process(object):
    def __init__(self, config=None, log=None):
        self.config = config
        if log is None: log = pexLog.getDefaultLog()
        self.log = pexLog.Log(log, self.__class__.__name__)
        self._display = lsstDebug.Info(__name__).display
        return


    def run(self):
        raise NotImplementedError("This method needs to be provided by the subclass.")


    def read(self, butler, ident, productList):
        """Read products

        @param butler Data butler
        @param ident Identifier for data
        @param productList List of products to read
        @return List of products
        """
        assert butler, "butler not provided"
        assert ident, "ident not provided"
        assert productList, "productList not provided"

        gotten = list()
        for product in productList:
            if product == "detrends":
                do = self.config['do']
                detrends = dict()
                if do['bias']:
                    self.log.log(self.log.INFO, "Reading bias for %s" % (ident))
                    detrends['bias'] = butler.get('bias', ident)
                if do['dark']:
                    self.log.log(self.log.INFO, "Reading dark for %s" % (ident))
                    detrends['dark'] = butler.get('dark', ident)
                if do['flat']:
                    self.log.log(self.log.INFO, "Reading flat for %s" % (ident))
                    detrends['flat'] = butler.get('flat', ident)
                if do['fringe']:
                    self.log.log(self.log.INFO, "Reading fringe for %s" % (ident))
                    detrends['fringe'] = butler.get('fringe', ident)
                gotten.append(detrends)
            else:
                self.log.log(self.log.INFO, "Reading %s for %s" % (product, ident))
                data = butler.get(product, ident)

                # Convert to floating-point
                # XXX This also appears to read the image, stepping around problems in the daf_persistence
                # readProxy
                if isinstance(data, afwImage.ExposureU):
                    data = data.convertF()

                gotten.append(data)

        return gotten


    def write(self, butler, ident, productDict):
        """Write products

        @param butler Data butler
        @param ident Identifier for data
        @param productDict
        """
        assert butler, "butler not provided"
        assert ident, "ident not provided"
        assert productDict, "productDict not provided"

        for product, source in productDict.items():
            butler.put(source, product, ident)
            self.log.log(self.log.INFO, "Writing %s: %s" % (product, ident))
        return


    def display(self, name, exposure=None, sources=None, matches=None, pause=None):
        """Display image and/or sources

        @param name Name of product to display
        @param exposure Exposure to display, or None
        @param sources Sources to display, or None
        @param matches Matches to display, or None
        @param pause Pause execution?
        """
        if not self._display or not self._display.has_key(name) or self._display <= 0:
            return

        if isinstance(self._display, int):
            frame = self._display
        elif isinstance(self._display, dict):
            frame = self._display[name]
        else:
            frame = 1

        if exposure:
            if isinstance(exposure, list):
                if len(exposure) == 1:
                    exposure = exposure[0]
                else:
                    exposure = ipIsr.assembleCcd(exposure, engUtil.getCcd(exposure[0]))
            mi = exposure.getMaskedImage()
            ds9.mtv(mi, frame=frame, title=name)
            x0, y0 = mi.getX0(), mi.getY0()
        else:
            x0, y0 = 0, 0

        if sources and isinstance(sources, afwDet.SourceSet) or isinstance(sources, list):
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
