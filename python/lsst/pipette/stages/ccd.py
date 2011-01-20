#!/usr/bin/env python

from lsst.pipette.stage import MultiStage
from lsst.pipette.stageFactory import StageFactory

from lsst.pipette.stages.isr import Isr
from lsst.pipette.stages.bootstrap import Bootstrap
from lsst.pipette.stages.phot import Phot
from lsst.pipette.stages.characterize import Characterize

class CcdProcessing(MultiStage):
    """Processing of a single CCD."""
    def __init__(self, name='ccd', factory=None, *args, **kwargs):
        factory = StageFactory(factory, isr=Isr, bootstrap=Bootstrap, phot=Phot, char=Characterize)
        stages = factory.create(['isr',
                                 'bootstrap',
                                 'char'], always=True, *args, **kwargs)
        super(CcdProcessing, self).__init__(name, stages, *args, **kwargs)
        return
   
