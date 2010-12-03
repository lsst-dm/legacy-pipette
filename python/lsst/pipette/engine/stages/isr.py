#!/usr/bin/env python

from lsst.pipette.engine.stage import IterateMultiStage
from lsst.pipette.engine.stageFactory import StageFactory

class Isr(IterateMultiStage):
    def __init__(self, name='isr', factory=StageFactory, *args, **kwargs):
        stages = factory.create(['saturation',
                                 'overscan',], *args, **kwargs)
        stages += factory.create(['trim',], always=True, *args, **kwargs)
        stages += factory.create(['bias',], *args, **kwargs)
        stages += [factory.create('variance', always=True, *args, **kwargs)]
        stages += factory.create(['dark',
                                  'flat',
                                  'fringe',
                                  ], *args, **kwargs)
        iterate = ['exposure', 'detrends']
        super(Isr, self).__init__(name, iterate, stages, *args, **kwargs)
        return
