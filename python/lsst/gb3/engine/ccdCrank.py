#!/usr/bin/env python

from lsst.gb3.engine.crank import Crank
from lsst.gb3.engine.isrCrank import IsrCrank
from lsst.gb3.engine.assemblyCrank import AssemblyCrank
from lsst.gb3.engine.bootstrapCrank import BootstrapCrank
from lsst.gb3.engine.charCrank import CharCrank
from lsst.gb3.engine.stage import Stage

class CcdCrank(Crank):
    def __init__(self, name=None, config=None, *args, **kwargs):
        super(CcdCrank, self).__init__(name=name, config=config, *args, **kwargs)
        self.stages = [Stage('isr', depends=['exposure', 'detrends'], always=True,
                             crank=IsrCrank(name=name, config=config)),
                       Stage('assembly', depends='exposure', always=True,
                            crank=AssemblyCrank(name=name, config=config)),
                       Stage('bootstrap', depends='exposure', always=True,
                             crank=BootstrapCrank(name=name, config=config)),
                       Stage('char', always=True, crank=CharCrank(name=name, config=config)),
                       ]
        self.cranks = dict(map(lambda stage: (stage.name, stage.crank), self.stages))
        return

    def _isr(self, exposure=None, detrends=None, **kwargs):
        assert exposure, "No exposure provided"
        assert detrends, "No detrend provided"

        crank = self.cranks['isr']
        processed = list()
        if hasattr(exposure, '__iter__'):
            assert hasattr(detrends, '__iter__') and len(exposure) == len(detrends), \
                   "Number of exposures (%d) and detrends (%d) differ" % (len(exposures), len(detrends))
            for exp, det in zip(exposure, detrends):
                clipboard = crank.turn(exposure=exp, detrends=det)
                processed.append(clipboard['exposure'])
        else:
            clipboard = crank.turn(exposure=exposure, detrends=detrends)
            processed.append(clipboard['exposure'])
        return {'exposure': processed}

    def _assembly(self, exposure=None, **kwargs):
        assert exposure, "No exposure provided"
        crank = self.cranks['assembly']
        clipboard = crank.turn(exposure=exposure)
        return clipboard
