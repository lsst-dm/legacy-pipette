#!/usr/bin/env python

from lsst.pipette.engine.stage import MultiStage, IgnoredStage
from lsst.pipette.engine.stageFactory import StageFactory
from lsst.pipette.engine.stages.cr import CrIdentify
from lsst.pipette.engine.stages.detect import DetectBright
from lsst.pipette.engine.stages.phot import Phot

class Bootstrap(MultiStage):
    """Bootstrap stage involves putting inputs together and measuring the PSF."""
    def __init__(self, name='bootstrap', factory=None, *args, **kwargs):
        factory = StageFactory(factory, cr=CrIdentify, detect=DetectBright)
        stages = [factory.create('assembly', always=True, *args, **kwargs)]
        stages += factory.create(['defects',
                                  'background',], *args, **kwargs)
        stages += [factory.create('fakePsf', always=True, *args, **kwargs)]
        stages += factory.create(['interpolate',
                                  'cr',], *args, **kwargs)
        photStage = factory.create('phot', *args, **kwargs)
        stages += [photStage]
        if not isinstance(photStage, IgnoredStage):
            stages += factory.create(['psf',
                                      'apcorr',
                                      ], always=True, *args, **kwargs)
        super(Bootstrap, self).__init__(name, stages, *args, **kwargs)
        return
