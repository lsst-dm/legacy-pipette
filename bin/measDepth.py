#!/usr/bin/env python
"""Measure depth of a coadd (or other exposure) by performing detection, measurement,
re-detection, re-measurement and source association
and reporting the number of objects found, number missed and false detections.

@todo
- Display a line graph of fraction of detected stars vs. magnitude
  as Andy Becker says: # matched stars + # blended stars / # of ref stars
  (though in my case I don't know about blends because I'm using cruder source association).
- Display a separate plot of psfFlux error vs. magnitude for matched stars, binned by 1/2 mag
  and comapre this to one of the input images. At a given fraction you should be able to go fainter in the coadd.
- Once ticket #1714 is fixed use database source IDs for reference source IDs
"""
import math
import os
import sys

import numpy
import matplotlib.pyplot as pyplot
import MySQLdb

import lsst.afw.coord as afwCoord
import lsst.afw.detection as afwDet
import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.meas.algorithms as measAlg
import lsst.sdqa as sdqa
import lsst.pipette.options
import lsst.pipette.calibrate
import lsst.pipette.phot
import lsst.pipette.processCcd

def getObjectsInField(exposure, filterName, db, user, password, host="lsst10.ncsa.uiuc.edu", objTable="SimRefObject"):
    """Query database for all reference objects within a given exposure from a given table
    
    @param[in] exposure: exposure whose footprint on the sky is to be searched
    @param[in] filterName: name of filter (e.g. "g"); required because exposure may not have a Filter
    @param[in] db: database to search for reference objects
    @param[in] user: user for database server
    @param[in] password: password for database server
    @param[in] host: database host
    @param[in] objTable: table of reference objects
    
    @return a list of sources. Fields that are set include:
        - sourceId: set to an index, NOT refObjectId from the database 
        - ra, dec
        - flagForDetection is 1 if isStar, 0 otherwise
        - psfFlux
    
    @warning
    - sourceId is set to an arbitrary index, NOT refObjectId from the database, due to ticket #1714
    - assumes database sky positions are ICRS

    SimRefObject table:    
    +----------------+--------------+------+-----+---------+-------+
    | refObjectId    | bigint(20)   | NO   | PRI | NULL    |       |
    | isStar         | tinyint(4)   | NO   |     | NULL    |       |
    | varClass       | tinyint(4)   | NO   |     | NULL    |       |
    | ra             | double       | NO   |     | NULL    |       |
    | decl           | double       | NO   | MUL | NULL    |       |
    | gLat           | double       | YES  |     | NULL    |       |
    | gLon           | double       | YES  |     | NULL    |       |
    | sedName        | varchar(255) | YES  |     | NULL    |       |
    | uMag           | double       | NO   |     | NULL    |       |
    | gMag           | double       | NO   |     | NULL    |       |
    | rMag           | double       | NO   |     | NULL    |       |
    | iMag           | double       | NO   |     | NULL    |       |
    | zMag           | double       | NO   |     | NULL    |       |
    | yMag           | double       | NO   |     | NULL    |       |
    | muRa           | double       | YES  |     | NULL    |       |
    | muDecl         | double       | YES  |     | NULL    |       |
    | parallax       | double       | YES  |     | NULL    |       |
    | vRad           | double       | YES  |     | NULL    |       |
    | redshift       | double       | YES  |     | NULL    |       |
    | semiMajorBulge | double       | YES  |     | NULL    |       |
    | semiMinorBulge | double       | YES  |     | NULL    |       |
    | semiMajorDisk  | double       | YES  |     | NULL    |       |
    | semiMinorDisk  | double       | YES  |     | NULL    |       |
    | uCov           | smallint(6)  | NO   |     | NULL    |       |
    | gCov           | smallint(6)  | NO   |     | NULL    |       |
    | rCov           | smallint(6)  | NO   |     | NULL    |       |
    | iCov           | smallint(6)  | NO   |     | NULL    |       |
    | zCov           | smallint(6)  | NO   |     | NULL    |       |
    | yCov           | smallint(6)  | NO   |     | NULL    |       |
    +----------------+--------------+------+-----+---------+-------+
    """
    wcs = exposure.getWcs()

    db = MySQLdb.connect(host = host,
                         db = db,
                         user = user,
                         passwd = password)
    cursor = db.cursor()

    calib = exposure.getCalib()
    
    filterColName = "%sMag" % (filterName,)
    print "filterName=%s, filterColName=%s" % (filterName, filterColName)

    pixPosBox = afwGeom.Box2D(exposure.getBBox(afwImage.PARENT))
    llSky = wcs.pixelToSky(pixPosBox.getMin()).getPosition()
    urSky = wcs.pixelToSky(pixPosBox.getMax()).getPosition()
    # create binary representation of search polygon; name it @poly
    queryStr = "SET @poly = scisql_s2CPolyToBin(%0.6f, %0.6f, %0.6f, %0.6f, %0.6f, %0.6f, %0.6f, %0.6f)" % \
    (
        llSky[0], llSky[1],
        urSky[0], llSky[1],
        urSky[0], urSky[1],
        llSky[0], urSky[1],
    )
    print "SQL command:", queryStr
    cursor.execute(queryStr)

    # Compute HTM ID ranges for the level 20 triangles overlapping @poly.
    # They will be stored in a temp table called scisql.Region with two columns, htmMin and htmMax
    queryStr = "CALL scisql.scisql_s2CPolyRegion(@poly, 20)"
    print "SQL command:", queryStr
    cursor.execute(queryStr)

    # Select reference objects inside the polygon. The join against
    # the HTM ID range table populated above cuts down on the number of
    # SimRefObject rows that need to be tested against the polygon
    queryStr = "SELECT refObjectId, isStar, ra, decl, %s" % (filterColName,) + \
        " FROM %s AS objTbl INNER JOIN" % (objTable,) + \
        " scisql.Region AS rgnTbl ON (objTbl.htmId20 BETWEEN rgnTbl.htmMin and rgnTbl.htmMax)" + \
        " WHERE scisql_s2PtInCPoly(ra, decl, @poly) = 1"
    print "SQL command:", queryStr
    cursor.execute(queryStr)
    sourceList = []
    fakeId = 0 # to work around ticket #1714
    while True:
        dataTuple = cursor.fetchone()
        if dataTuple == None:
            break
        sourceId, isStar, ra, dec, mag = dataTuple
        fakeId += 1
        raDecCoord = afwCoord.IcrsCoord(afwGeom.Point2D(ra, dec), afwCoord.DEGREES) 
        flux = calib.getFlux(mag)
        if flux <= 0:
            print "Error: reference source %s has flux = %s < 0; mag = %s" % (sourceId, flux, mag)
            continue
        source = afwDet.Source(fakeId)
        source.setRaDecObject(raDecCoord)
        source.setFlagForDetection(isStar)
        source.setPsfFlux(flux)
        sourceList.append(source)

    # copy RaObject/DecObject to Ra/Dec
    for source in sourceList:
        source.setRa(source.getRaObject())
        source.setDec(source.getDecObject())
    return sourceList


def measure(exposure, config):
    """Detect and measure sources on an exposure

    @param[in] exposure: an instance of afwImage.Exposure
    @param[in] policy:
    
    @return sourceList
    """
    # zero out the mask except for "nan"s.
    print "Remake mask to only mask out NaNs"
    edgeMask = afwImage.MaskU.getPlaneBitMask(["EDGE"])
    mi = exposure.getMaskedImage()
    imArr = mi.getImage().getArray()
    maskArr = mi.getMask().getArray()
    print "Number of masked pixels = %d before remaking mask" % (numpy.sum(maskArr != 0),)
    maskArr[:] = numpy.where(numpy.isfinite(imArr), 0, edgeMask)
    print "Number of masked pixels = %d after remaking mask" % (numpy.sum(maskArr != 0),)
    exposure.writeFits("remaskedExposure.fits")
    
    config['do']['isr']['enabled'] = False
    config['do']['calibrate']['psf'] = True
    config['do']['calibrate']['apcorr'] = True
    config['do']['calibrate']['astrometry'] = False
    config['do']['calibrate']['zeropoint'] = False # prevents measuring astrometry
    # turn off cosmic ray interpolation due to ticket #1718 and because it is probably not wanted anyway
    config['do']['calibrate']['repair']['interpolate'] = False
    config['do']['calibrate']['repair']['cosmicray'] = False
    config['do']['calibrate']['background'] = False

    config["psf"]["select"]["fluxLim"] = 10.0 # why is the default so much larger?
    
    procCcdProc = lsst.pipette.processCcd.ProcessCcd(config=config)
    exp, psf, apcorr, brightSources, sourceList, matches, matchMeta = procCcdProc.run([exposure])
    
    badSourceList = [s for s in sourceList if s.getPsfFlux() <= 0]
    if len(badSourceList) > 0:
        print "Warning: rejecting %d sources with psfFlux <= 0" % (len(badSourceList),)
        sourceList = [s for s in sourceList if s.getPsfFlux() > 0]

    return sourceList


def matchSources(sourceList, refSourceList, maxSep):
    """Match exposure sources to reference sources
    
    @param[in] sourceList: list of Sources from the exposure
    @param[in] refSourceList: list of Sources from the reference catalog
    @param[in] maxSep: maximum separation (arcsec)

    @return
    - matchedSources:       set of matched exposure Sources
    - matchedRefSources:    set of matched reference Sources
    - unmatchedSources:     set of unmatched exposure Sources
    - unmatchedRefSources:  set of unmatched reference Sources
    """
    sourceMatchList = afwDet.matchRaDec(sourceList, refSourceList, float(maxSep))
    print "Matched %d sources using maxSep=%s" % (len(sourceMatchList), maxSep)
    
    matchedSources = set(m.first for m in sourceMatchList)
    matchedRefSources = set(m.second for m in sourceMatchList)

    sourceDict = dict((s.getSourceId(), s) for s in sourceList)
    sourceIds = set(sourceDict.keys())
    matchedSourceIds  = set(m.first.getSourceId()  for m in sourceMatchList)
    unmatchedSourceIds = sourceIds - matchedSourceIds
    unmatchedSources = set(sourceDict[id] for id in unmatchedSourceIds)

    refSourceDict = dict((s.getSourceId(), s) for s in refSourceList)
    refSourceIDs = set(s.getSourceId() for s in refSourceList)
    matchedRefSourceIds = set(s.getSourceId() for s in matchedRefSources)
    unmatchedRefSourceIds = refSourceIDs - matchedRefSourceIds
    unmatchedRefSources = set(refSourceDict[id] for id in unmatchedRefSourceIds)

    return matchedSources, matchedRefSources, unmatchedSources, unmatchedRefSources


if __name__ == "__main__":
    # Note: coadds don't have an official spot in repositories yet
    # so provide an argument to specify the coadd exposure path instead of using the butler
    
    parser = lsst.pipette.options.OptionParser()
    parser.add_option("--exposure", dest="exposure", type="string", help="Path to exposure")
    parser.add_option("--filter", dest="filter", type="string", help="Filter name (e.g. g)")
    parser.add_option("--maxsep", dest="maxsep", type="float", default=0.5,
        help="Maximum separation for two sources to match (arcsec)")
    parser.add_option("--db", dest="db", type="string", help="Name of database containing reference catalog")
    parser.add_option("--user", dest="user", type="string", help="Username for database")
    parser.add_option("--password", dest="password", type="string", help="Password for database")
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "measDepthDictionary.paf")
    overridePath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "lsstSim.paf")
    config, opts, args = parser.parse_args([policyPath, overridePath])
    
    policy = config.getPolicy()
    dbPolicy = policy.getPolicy("dbPolicy")
    matchPolicy = policy.getPolicy("matchPolicy")
    
    exposurePath = opts.exposure
    filterName = opts.filter
    db = opts.db
    user = opts.user
    password = opts.password
    
    for name in ("exposure", "db", "filter", "user", "password"):
        if getattr(opts, name) == None:
            print "Error: must specify --%s" % (name,)
            sys.exit(1)
    
    host = dbPolicy.get("host")
    objTable = dbPolicy.get("objTable")
    
    exposure = afwImage.ExposureF(exposurePath)
    calib = exposure.getCalib()
    print "exposure zeropoint=%0.1f" % (calib.getMagnitude(1.0),)
    maxSep = opts.maxsep

    print "Search the reference catalog"
    refSourceList = getObjectsInField(
        exposure = exposure,
        filterName = filterName,
        db = db,
        user = user,
        password = password,
        host = dbPolicy.get("host"),
        objTable = dbPolicy.get("objTable"),
    )
    print "Found %d reference sources in the catalog" % (len(refSourceList),)
    
    print "Detect and measure sources on the exposure"
    sourceList = measure(exposure, config)
    print "Found %d sources on the exposure" % (len(sourceList),)
    
    print "Match sources"
    matchedSources, matchedRefSources, unmatchedSources, unmatchedRefSources = matchSources(
        sourceList = sourceList,
        refSourceList = refSourceList,
        maxSep = maxSep,
    )

    matchedStars = set(s for s in matchedSources if s.getFlagForDetection())
    matchedRefStars = set(s for s in matchedRefSources if s.getFlagForDetection())
    unmatchedRefStars = set(s for s in unmatchedRefSources if s.getFlagForDetection())
    
    print "Found %d reference sources, of which %d are stars, in the catalog" % \
        (len(refSourceList), len(matchedRefStars) + len(unmatchedRefStars))
    print "Found %d sources on the exposure" % (len(sourceList),)
    print "Matched using maxSep=%0.1f arcsec" % (maxSep,)
    print "Matched %d sources; failed to detect %d reference sources; falsely detected %d sources" % \
        (len(matchedSources), len(unmatchedRefSources), len(unmatchedSources))
    print "Matched %d stars; failed to detect %d reference stars" % \
        (len(matchedRefStars), len(unmatchedRefStars))
    
    matchedStarPsfMags = sorted(list(calib.getMagnitude(s.getPsfFlux()) for s in matchedStars))
    unmatchedRefStarPsfMags = sorted(list(calib.getMagnitude(s.getPsfFlux()) for s in unmatchedRefStars))
    unmatchedSourcePsfMags = sorted(list(calib.getMagnitude(s.getPsfFlux()) for s in unmatchedSources))
    
    plotData = (matchedStarPsfMags, unmatchedRefStarPsfMags, unmatchedSourcePsfMags)
    dataLabels = ("Matched Stars", "Unmatched Ref Stars", "False Detections")
    try:
        count, bins, ignored = pyplot.hist(plotData,
            label=dataLabels, bins=30, histtype='barstacked', normed=True)
        pyplot.legend(loc='upper left')
    except Exception:
        # old version of matplotlib; cannnot show a useful legend without a lot of extra work
        count, bins, ignored = pyplot.hist(plotData, bins=30, histtype='barstacked', normed=True)
        print "This matplotlib is too old to support legends for stacked histograms."
        print "From bottom to top the histogram shows:"
        for label in dataLabels:
            print "*", label
    pyplot.show()
