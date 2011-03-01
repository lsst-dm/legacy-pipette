#!/usr/bin/env python
import os
import math
import lsst.pex.logging as pexLog
import lsst.pex.policy as pexPolicy
import lsst.daf.persistence as dafPersist
import lsst.afw.cameraGeom as cameraGeom
import lsst.afw.cameraGeom.utils as cameraGeomUtils
import lsst.afw.image as afwImage
import lsst.afw.detection as afwDet
import lsst.afw.coord as afwCoord
import lsst.meas.astrom as measAstrom
import lsst.meas.algorithms.utils as maUtils

"""This module provides I/O for pipette (LSST algorithms testing)"""

mapperBuffer = dict()                   # Buffer of mappers for recycling

def getMapper(mapper, root=None, calibRoot=None, registry=None):
    """Pull a mapper out of the buffer, if present, otherwise instantiate a new one"""
    key = ""
    for part in (root, calibRoot, registry):
        if part:
            key += part
        key += ":"
    if not mapperBuffer.has_key(mapper):
        mapperBuffer[mapper] = dict()
    thisMapperBuffer = mapperBuffer[mapper]
    if not thisMapperBuffer.has_key(key):
        thisMapperBuffer[key] = mapper(root=root, registry=registry)
    return thisMapperBuffer[key]


def initMapper(mapper, config, log, inMap=True):
    """Utility function to initialize an input or output mapper"""
    
    if isinstance(mapper, dafPersist.Mapper):
        mapp = mapper
    elif issubclass(mapper, dafPersist.Mapper):
        # It's a class that we're to instantiate
        if config is None:
            # We'll try this, but don't expect it will work...
            log.log(self.log.WARN, "No configuration provided for mapper.")
            mapp = getMapper(mapper)
        else:
            roots = config['roots']
            dataRoot = roots['data'] if roots.has_key('data') else None
            # UNUSED calibRoot = roots['calib'] if roots.has_key('calib') else None
            if inMap:
                mapp = getMapper(mapper, root=dataRoot)
            else:
                outRoot = roots['output'] if roots.has_key('output') else None
                # if there's no output registry, use the input registry
                outRegistry = os.path.join(outRoot, "registry.sqlite3")
                inRegistry = os.path.join(dataRoot, "registry.sqlite3")
                if os.path.exists(outRegistry):
                    registry = outRegistry
                elif (os.path.exists(inRegistry)):
                    registry = inRegistry
                else:
                    log.log(log.WARN, "Unable to find a registry for output mapper")
                    registry = None
                
                mapp = getMapper(mapper, root=outRoot, registry=registry)

    else:
        raise RuntimeError("Unable to interpret provided mapper.")

    return mapp



class ReadWrite(object):
    """ReadWrite provides I/O for pipette (LSST algorithms testing)"""

    def __init__(self,                  # ReadWrite
                 mappers,               # Mapper or mapper class to use
                 ccdKeys,               # Data keywords required to specify a CCD
                 fileKeys=None,         # Data keywords required to specify a file
                 config=None,           # Configuration
                 ):
        """Initialisation

        @param mapper Data mapper (class or instance) for persistence
        @param config Configuration (for instantiating mapper)
        """

        # if we got a list, it contains [inMapper, outMapper]
        if isinstance(mappers, list) and len(mappers) == 2:
            inMapper, outMapper = mappers
        # if we got a mapper, use it for both input and output
        elif (isinstance(mappers, dafPersist.Mapper) or issubclass(mappers, dafPersist.Mapper)):
            inMapper, outMapper = mappers, mappers
        # punt
        else:
            raise RuntimeError("'mapper' must be a dafPersist.Mapper (or derived from), or a list containing two of them (in and out).")

        
        self.log = pexLog.Log(pexLog.getDefaultLog(), "ReadWrite")

        self.inMapper = initMapper(inMapper, config, self.log, inMap=True)
        self.ibf = dafPersist.ButlerFactory(mapper=self.inMapper)
        self.inButler = self.ibf.create()
        
        self.outMapper = initMapper(outMapper, config, self.log, inMap=False)
        self.obf = dafPersist.ButlerFactory(mapper=self.outMapper)
        self.outButler = self.obf.create()
        
        self.ccdKeys = ccdKeys
        if fileKeys is None:
            fileKeys = list(ccdKeys)
        if isinstance(fileKeys, basestring):
            fileKeys = [fileKeys]
        self.fileKeys = fileKeys
        return

    def lookup(self, dataId):
        """Lookup data for a CCD.

        @param dataId Data identifier for butler
        @returns Complete data identifiers
        """
        for key in self.ccdKeys:
            if not dataId.has_key(key):
                raise KeyError("Data identifier does not contain keyword %s" % key)
        keys = self.inButler.queryMetadata('raw', self.ccdKeys, format=self.fileKeys, dataId=dataId)

        identifiers = list()
        for key in keys:
            ident = dict()
            if not isinstance(key, basestring) and hasattr(key, "__getitem__"):
                for index, name in enumerate(self.fileKeys):
                    ident[name] = key[index]
            else:
                assert(len(self.fileKeys) == 1)
                ident[self.fileKeys[0]] = key
            identifiers.append(ident)
        return identifiers

    def readRaw(self, dataId):
        """Read raw data of a CCD.

        @param dataId Data identifier for butler
        @returns Raw exposures
        """
        self.log.log(self.log.INFO, "Looking for: %s" % (dataId))
        identifiers = self.lookup(dataId)
        if not identifiers:
            raise RuntimeError("No raw data found for dataId %s" % (dataId))
        
        exposures = list()
        for ident in identifiers:
            ident.update(dataId)
            if not self.inButler.datasetExists('raw', ident):
                raise RuntimeError("Raw data does not exist for %s" % ident)
            self.log.log(self.log.INFO, "Reading: %s" % (ident))
            exp = self.inButler.get('raw', ident)
            if isinstance(exp, afwImage.ExposureU):
                exp = exp.convertF()
            exposures.append(exp)
        return exposures

    def readMatches(self, dataId, ignore=False):
        """Read matches, sources and catalogue; combine.

        @param dataId Data identifier for butler
        @param ignore Ignore non-existent data?
        @returns Matches
        """
        sources = self.read('matchedsources', dataId, ignore=ignore)
        matches = self.read('matches', dataId, ignore=ignore)
        headers = self.read('calexp_md', dataId, ignore=ignore)

        output = []
        for sourceList, matchList, header in zip(sources, matches, headers):
            meta = matchList.getSourceMatchMetadata()
            matchList = matchList.getSourceMatches()
            sourceList = sourceList.getSources()
            wcs = afwImage.makeWcs(header)

            filter = header.get('FILTER').strip()
            width, height = header.get('NAXIS1'), header.get('NAXIS2')
            xc, yc = 0.5 * width, 0.5 * height
            radec = wcs.pixelToSky(xc, yc)
            ra = radec.getLongitude(afwCoord.DEGREES)
            dec = radec.getLatitude(afwCoord.DEGREES)
            radius = wcs.pixelScale() * math.hypot(xc, yc) * 1.1

            policy = pexPolicy.Policy()
            policy.set('matchThreshold', 30)
            solver = measAstrom.createSolver(policy, self.log)
            idName = 'id'
            anid = meta.getInt('ANINDID')

            cat = solver.getCatalogue(ra, dec, radius, filter, idName, anid)
            ref = cat.refsources
            inds = cat.inds

            referrs, stargal = None, None
            colnames = [c.name for c in solver.getTagAlongColumns(anid)]

            col = 'starnotgal'
            if col in colnames:
                stargal1 = solver.getTagAlongBool(anid, col, inds)
                stargal = []
                for i in range(len(stargal1)):
                    stargal.append(stargal1[i])

            fdict = maUtils.getDetectionFlags()

            keepref = []
            keepi = []
            for i in xrange(len(ref)):
                x, y = wcs.skyToPixel(ref[i].getRa(), ref[i].getDec())
                if x < 0 or y < 0 or x > width or y > height:
                    continue
                ref[i].setXAstrom(x)
                ref[i].setYAstrom(y)
                if stargal is not None and stargal[i]:
                    ref[i].setFlagForDetection(ref[i].getFlagForDetection() | fdict["STAR"])
                keepref.append(ref[i])
                keepi.append(i)

            ref = keepref

            if referrs is not None:
                referrs = [referrs[i] for i in keepi]
            if stargal is not None:
                stargal = [stargal[i] for i in keepi]

            stargal = stargal
            referrs = referrs

            measAstrom.joinMatchList(matchList, ref, first=True, log=self.log)
            args = {}
            if True:
                # ugh, mask and offset req'd because source ids are assigned at write-time
                # and match list code made a deep copy before that.
                # (see svn+ssh://svn.lsstcorp.org/DMS/meas/astrom/tickets/1491-b r18027)
                args['mask'] = 0xffff
                args['offset'] = -1
#            self.log.setThreshold(self.log.DEBUG)
            print len(matchList), len(sourceList)
            measAstrom.joinMatchList(matchList, sourceList, first=False, log=self.log, **args)
            output.append(matchList)
        return output


    def read(self, which, dataId, ignore=False):
        """Read some data.

        @param which Type of data to read
        @param dataId Data identifier for butler
        @returns Raw exposures
        """
        identifiers = self.lookup(dataId)
        data = list()
        for ident in identifiers:
            ident.update(dataId)
            if not self.inButler.datasetExists(which, ident):
                if not ignore:
                    raise RuntimeError("Data type %s does not exist for %s" % (which, ident))
            else:
                self.log.log(self.log.INFO, "Reading %s: %s" % (which, ident))
                data.append(self.inButler.get(which, ident))
        return data

    def detrends(self, dataId, config):
        """Read detrends for a CCD.

        @param dataId Data identifier for butler
        @param config Configuration (for which detrends to read)
        @returns Dict of lists for each detrend type
        """
        identifiers = self.lookup(dataId)
        detrends = dict()
        do = config['do']['isr']
        for kind in ('bias', 'dark', 'flat'):
            if do[kind]:
                detList = list()
                for ident in identifiers:
                    ident.update(dataId)
                    if not self.inButler.datasetExists(kind, ident):
                        raise RuntimeError("Data type %s does not exist for %s" % (which, ident))
                    self.log.log(self.log.INFO, "Reading %s for %s" % (kind, ident))
                    detrend = self.inButler.get(kind, ident)
                    detList.append(detrend)
                detrends[kind] = detList
        # Fringe depends on the filter
        if do['fringe']:
            fringeList = list()
            for ident in identifiers:
                ident.update(dataId)
                filterList = self.inButler.queryMetadata("raw", None, "filter", ident)
                assert len(filterList) == 1, "Filter query is non-unique: %s" % filterList
                filtName = filterList[0]
                if filtName in config['fringe']['filters']:
                    if not self.inButler.datasetExists('fringe', ident):
                        raise RuntimeError("Data type fringe does not exist for %s" % ident)
                    self.log.log(self.log.INFO, "Reading fringe for %s" % (ident))
                    fringe = self.inButler.get("fringe", ident)
                    fringeList.append(fringe)
            if len(fringeList) > 0:
                detrends['fringe'] = fringeList
        return detrends

    def write(self, dataId, exposure=None, psf=None, sources=None, matches=None, matchMeta=None, **kwargs):
        """Write processed data.

        @param dataId Data identifier for butler
        @param exposure Exposure to write, or None
        @param psf PSF to write, or None
        @param sources Sources to write, or None
        @param mathces Matches to write, or None
        """
        if exposure is not None:
            self.log.log(self.log.INFO, "Writing exposure: %s" % (dataId))
            self.outButler.put(exposure, 'calexp', dataId)
        if psf is not None:
            self.log.log(self.log.INFO, "Writing PSF: %s" % (dataId))
            self.outButler.put(psf, 'psf', dataId)
        if sources is not None:
            self.log.log(self.log.INFO, "Writing sources: %s" % (dataId))
            for src in sources:
                src.setAstrometry(None)
                src.setPhotometry(None)
                src.setShape(None)
            self.outButler.put(afwDet.PersistableSourceVector(sources), 'src', dataId)
        if matches is not None:
            try:
                self.log.log(self.log.INFO, "Writing matches: %s" % (dataId))
                smv = afwDet.SourceMatchVector()
                for match in matches:
                    smv.push_back(match)
                self.outButler.put(afwDet.PersistableSourceMatchVector(smv, matchMeta), 'matches', dataId)

                matchSources = afwDet.SourceSet()
                for match in matches:
                    matchSources.push_back(match.first)
                self.outButler.put(afwDet.PersistableSourceVector(matchSources), 'matchedsources', dataId)
                
            except Exception, e:
                self.log.log(self.log.WARN, "Unable to write matches: %s" % e)
        return
