#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage
from lsst.pipette.engine.stageFactory import StageFactory

from lsst.pipette.engine.stages.isr import Isr
from lsst.pipette.engine.stages.bootstrap import Bootstrap
from lsst.pipette.engine.stages.phot import Phot
from lsst.pipette.engine.stages.characterize import Characterize

class CcdProcessing(MultiStage):
    """Processing of a single CCD."""
    def __init__(self, name='ccd', factory=None, *args, **kwargs):
        factory = StageFactory(factory, isr=Isr, bootstrap=Bootstrap, phot=Phot, char=Characterize)
        stages = factory.create(['isr',
                                 'bootstrap',
                                 'char'], always=True, *args, **kwargs)
        super(CcdProcessing, self).__init__(name, stages, *args, **kwargs)
        return
   
