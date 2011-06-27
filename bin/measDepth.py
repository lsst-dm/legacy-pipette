#!/usr/bin/env python
"""Measure depth of a coadd (or other exposure) by performing detection, measurement,
re-detection, re-measurement and source association
and reporting the number of objects found, number missed and false detections.

@todo once ticket #1714 is fixed use database source IDs for reference source IDs
"""
import math
import os
import sys

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

def getObjectsInField(exposure, db, user, password, host="lsst10.ncsa.uiuc.edu", objTable="SimRefObject"):
    """Query database for all reference objects within a given exposure from a given table
    
    @param[in] exposure: exposure whose footprint on the sky is to be searched
    @param[in] db: database to search for reference objects
    @param[in] user: user for database server
    @param[in] password: password for database server
    @param[in] host: database host
    @param[in] objTable: table of reference objects
    
    @warning assumes database sky positions are ICRS
    
    @return a list of sources

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

    pixPosBox = afwGeom.Box2D(exposure.getBBox(afwImage.PARENT))
    llSky = wcs.pixelToSky(pixPosBox.getMin()).getPosition()
    urSky = wcs.pixelToSky(pixPosBox.getMax()).getPosition()
    skyCornersStr = "%0.4f %0.4f %0.4f %0.4f %0.4f %0.4f %0.4f %0.4f" % (
        llSky[0], llSky[1],
        urSky[0], llSky[1],
        urSky[0], urSky[1],
        llSky[0], urSky[1],
    )
    
    queryStr = "select refObjectId, ra, decl " + \
        "from %s as objTbl " % (objTable,) + \
        "where qserv_ptInSphPoly(objTbl.ra, objTbl.decl, '%s')" % (skyCornersStr,)
    print "SQL query=%r" % (queryStr,)
    results = cursor.execute(queryStr)
    sourceList = []
    fakeId = 0 # to work around ticket #1714
    while True:
        dataTuple = cursor.fetchone()
        if dataTuple == None:
            break
        sourceId, ra, dec = dataTuple
        fakeId += 1
        raDecCoord = afwCoord.IcrsCoord(afwGeom.Point2D(ra, dec), afwCoord.DEGREES) 
        source = afwDet.Source(fakeId)
        source.setRaDecObject(raDecCoord)
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
    config['do']['isr']['enabled'] = False
    config['do']['calibrate']['psf'] = True
    config['do']['calibrate']['apcorr'] = True
    config['do']['calibrate']['astrometry'] = False
    config['do']['calibrate']['zeropoint'] = False # prevents measuring astrometry
    # turn off cosmic ray interpolation due to ticket #1718 and because it is probably not wanted anyway
    config['do']['calibrate']['repair']['interpolate'] = False
    config['do']['calibrate']['repair']['cosmicray'] = False
    config['do']['calibrate']['background'] = False

#    config['calibrate']['thresholdValue'] = 10.0 # default is 50
    config['detect']['thresholdValue'] = 5.0
    config["psf"]["select"]["fluxLim"] = 50.0 # why is the default so much larger?
    
    procCcdProc = lsst.pipette.processCcd.ProcessCcd(config=config)
    exp, psf, apcorr, brightSources, sourceList, matches, matchMeta = procCcdProc.run([exposure])

#     # copy Ra/Dec to RaObject/DecObject
#     for source in sourceList:
#         source.setRaObject(source.getRa())
#         source.setDecObject(source.getDec())
    return sourceList

def matchSources(sourceList, refSourceList, maxSep):
    """Match exposure sources to reference sources
    
    @param[in] sourceList: list of Sources from the exposure
    @param[in] refSourceList: list of Sources from the reference catalog
    @param[in] maxSep: maximum separation (arcsec)

    @return
    - matchedSourceIds:      set of matched source IDs
    - matchedRefSourceIds:   set of matched reference source IDs
    - unmatchedSourceIds:    set of unmatched source IDs
    - unmatchedRefSourceIds: set of unmatched reference IDs
    """
    sourceMatchList = afwDet.matchRaDec(sourceList, refSourceList, float(maxSep))
    print "matched %d sources using maxSep=%s" % (len(sourceMatchList), maxSep)

    sourceIds = set(s.getSourceId() for s in sourceList)
    refSourceIds = set(s.getSourceId() for s in refSourceList)
    matchedSourceIds = set()
    matchedRefSourceIds = set()
    for match in sourceMatchList:
       matchedSourceIds.add(match.first.getSourceId())
       matchedRefSourceIds.add(match.second.getSourceId())
    unmatchedSourceIds = sourceIds - matchedSourceIds
    unmatchedRefSourceIds = refSourceIds - matchedRefSourceIds
    return matchedSourceIds, matchedRefSourceIds, unmatchedSourceIds, unmatchedRefSourceIds

if __name__ == "__main__":
    # Note: coadds don't have an official spot in repositories yet
    # so provide an argument to specify the coadd exposure path instead of using the butler
    
    parser = lsst.pipette.options.OptionParser()
    parser.add_option("--exposure", dest="exposure", type="string", help="Path to exposure")
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
    db = opts.db
    user = opts.user
    password = opts.password
    
    for name in ("exposure", "db", "user", "password"):
        if getattr(opts, name) == None:
            print "Error: must specify --%s" % (name,)
            sys.exit(1)
    
    host = dbPolicy.get("host")
    objTable = dbPolicy.get("objTable")
    
    exposure = afwImage.ExposureF(exposurePath)
    maxSep = opts.maxsep

    print "Search the reference catalog"
    refSourceList = getObjectsInField(
        exposure = exposure,
        db = db,
        user = user,
        password = password,
        host = dbPolicy.get("host"),
        objTable = dbPolicy.get("objTable"),
    )
    
    print "Detect and measure sources on the exposure"
    sourceList = measure(exposure, config)
    
    print "Match sources"
    matchedSourceIds, matchedRefSourceIds, unmatchedSourceIds, unmatchedRefSourceIds = matchSources(
        sourceList = sourceList,
        refSourceList = refSourceList,
        maxSep = maxSep,
    )
    print "Found %d reference sources in the catalog" % (len(refSourceList),)
    print "Found %d sources on the exposure" % (len(sourceList),)
    print "Matched using maxSep=%0.1f arcsec" % (maxSep,)
    print "Identified %d sources from the exposure; failed to detect %d sources and falsely detected %d" % \
        (len(matchedSourceIds), len(unmatchedRefSourceIds), len(unmatchedSourceIds))
