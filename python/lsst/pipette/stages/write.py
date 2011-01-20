#!/usr/bin/env python

from lsst.pipette.stage import BaseStage

class Write(BaseStage):
    def __init__(self, name, which={'postISRCCD': 'exposure'}, *args, **kwargs):
        requires = ['outButler', 'ident'] + which.values()
        super(Write, self).__init__(name, requires=requires, *args, **kwargs)
        self.which = which
        return

    def run(self, outButler=None, ident=None, **clipboard):
        """Write products from the clipboard
        """
        assert outButler, "outButler not provided"
        assert ident, "ident not provided"

        for product, source in self.which.items():
            outButler.put(clipboard[source], product, ident)
            self.log.log(self.log.INFO, "Writing %s from %s: %s" % (product, source, ident))
        return
