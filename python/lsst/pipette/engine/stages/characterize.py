#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage
from lsst.pipette.engine.stageFactory import StageFactory, StageDict
from lsst.pipette.engine.stages.phot import Phot

class CharacterizeStageFactory(StageFactory):
    stages = StageFactory.stages.copy()
    stages['phot'] = Phot
    stages = StageDict(stages)
    

class Characterize(MultiStage):
    def __init__(self, name='char', factory=CharacterizeStageFactory, *args, **kwargs):
        stages = ['phot',
                  'ast',
                  'cal']
        super(Characterize, self).__init__(name, stages, factory=factory, *args, **kwargs)
        return
