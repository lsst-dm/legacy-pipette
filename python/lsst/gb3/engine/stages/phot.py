#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage
from lsst.pipette.engine.stageFactory import StageFactory

class Phot(MultiStage):
     def __init__(self, name='phot', factory=StageFactory, *args, **kwargs):
        stages = factory.create(['detect',
                                 'measure',], always=True, *args, **kwargs)
        super(Phot, self).__init__(name, stages, *args, **kwargs)
        return
