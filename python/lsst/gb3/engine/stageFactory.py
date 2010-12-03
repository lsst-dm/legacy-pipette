#!/usr/bin/env python

from lsst.gb3.engine.stage import IgnoredStage

import lsst.gb3.engine.stages.apcorr as apcorr
import lsst.gb3.engine.stages.assembly as assembly
import lsst.gb3.engine.stages.ast as ast
import lsst.gb3.engine.stages.background as background
import lsst.gb3.engine.stages.bias as bias
import lsst.gb3.engine.stages.cal as cal
import lsst.gb3.engine.stages.cr as cr
import lsst.gb3.engine.stages.dark as dark
import lsst.gb3.engine.stages.defects as defects
import lsst.gb3.engine.stages.detect as detect
import lsst.gb3.engine.stages.detrend as detrend
import lsst.gb3.engine.stages.distortion as distortion
import lsst.gb3.engine.stages.fakePsf as fakePsf
import lsst.gb3.engine.stages.flat as flat
import lsst.gb3.engine.stages.fringe as fringe
import lsst.gb3.engine.stages.interpolate as interpolate
import lsst.gb3.engine.stages.measure as measure
import lsst.gb3.engine.stages.overscan as overscan
import lsst.gb3.engine.stages.psf as psf
import lsst.gb3.engine.stages.saturation as saturation
import lsst.gb3.engine.stages.trim as trim
import lsst.gb3.engine.stages.variance as variance


class StageFactory(object):
    stages = {'apcorr': apcorr.Apcorr,
              'assembly': assembly.Assembly,
              'ast': ast.Ast,
              'background': background.Background,
              'bias': bias.Bias,
              'cal': cal.Cal,
              'cr': cr.Cr,
              'dark': dark.Dark,
              'defects': defects.Defects,
              'detect': detect.Detect,
              'detrend': detrend.Detrend,
              'distortion': distortion.Distortion,
              'fakePsf': fakePsf.FakePsf,
              'flat': flat.Flat,
              'fringe': fringe.Fringe,
              'interpolate': interpolate.Interpolate,
              'measure': measure.Measure,
              'overscan': overscan.Overscan,
              'psf': psf.Psf,
              'saturation': saturation.Saturation,
              'trim': trim.Trim,
              'variance': variance.Variance,
              }

    @classmethod
    def _create(cls, stage, always=False, name=None, config=None, *args, **kwargs):
        if not cls.stages.has_key(stage):
            raise KeyError("Unknown stage name: %s" % stage)
        if name is None: name = stage
        if always or (config is not None and config['do'][name]):
            stageType = cls.stages[stage]
        else:
            stageType = IgnoredStage
        return stageType(name, config=config, *args, **kwargs)

    @classmethod
    def create(cls, stages, always=False, name=None, config=None, *args, **kwargs):
        if isinstance(stages, basestring):
            return cls._create(stages, always=always, name=name, config=config, *args, **kwargs)
        stageList = list()
        for stage in stages:
            stageList.append(cls._create(stage, always=always, name=name, config=config, *args, **kwargs))
        return stageList
