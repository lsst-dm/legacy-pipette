#!/usr/bin/env python
import math
import os
import sys

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

def reportFwhm(idList, butler):
    """Print the maximum FWHM of each PSF found, sorted by filter name and FWHM

    @param[in] idList: list of data identity dictionaries
    @param[in] butler: data butler for input images
    """
    print "Processing %d PSFs" % (len(idList),)
    reportInterval = max(len(idList) / 80, 5)
    dataList = []
    for id in idList:
        try:
            exposure = butler.get("calexp", id)
            bbox = exposure.getBBox(afwImage.PARENT)
            filterName = exposure.getFilter().getName()
            psf = butler.get("psf", id)
            maxGaussWidth = computeGaussianWidth(psf, bbox)
            maxFwhm = FWHMPerSigma * maxGaussWidth
            dataList.append((filterName, maxFwhm, id))
            if len(dataList) % reportInterval == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
        except Exception:
            print "Failed on %s: %s" % (id, e)
            continue            
    print "\nDetermined %d PSFs:" % (len(dataList),)

    dataList.sort()
    for filterName, maxFwhm, id in dataList:
        print "%s\t%0.2f" % (id, maxFwhm)
    

if __name__ == "__main__":
    parser = lsst.pipette.idListOptions.IdListOptionParser()
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "blankDictionary.paf")
    config, opts, args = parser.parse_args(policyPath)
    
    reportFwhm(
        idList = parser.getIdList(),
        butler = parser.getReadWrite().inButler,
    )
