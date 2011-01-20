#!/usr/bin/env python

from lsst.pipette.engine.stage import IgnoredStage

import lsst.pipette.engine.stages.apcorr as apcorr
import lsst.pipette.engine.stages.assembly as assembly
import lsst.pipette.engine.stages.ast as ast
import lsst.pipette.engine.stages.background as background
import lsst.pipette.engine.stages.bias as bias
import lsst.pipette.engine.stages.cal as cal
import lsst.pipette.engine.stages.cr as cr
import lsst.pipette.engine.stages.dark as dark
import lsst.pipette.engine.stages.defects as defects
import lsst.pipette.engine.stages.detect as detect
import lsst.pipette.engine.stages.detrend as detrend
import lsst.pipette.engine.stages.distortion as distortion
import lsst.pipette.engine.stages.fakePsf as fakePsf
import lsst.pipette.engine.stages.flat as flat
import lsst.pipette.engine.stages.fringe as fringe
import lsst.pipette.engine.stages.interpolate as interpolate
import lsst.pipette.engine.stages.measure as measure
import lsst.pipette.engine.stages.overscan as overscan
import lsst.pipette.engine.stages.psf as psf
import lsst.pipette.engine.stages.saturation as saturation
import lsst.pipette.engine.stages.trim as trim
import lsst.pipette.engine.stages.variance as variance


class StageFactory(object):
    """A StageFactory creates Stages from a name."""

    def __init__(self, *args, **kwargs):
        self._stages = None
        if args is not None:
            # Creating 
            if len(args) > 1:
                raise RuntimeError("Unable to interpret arguments")
            source = args[0]
            if source is not None:
                assert isinstance(source, StageFactory), "Cannot construct from %s" % type(source)
                self._stages = source._stages.copy()

        if self._stages is None:
            self._stages = {'apcorr': apcorr.Apcorr,
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

        self._stages.update(kwargs)
        return

    def add(self, **definitions):
        self._stages.update(definitions)
        return self

    def copy(self):
        return self.__new__(self.__class__, **self._stages)

    def __getitem__(self, name):
        return self._stages[name]

    def __setitem__(self, name, value):
        self._stages[name] = value
        return

    def _create(self, stage, always=False, name=None, config=None, *args, **kwargs):
        """Create a single stage

        @param stage Stage name
        @param always Always execute this stage (user can't choose)?
        @param name Name to give stage
        @param config Configuration for stage
        @param *args,**kwargs Additional arguments passed to stage
        """
        if not self._stages.has_key(stage):
            raise KeyError("Unknown stage name: %s" % stage)
        if name is None: name = stage
        if always or (config is not None and config['do'][name]):
            stageType = self._stages[stage]
        else:
            stageType = IgnoredStage
        if not 'factory' in kwargs:
            kwargs['factory'] = self
        return stageType(name, config=config, *args, **kwargs)

    def create(self, stages, always=False, name=None, config=None, *args, **kwargs):
        """Create one or more stages

        @param stages Stage name or list of stage names
        @param always Always execute these stages (user can't choose)?
        @param name Name to give stage
        @param config Configuration for stage
        @param *args,**kwargs Additional arguments passed to stage
        """
        if isinstance(stages, basestring):
            return self._create(stages, always=always, name=name, config=config, *args, **kwargs)
        stageList = list()
        for stage in stages:
            stageList.append(self._create(stage, always=always, config=config, *args, **kwargs))
        return stageList
