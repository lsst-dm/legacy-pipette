#!/usr/bin/env python

import lsstDebug
import lsst.pex.logging as pexLog
import lsst.afw.detection as afwDet
import lsst.afw.image as afwImage
import lsst.afw.display.ds9 as ds9
import lsst.ip.isr as ipIsr
import lsst.pipette.util as pipUtil

"""This module defines the base class for processes."""

class Process(object):
    def __init__(self, config=None, log=None):
        self.config = config
        if log is None: log = pexLog.getDefaultLog()
        self.log = pexLog.Log(log, self.__class__.__name__)
        self._display = lsstDebug.Info(__name__).display

    def run(self):
        raise NotImplementedError("This method needs to be provided by the subclass.")


    def read(self, butler, ident, productList, ignore=False):
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
                do = self.config['do']['isr']
                detrends = dict()

                for kind in ('bias', 'dark', 'flat'):
                    if do[kind]:
                        if not butler.datasetExists(kind, ident):
                            if not ignore:
                                raise RuntimeError("Data type %s does not exist for %s" % (kind, ident))
                            continue
                        self.log.log(self.log.INFO, "Reading %s for %s" % (kind, ident))
                        detrend = butler.get(kind, ident)
                        detrends[kind] = detrend
                # Fringe depends on the filter
                if do['fringe'] and config.has_key('fringe') and config['fringe'].has_key('filters'):
                    filterList = butler.queryMetadata("raw", None, "filter", ident)
                    assert len(filterList) == 1, "Filter query is non-unique: %s" % filterList
                    filtName = filterList[0]
                    if filtName in config['fringe']['filters']:
                        if not butler.datasetExists('fringe', ident):
                            if not ignore:
                                raise RuntimeError("Data type fringe does not exist for %s" % ident)
                            continue
                        self.log.log(self.log.INFO, "Reading fringe for %s" % (ident))
                        fringe = butler.get("fringe", ident)
                        detrends['fringe'] = fringe
                gotten.append(detrends)
            else:
                if not butler.datasetExists(product, ident):
                    if not ignore:
                        raise RuntimeError("Data type %s does not exist for %s" % (product, ident))
                    continue
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


    def display(self, name, exposure=None, sources=[], matches=None, pause=None, prompt=None):
        """Display image and/or sources

        @param name Name of product to display
        @param exposure Exposure to display, or None
        @param sources list of sets of Sources to display, or []
        @param matches Matches to display, or None
        @param pause Pause execution?
        """
        if not self._display or not self._display.has_key(name) or self._display < 0 or \
               self._display in (False, None) or \
               self._display[name] in (False, None) or self._display[name] < 0:
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
                    exposure = ipIsr.assembleCcd(exposure, pipUtil.getCcd(exposure[0]))
            mi = exposure.getMaskedImage()
            ds9.mtv(mi, frame=frame, title=name)
            x0, y0 = mi.getX0(), mi.getY0()
        else:
            x0, y0 = 0, 0

        try:
            sources[0][0]
        except IndexError:              # empty list
            pass
        except TypeError:               # not a list of sets of sources
            sources = [sources]
            
        ctypes = [ds9.GREEN, ds9.RED, ds9.BLUE]
        for i, ss in enumerate(sources):
            try:
                ds9.buffer()
            except AttributeError:
                ds9.cmdBuffer.pushSize()

            for source in ss:
                xc, yc = source.getXAstrom() - x0, source.getYAstrom() - y0
                ds9.dot("o", xc, yc, size=4, frame=frame, ctype=ctypes[i%len(ctypes)])
                #try:
                #    mag = 25-2.5*math.log10(source.getPsfFlux())
                #    if mag > 15: continue
                #except: continue
                #ds9.dot("%.1f" % mag, xc, yc, frame=frame, ctype="red")
            try:
                ds9.buffer(False)
            except AttributeError:
                ds9.cmdBuffer.popSize()

        if matches:
            try:
                ds9.buffer()
            except AttributeError:
                ds9.cmdBuffer.pushSize()

            for match in matches:
                first = match.first
                x1, y1 = first.getXAstrom() - x0, first.getYAstrom() - y0
                ds9.dot("+", x1, y1, size=8, frame=frame, ctype="yellow")
                second = match.second
                x2, y2 = second.getXAstrom() - x0, second.getYAstrom() - y0
                ds9.dot("x", x2, y2, size=8, frame=frame, ctype="red")
            try:
                ds9.buffer(False)
            except AttributeError:
                ds9.cmdBuffer.popSize()

        if pause:
            if prompt is None:
                prompt = "%s: Enter or c to continue [chp]: " % name
            while True:
                ans = raw_input(prompt).lower()
                if ans in ("", "c",):
                    break
                if ans in ("p",):
                    import pdb; pdb.set_trace()
                elif ans in ("h", ):
                    print "h[elp] c[ontinue] p[db]"
                    
        return
