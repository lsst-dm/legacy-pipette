#!/usr/bin/env python

from lsst.pipette.engine.stage import BaseStage
import lsst.afw.image as afwImage

class Read(BaseStage):
    def __init__(self, name, which={"raw": "exposure"}, *args, **kwargs):
        provides = set(which.values())
        super(Read, self).__init__(name, requires=['ident', 'inButler'], provides=provides, *args, **kwargs)
        self.which = which
        return

    def run(self, ident=None, inButler=None, **clipboard):
        """Read products onto the clipboard
        """
        assert ident, "ident not provided"
        assert inButler, "inButler not provided"

        gotten = dict()
        for product, target in self.which.items():
            if product == "detrends":
                do = self.config['do']
                detrends = dict()
                if do['bias']:
                    self.log.log(self.log.INFO, "Reading bias for %s" % (ident))
                    detrends['bias'] = inButler.get('bias', ident)
                if do['dark']:
                    self.log.log(self.log.INFO, "Reading dark for %s" % (ident))
                    detrends['dark'] = inButler.get('dark', ident)
                if do['flat']:
                    self.log.log(self.log.INFO, "Reading flat for %s" % (ident))
                    detrends['flat'] = inButler.get('flat', ident)
                if do['fringe']:
                    self.log.log(self.log.INFO, "Reading fringe for %s" % (ident))
                    detrends['fringe'] = inButler.get('fringe', ident)
                gotten[target] = detrends
            else:
                self.log.log(self.log.INFO, "Reading %s for %s" % (product, ident))
                gotten[target] = inButler.get(product, ident)

                # Convert to floating-point
                # XXX This also appears to read the image, stepping around problems in the daf_persistence
                # readProxy
                if isinstance(gotten[target], afwImage.ExposureU):
                    gotten[target] = gotten[target].convertF()

        return gotten
