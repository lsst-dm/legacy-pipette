#!/usr/bin/env python

from lsst.pipette.stage import MultiStage
from lsst.pipette.stageFactory import StageFactory

class Phot(MultiStage):
     """Photometry stage.
     Photometry consists of two separate stages (detect and measure) but
     we want to refer to them collectively, and we never want one without
     the other.
     """
     def __init__(self, name='phot', factory=None, *args, **kwargs):
          factory = StageFactory(factory)
          stages = factory.create(['detect',
                                   'measure',], always=True, *args, **kwargs)
          super(Phot, self).__init__(name, stages, *args, **kwargs)
          return
