#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage
from lsst.pipette.engine.stageFactory import StageFactory

class Phot(MultiStage):
     """Photometry stage.
     Photometry consists of two separate stages (detect and measure) but
     we want to refer to them collectively, and we never want one without
     the other.
     """
     def __init__(self, name='phot', factory=StageFactory, *args, **kwargs):
        stages = factory.create(['detect',
                                 'measure',], always=True, *args, **kwargs)
        super(Phot, self).__init__(name, stages, *args, **kwargs)
        return
