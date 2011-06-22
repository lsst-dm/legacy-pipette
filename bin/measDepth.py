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

def getObjectsInField(exposure, db, user, password, host="lsst10.ncsa.uiuc.edu", objTable="SimRefObject"):
    """Query database for all reference objects within a given exposure from a given table
    
    @param[in] exposure: exposure whose footprint on the sky is to be searched
    @param[in] db: database to search for reference objects
    @param[in] user: user for database server
    @param[in] password: password for database server
    @param[in] host: database host
    @param[in] objTable: table of reference objects
    
    @warning assumes database sky positions are ICRS
    
    @return a list of sourceList

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
    return sourceList

def measure(exposure, config):
    """Detect and measure sourceList on an exposure

    @param[in] exposure: an instance of afwImage.Exposure
    @param[in] policy:
    
    @return sourceList, footprints
    """
    config['do']['calibrate']['astrometry'] = False
    config['do']['calibrate']['zeropoint'] = True
    config['do']['calibrate']['background'] = False
    config['detect']['thresholdValue'] = 5.0

    calProc = lsst.pipette.calibrate.Calibrate(config=config)
    psf, apcorr, sources, matches, matchMeta = calProc.run(exposure)
    if sources == None:
        raise RuntimeError("found no sources")
    print "Calibrate results: psf=%s, apcorr=%s, %d sources" % (psf, apcorr, len(sources))
    
    photProc = lsst.pipette.phot.Photometry(config=config)
    sourceList, footprints = photProc.run(exposure, psf=psf, apcorr=apcorr, wcs=exposure.getWcs())
    return sourceList, footprints

def matchSources(sourceList, refSourceList, maxSep):
    """Match exposure sourceList to reference sourceList
    
    @param[in] sourceList: list of Sources from the exposure
    @param[in] refSourceList: list of Sources from the reference catalog
    @param[in] maxSep: maximum separation (arcsec)

    @return
    - matchedSourceIds:      set of matched source IDs
    - matchedRefSourceIds:   set of matched reference source IDs
    - unmatchedSourceIds:    set of unmatched source IDs
    - unmatchedRefSourceIds: set of unmatched reference IDs
    """
    sourceMatchList = afwDet.matchRAaDec(sourceList, refSourceList, maxSep)

    sourceIds = set(s.sourceId for s in sourceList)
    refSourceIds = set(s.sourceId for s in refSourceList)
    matchedSourceIds = set()
    matchedRefSourceIds = set()
    for match in sourceMatchList:
       matchedSourcesIds.add(match.first)
       matchedRefSourceIds.add(match.second)
    unmatchedSourceIds = sourceIds - matchedSourceIds
    unmatchedRefSourceIds = refSourceIds - matchedRefSourceIds
    return matchedSourceIds, matchedRefSourceIds, unmatchedSourceIDs, unmatchedRefIDs

if __name__ == "__main__":
    # Note: coadds don't have an official spot in repositories yet
    # so provide an argument to specify the coadd exposure path instead of using the butler
    
    parser = lsst.pipette.options.OptionParser()
    parser.add_option("--exposure", dest="exposure", type="string", help="Path to exposure")
    parser.add_option("--maxsep", dest="maxsep", type="float",
        help="Maximum separation for two sources to match (arcsec)")
    parser.add_option("--db", dest="db", type="string", help="Name of database containing reference catalog")
    parser.add_option("--user", dest="user", type="string", help="Username for database")
    parser.add_option("--password", dest="password", type="string", help="Password for database")
    policyPath = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "measDepthDictionary.paf")
    config, opts, args = parser.parse_args(policyPath)
    
    policy = config.getPolicy()
    dbPolicy = policy.getPolicy("dbPolicy")
    matchPolicy = policy.getPolicy("matchPolicy")
    
    exposurePath = opts.exposure
    db = opts.db
    user = opts.user
    password = opts.password
    host = dbPolicy.get("host")
    objTable = dbPolicy.get("objTable")
    
    exposure = afwImage.ExposureF(exposurePath)
    maxSep = opts.maxsep

    refSourceList = getObjectsInField(
        exposure = exposure,
        db = db,
        user = user,
        password = password,
        host = dbPolicy.get("host"),
        objTable = dbPolicy.get("objTable"),
    )
    print "Found %d reference sources" % (len(refSourceList),)
    sourceList, footprints = measure(exposure, config)
    print "Found %d sources on the exposure" % (len(sourceList),)
    matchedSourceIds, matchedRefSourceIds, unmatchedSourceIDs, unmatchedRefIDs = matchSources(
        sourceList = sourceList,
        refSourceList = refSourceList,
        maxSep = maxSep,
    )

    print "Found %d sources; missed %d and falsely detected %d" % \
        (len(matchedSourceIds), len(unmatchedRefIDs), len(unmatchedSourceIDs))
