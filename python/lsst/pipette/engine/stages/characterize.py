#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage
from lsst.pipette.engine.stageFactory import StageFactory
from lsst.pipette.engine.stages.phot import Phot

class CharacterizeStageFactory(StageFactory):
    stages = StageFactory.stages.copy()
    stages['phot'] = Phot
    

class Characterize(MultiStage):
    def __init__(self, name='char', factory=CharacterizeStageFactory, *args, **kwargs):
        stages = ['phot',
                  'ast',
                  'cal']
        super(Characterize, self).__init__(name, stages, factory=factory, *args, **kwargs)
        return
