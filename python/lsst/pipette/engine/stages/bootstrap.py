#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage, IgnoredStage
from lsst.pipette.engine.stageFactory import StageFactory, StageDict
from lsst.pipette.engine.stages.cr import Cr
from lsst.pipette.engine.stages.detect import Detect
from lsst.pipette.engine.stages.phot import Phot

class BootstrapCr(Cr):
    def run(self, **kwargs):
        return super(BootstrapCr, self).run(keepCRs=True, **kwargs)

class BootstrapDetect(Detect):
    def run(self, **kwargs):
        super(BootstrapDetect, self).run(thresold=self.config['bootstrap']['thresholdValue'], **kwargs)

class BootstrapStageFactory(StageFactory):
    stages = StageFactory.stages.copy()
    stages['cr'] = BootstrapCr
    stages['detect'] = BootstrapDetect
    stages['phot'] = Phot
    stages = StageDict(stages)

class Bootstrap(MultiStage):
    def __init__(self, name='bootstrap', factory=BootstrapStageFactory, *args, **kwargs):
        stages = [factory.create('assembly', always=True, *args, **kwargs)]
        stages += factory.create(['defects',
                                  'background',], *args, **kwargs)
        stages += [factory.create('fakePsf', always=True, *args, **kwargs)]
        stages += factory.create(['interpolate',
                                  'cr',
                                  'phot',], *args, **kwargs)
        if not isinstance(stages[-1], IgnoredStage):
            stages += factory.create(['psf',
                                      'apcorr',], always=True, *args, **kwargs)
        super(Bootstrap, self).__init__(name, stages, *args, **kwargs)
        return
