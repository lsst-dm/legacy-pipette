#!/usr/bin/env python

import numpy

import lsst.afw.math as afwMath
import lsst.afw.image as afwImage

import lsst.pipette.engine.process as pipProc
import lsst.pipette.engine.isr as pipIsr
import lsst.pipette.engine.background as pipBackground
import lsst.pipette.engine.phot as pipPhot


class Master(pipProc.Process):
    def run(self, identMatrix, inButler, outButler):
        """Combine individual detrend exposures to create a master detrend.

        @param identMatrix Matrix of identifiers; order is component-major, exposure minor, like this:
                           [ [ {'visit': 1, 'ccd': 1}, {'visit': 2, 'ccd': 1}, {'visit': 3, 'ccd': 1} ],
                             [ {'visit': 1, 'ccd': 2}, {'visit': 2, 'ccd': 2}, {'visit': 3, 'ccd': 2} ],
                             [ {'visit': 1, 'ccd': 3}, {'visit': 2, 'ccd': 3}, {'visit': 3, 'ccd': 3} ] ]
        @param inButler Butler for inputs
        @param outButler Butler for outputs
        @output List of master detrends for each component
        """
        assert identMatrix, "No identMatrix provided"
        assert inButler, "No inButler provided"
        assert outButler, "No outButler provided"

        do = self.config['do']

        isrProc = pipIsr.Isr(config=self.config, log=self.log)
        bgProc = pipBackground.BackgroundMeasure(config=self.config, log=self.log)

        bgMatrix = list()
        for identList in identMatrix:
            bgList = list()
            bgMatrix.append(bgList)
            for ident in identList:
                exposure, detrends = self.read(inButler, ident, ['raw', 'detrends'])
                isrProc.run(exposure, detrends=detrends)
                del detrends
                bg = bgProc.run(exposure)
                bgList.append(bg)
                # XXX photometry so we can mask objects?
                self.write(outButler, ident, {'postISRCCD': exposure})
                del exposure
                
        if do['scale']:
            compScales, expScales = self.scale(bgMatrix)
        else:
            compScales, expScales = None, None

        masterList = list()
        for identList in identMatrix:
            master = self.combine(identList, outButler, expScales=expScales)
            self.display('master', exposure=master, pause=True)
            masterList.append(master)

        return masterList


    def scale(self, backgrounds):
        """Determine scaling for flat-fields

        @param backgrounds Backgrounds provided as a matrix, backgrounds[component][exposure]
        @return Relative scales for each component, Scales for each exposure
        """
        assert backgrounds, "background not provided"

        bad = False                     # Are the inputs bad?
        bg = list(backgrounds)
        for y in range(len(backgrounds)):
            bg[y] = list(backgrounds[y])
            for x in range(len(backgrounds[y])):
                value = backgrounds[y][x]
                if isinstance(value, afwMath.mathLib.Background):
                    image = value.getImageF()
                    stats = afwMath.makeStatistics(image, afwMath.MEDIAN, afwMath.StatisticsControl())
                    value = stats.getValue(afwMath.MEDIAN)
                    del image
                    del stats
                elif not isinstance(value, numbers.Real):
                    raise RuntimeError("Unable to interpret background for exposure %d component %d: %s" %
                                       (x, y, value))

                bg[y][x] = value
                if not numpy.any(numpy.isfinite(bg[y][x])):
                    # XXX Mask bad value instead of failing completely
                    bad = True
                    self.log.log(self.log.WARN, "Bad background for exposure %d component %d: %f" % 
                                 (x, y, bg[y][x]))
        if bad:
            raise RuntimeError("One or more bad backgrounds found.")

        matrix = numpy.log(numpy.array(bg)) # log(Background) for each exposure/component
        components, exposures = numpy.shape(matrix)
        compScales = numpy.zeros(components) # Initial guess at log(scale) for each component
        expScales = numpy.apply_along_axis(lambda x: numpy.average(x - compScales), 0, matrix)

        self.log.log(self.log.DEBUG, "Input backgrounds: %s" % numpy.exp(matrix))

        for iterate in range(self.config['scale']['iterate']):
            # XXX use masks for each quantity: maskedarrays
            compScales = numpy.apply_along_axis(lambda x: numpy.average(x - expScales), 1, matrix)
            expScales = numpy.apply_along_axis(lambda x: numpy.average(x - compScales), 0, matrix)
            avgScale = numpy.average(numpy.exp(compScales))
            compScales -= numpy.log(avgScale)
            self.log.log(self.log.DEBUG, "Iteration %d exposure scales: %s" %
                         (iterate, numpy.exp(expScales)))
            self.log.log(self.log.DEBUG, "Iteration %d component scales: %s" %
                         (iterate, numpy.exp(compScales)))

        expScales = numpy.apply_along_axis(lambda x: numpy.average(x - compScales), 0, matrix)

        if numpy.any(numpy.isnan(expScales)):
            raise RuntimeError("Bad exposure scales: %s --> %s" % (matrix, expScales))
        
        self.log.log(self.log.INFO, "Exposure scales: %s" % (numpy.exp(expScales)))
        self.log.log(self.log.INFO, "Component relative scaling: %s" % (numpy.exp(compScales)))

        return numpy.exp(compScales), numpy.exp(expScales)

    def combine(self, identList, butler, expScales=None):
        """Combine multiple exposures for a single component

        @param identList List of data identifiers
        @param butler Data butler
        @param expScales Scales to apply for each exposure, or None
        @return Combined image
        """
        numRows = self.config['combine']['rows'] # Number of rows to combine at once

        assert identList, "ident not provided"
        assert butler, "butler not provided"
        if expScales is not None:
            assert len(expScales) == len(identList), \
                "Lengths of inputs (%d) and scales (%d) differ" % (len(expScales), len(identList))

        height, width = 0,0             # Size of image
        for i in identList:
            exp = butler.get('postISRCCD', i)
            if height == 0 and width == 0:
                height, width = exp.getHeight(), exp.getWidth()
            elif height != exp.getHeight() or width != exp.getWidth():
                raise RuntimeError("Height and width don't match: %dx%d vs %dx%d" % 
                                   (exp.getHeight(), exp.getWidth(), height, width))
            del exp

        master = afwImage.MaskedImageF(width, height)
        stats = afwMath.StatisticsControl()

        self.log.log(self.log.INFO, "Combining image %dx%d in chunks of %d rows" % (width, height, numRows))
        for start in range(0, height, numRows):
            # Read the row of interest
            combine = afwImage.vectorMaskedImageF()
            stop = min(start + numRows, height)
            rows = stop - start
            box = afwImage.BBox(afwImage.PointI(0, start), width, rows)
            for index, i in enumerate(identList):
                data = afwImage.MaskedImageF(width, rows)
                exp = butler.get('postISRCCD', i)
                image = exp.getMaskedImage()
                data <<= afwImage.MaskedImageF(image, box)
                if expScales is not None:
                    data /= expScales[index]
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

        return master
