#!/usr/bin/env python

import numpy

import lsst.afw.math as afwMath
import lsst.afw.image as afwImage

import lsst.pipette.stage as pipStage
from lsst.pipette.stageFactory import StageFactory

from lsst.pipette.stages.isr import Isr
from lsst.pipette.stages.background import BackgroundMeasure
from lsst.pipette.stages.read import Read
from lsst.pipette.stages.write import Write
from lsst.pipette.stages.drop import Drop


# Caller needs to start the clipboard with something like:
# { 'ident': [ [ {'visit': 1, 'ccd': 1}, {'visit': 2, 'ccd': 1}, {'visit': 3, 'ccd': 1} ],
#              [ {'visit': 1, 'ccd': 2}, {'visit': 2, 'ccd': 2}, {'visit': 3, 'ccd': 2} ],
#              [ {'visit': 1, 'ccd': 3}, {'visit': 2, 'ccd': 3}, {'visit': 3, 'ccd': 3} ] ],
#   'inButler': inButler,
#   'outButler': outButler,
# }
#
# Note that the 'ident' matrix is constant in ccd (or whatever component) along the rows, and constant in
# visit (or exposure) along the columns.  A corresponding numpy matrix would be accessed: value[ccd][visit]

class MasterProcessExposure(pipStage.IterateStage):
    """Master detrend exposure creation stage."""
    def __init__(self, name='master.process.exposure', *args, **kwargs):
        iterate = ['ident']
        stage = MasterProcessComponent(*args, **kwargs)
        super(MasterProcessExposure, self).__init__(name, iterate, stage, *args, **kwargs)
        return

class MasterProcessComponent(pipStage.IterateMultiStage):
    """Master detrend processing stage."""
    def __init__(self, name='master.process.comp', factory=None, *args, **kwargs):
        factory = StageFactory(factory, isr=Isr, read=Read, write=Write, drop=Drop, bg=BackgroundMeasure)
        stages = factory.create(['read'], which={'raw': 'exposure', 'detrends': 'detrends'},
                                always=True, *args, **kwargs)
        stages += factory.create(['isr', 'bg'], always=True, *args, **kwargs)
        stages += factory.create(['write'], which={'postISRCCD': 'exposure'}, always=True, *args, **kwargs)
        stages += factory.create(['drop'], which=['exposure', 'detrends'], always=True, *args, **kwargs)
        iterate = ['ident']
        super(MasterProcessComponent, self).__init__(name, iterate, None, stages, *args, **kwargs)
        return

class MasterScale(pipStage.BaseStage):
    """Master detrend scaling stage."""
    def __init__(self, name='master.scale', *args, **kwargs):
        super(MasterScale, self).__init__(name, requires='background', provides='scale', *args, **kwargs)
        # XXX get options from configuration
        self.iterate = 10
        self.tol = 1.0e-3
        return

    def run(self, background=None, *args, **kwargs):
        """Determine scaling for flat-fields"""
        assert background, "background not provided"

        bad = False                     # Are the inputs bad?
        bg = list(background)
        for y in range(len(background)):
            bg[y] = list(background[y])
            for x in range(len(background[y])):
                value = background[y][x]
                if isinstance(value, afwMath.mathLib.Background):
                    image = value.getImageF()
                    stats = afwMath.makeStatistics(image, afwMath.MEDIAN, afwMath.StatisticsControl())
                    bg[y][x] = stats.getValue(afwMath.MEDIAN)
                    if not numpy.any(numpy.isfinite(bg[y][x])):
                        bad = True
                        self.log.log(self.log.WARN, "Bad background for exposure %d component %d: %f" % 
                                     (x, y, bg[y][x]))
                    del image
                    del stats
        if bad:
            raise RuntimeError("One or more bad backgrounds found.")

        matrix = numpy.log(numpy.array(bg)) # log(Background) for each exposure/component
        components, exposures = numpy.shape(matrix)
        scales = numpy.zeros(components) # Initial guess at log(scale) for each component
        fluxes = numpy.apply_along_axis(lambda x: numpy.average(x - scales), 0, matrix)

        self.log.log(self.log.DEBUG, "Input backgrounds: %s" % numpy.exp(matrix))

        for iterate in range(self.iterate):
            # XXX use masks for each quantity: maskedarrays
            scales = numpy.apply_along_axis(lambda x: numpy.average(x - fluxes), 1, matrix)
            fluxes = numpy.apply_along_axis(lambda x: numpy.average(x - scales), 0, matrix)
            avgScale = numpy.average(numpy.exp(scales))
            scales -= numpy.log(avgScale)
            self.log.log(self.log.DEBUG, "Iteration %d fluxes: %s" % (iterate, numpy.exp(fluxes)))
            self.log.log(self.log.DEBUG, "Iteration %d scales: %s" % (iterate, numpy.exp(scales)))

        fluxes = numpy.apply_along_axis(lambda x: numpy.average(x - scales), 0, matrix)

        if numpy.any(numpy.isnan(fluxes)):
            raise RuntimeError("Bad scales: %s --> %s" % (matrix, fluxes))
        
        self.log.log(self.log.INFO, "Exposure scales: %s" % (numpy.exp(fluxes)))
        self.log.log(self.log.INFO, "Component relative scaling: %s" % (numpy.exp(scales)))

        return {'scale': numpy.exp(fluxes)}

class MasterCombineExposure(pipStage.IterateStage):
    """Master detrend exposure creation stage."""
    def __init__(self, name='master.exposure', *args, **kwargs):
        iterate = ['ident']
        stage = MasterCombineComponent(*args, **kwargs)
        super(MasterCombineExposure, self).__init__(name, iterate, stage, *args, **kwargs)
        return

class MasterCombineComponent(pipStage.BaseStage):
    """Master detrend combination stage"""
    def __init__(self, name='master.combine', *args, **kwargs):
        super(MasterCombineComponent, self).__init__(name, requires=['ident', 'outButler'],
                                                     provides=['master'], *args, **kwargs)
        # XXX get options from configuration
        self.rows = 256
        return

    def run(self, ident=None, outButler=None, scale=None, **clipboard):
        assert ident, "ident not provided"
        assert outButler, "outButler not provided"

        height, width = 0,0             # Size of image
        for i in ident:
            exp = outButler.get('postISRCCD', i)
            if height == 0 and width == 0:
                height, width = exp.getHeight(), exp.getWidth()
            elif height != exp.getHeight() or width != exp.getWidth():
                raise RuntimeError("Height and width don't match: %dx%d vs %dx%d" % 
                                   (exp.getHeight(), exp.getWidth(), height, width))
            del exp

        master = afwImage.MaskedImageF(width, height)
        stats = afwMath.StatisticsControl()

        self.log.log(self.log.INFO, "Combining image %dx%d in chunks of %d rows" % (width, height, self.rows))
        for start in range(0, height, self.rows):
            # Read the row of interest
            combine = afwImage.vectorMaskedImageF()
            stop = min(start + self.rows, height)
            rows = stop - start
            box = afwImage.BBox(afwImage.PointI(0, start), width, rows)
            for index, i in enumerate(ident):
                data = afwImage.MaskedImageF(width, rows)
                exp = outButler.get('postISRCCD', i)
                image = exp.getMaskedImage()
                data <<= afwImage.MaskedImageF(image, box)
                if scale is not None:
                    data /= scale[index]
                combine.push_back(data)
                del exp
                #gc.collect()

            # Combine the inputs
            data = afwMath.statisticsStack(combine, afwMath.MEANCLIP, stats)
            masterChunk = afwImage.MaskedImageF(master, box)
            masterChunk <<= data
            
            del data
            del masterChunk
            del box
            del combine
            #gc.collect()
            self.log.log(self.log.DEBUG, "Combined from %d --> %d" % (start, stop))

        # Scale image appropriately
        stats = afwMath.makeStatistics(master, afwMath.MEDIAN, afwMath.StatisticsControl())
        median = stats.getValue(afwMath.MEDIAN)
        self.log.log(self.log.INFO, "Background of combined image: %f" % (median))

        return {'master': master}

class Master(pipStage.MultiStage):
    """Master detrend creation."""
    def __init__(self, name='master', factory=None, *args, **kwargs):
        factory = StageFactory(factory, 
                               master_process=MasterProcessExposure,
                               master_scale=MasterScale,
                               master_combine=MasterCombineExposure)
        stages = factory.create(['master_process'], always=True, *args, **kwargs)
        stages += factory.create(['master_scale'], always=False, *args, **kwargs)
        stages += factory.create(['master_combine'], always=True, *args, **kwargs)
        super(Master, self).__init__(name, stages, *args, **kwargs)
        return
