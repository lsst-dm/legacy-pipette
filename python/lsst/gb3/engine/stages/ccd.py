#!/usr/bin/env python

from lsst.gb3.engine.stage import MultiStage
from lsst.gb3.engine.stageFactory import StageFactory

from lsst.gb3.engine.stages.isr import Isr
from lsst.gb3.engine.stages.bootstrap import Bootstrap
from lsst.gb3.engine.stages.phot import Phot
from lsst.gb3.engine.stages.characterize import Characterize

class CcdStageFactory(StageFactory):
    stages = StageFactory.stages.copy()
    stages.update({'isr': Isr,
                   'bootstrap': Bootstrap,
                   'phot': Phot,
                   'char': Characterize,
                   })

class CcdProcessing(MultiStage):
    def __init__(self, name='ccd', *args, **kwargs):
        stages = CcdStageFactory.create(['isr',
                                         'bootstrap',
                                         'char'], always=True, *args, **kwargs)
        super(CcdProcessing, self).__init__(name, stages, *args, **kwargs)
        return
   
