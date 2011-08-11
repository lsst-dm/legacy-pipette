#!/usr/bin/env python
import math
import os
import sys

import numpy

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.meas.algorithms as measAlg
import lsst.pipette.idListOptions

FWHMPerSigma = 2 * math.sqrt(2 * math.log(2))

def computeGaussianWidth(psf, bbox):
    """Measures the gaussian width at 5 points and returns the largest value
    """
    gaussWidthList = []
    for x in (bbox.getMinX(), bbox.getMaxX()):
        for y in (bbox.getMinY(), bbox.getMaxY()):
            psfAttr = measAlg.PsfAttributes(psf, x, y)
            gaussWidth = psfAttr.computeGaussianWidth()
            gaussWidthList.append(gaussWidth)
    return max(gaussWidthList)

def reportFwhmAndRaDec(idList, butler):
    """Print the maximum FWHM and center RA/Dec of each image, sorted by filter name and FWHM

    @param[in] idList: list of data identity dictionaries
    @param[in] butler: data butler for input images
    """
    begLen = len(idList)
    print "Processing %d exposures" % (begLen,)
    reportInterval = max(len(idList) / 80, 5)
    dataList = []
    for ind, id in enumerate(idList):
        try:
            exposure = butler.get("calexp", id)
            bbox = exposure.getBBox(afwImage.PARENT)
            filterName = exposure.getFilter().getName()
            psf = butler.get("psf", id)
            maxGaussWidth = computeGaussianWidth(psf, bbox)
            maxFwhm = FWHMPerSigma * maxGaussWidth

            floatBBox = afwGeom.Box2D(bbox)
            ctrPixArr = (numpy.array(floatBBox.getMax()) + numpy.array(floatBBox.getMin())) / 2.0
            ctrPixPos = afwGeom.Point2D(*ctrPixArr)
            ctrSkyPos = exposure.getWcs().pixelToSky(ctrPixPos).getPosition()

            dataList.append((filterName, maxFwhm, ctrSkyPos, id))
            sys.stdout.write("\r%d of %d" % (ind+1, begLen))
            sys.stdout.flush()
        except Exception, e:
            print "\nFailed on %s: %s" % (id, e)
            continue
    endLen = len(dataList)
    print "\nProcessed %d exposures (skipped %d)" % (endLen, endLen - begLen)
    print "ID\tFWHM\tRA\tDec"

    dataList.sort()
    for filterName, maxFwhm, ctrSkyPos, id in dataList:
        print "%s\t%0.2f\t%0.5f\t%0.5f" % (id, maxFwhm, ctrSkyPos[0], ctrSkyPos[1])
    

if __name__ == "__main__":
    parser = lsst.pipette.idListOptions.IdListOptionParser()
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "blankDictionary.paf")
    config, opts, args = parser.parse_args(policyPath)
    
    reportFwhmAndRaDec(
        idList = parser.getIdList(),
        butler = parser.getReadWrite().inButler,
    )
