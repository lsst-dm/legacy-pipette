#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage
from lsst.pipette.engine.stageFactory import StageFactory, StageDict

from lsst.pipette.engine.stages.isr import Isr
from lsst.pipette.engine.stages.bootstrap import Bootstrap
from lsst.pipette.engine.stages.phot import Phot
from lsst.pipette.engine.stages.characterize import Characterize

class CcdStageFactory(StageFactory):
    stages = StageFactory.stages.copy()
    stages.update({'isr': Isr,
                   'bootstrap': Bootstrap,
                   'phot': Phot,
                   'char': Characterize,
                   })
    stages = StageDict(stages)

class CcdProcessing(MultiStage):
    def __init__(self, name='ccd', *args, **kwargs):
        stages = CcdStageFactory.create(['isr',
                                         'bootstrap',
                                         'char'], always=True, *args, **kwargs)
        super(CcdProcessing, self).__init__(name, stages, *args, **kwargs)
        return
   
