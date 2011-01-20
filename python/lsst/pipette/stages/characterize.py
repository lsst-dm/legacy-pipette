#!/usr/bin/env python

from lsst.pipette.stage import MultiStage
from lsst.pipette.stageFactory import StageFactory
from lsst.pipette.stages.phot import Phot

class Characterize(MultiStage):
    def __init__(self, name='char', factory=None, *args, **kwargs):
        factory = StageFactory(factory, phot=Phot)
        stages = ['interpolate',
                  'cr',
                  'phot',
                  'distortion',
                  'ast',
                  'cal']
        super(Characterize, self).__init__(name, stages, factory=factory, *args, **kwargs)
        return
