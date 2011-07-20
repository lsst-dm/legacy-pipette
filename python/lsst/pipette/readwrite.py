#!/usr/bin/env python

import os
import re
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

from lsst.pipette.timer import timecall

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
        thisMapperBuffer[key] = mapper(root=root, registry=registry, calibRoot=calibRoot)
    return thisMapperBuffer[key]

def parseRoot(root):
    root = re.sub("~", os.environ['HOME'], root)
    return root                                  


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
            roots = config['roots'] if config.has_key('roots') else {}
            dataRoot = parseRoot(roots['data']) if roots.has_key('data') else None
            calibRoot = parseRoot(roots['calib']) if roots.has_key('calib') else None
            if inMap:
                mapp = getMapper(mapper, root=dataRoot, calibRoot=calibRoot)
            else:
                outRoot = parseRoot(roots['output']) if roots.has_key('output') else None
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
                
                mapp = getMapper(mapper, root=outRoot, registry=registry, calibRoot=calibRoot)

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

    @timecall
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
            self.log.log(self.log.DEBUG, "Reading: %s" % (ident))
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
        sources = self.read('icSrc', dataId, ignore=ignore)
        matches = self.read('icMatch', dataId, ignore=ignore)
        headers = self.read('calexp_md', dataId, ignore=ignore)

        output = []
        for sourceList, matchList, header in zip(sources, matches, headers):
            wcs = afwImage.makeWcs(header)
            width, height = header.get('NAXIS1'), header.get('NAXIS2')

            matches = measAstrom.generateMatchesFromMatchList(matchList, sourceList.getSources(),
                                                              wcs, width, height, log=self.log)

            output.append(matches)
        return output


    @timecall
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
            for i, butler in enumerate([self.inButler, self.outButler]):
                if not butler.datasetExists(which, ident):
                    if i == 1:
                        if not ignore:
                            raise RuntimeError("Data type %s does not exist for %s" % (which, ident))
                else:
                    self.log.log(self.log.DEBUG, "Reading %s: %s" % (which, ident))
                    data.append(butler.get(which, ident))
                    break
        return data

    @timecall
    def detrends(self, dataId, config):
        """Read detrends for a CCD.

        @param dataId Data identifier for butler
        @param config Configuration (for which detrends to read)
        @returns Dict of lists for each detrend type
        """
        identifiers = self.lookup(dataId)
        detrends = dict()
        do = config['do']['isr']
        if not do['enabled']:
            return detrends

        for kind in ('bias', 'dark', 'flat'):
            if do[kind]:
                detList = list()
                for ident in identifiers:
                    ident.update(dataId)
                    if not self.inButler.datasetExists(kind, ident):
                        raise RuntimeError("Data type %s does not exist for %s" % (kind, ident))
                    self.log.log(self.log.DEBUG, "Reading %s for %s" % (kind, ident))
                    detrend = self.inButler.get(kind, ident)
                    detList.append(detrend)
                detrends[kind] = detList
        # Fringe depends on the filter
        if do['fringe'] and config['fringe'].has_key('filters'):
            fringeList = list()
            for ident in identifiers:
                ident.update(dataId)
                filterList = self.inButler.queryMetadata("raw", None, "filter", ident)
                assert len(filterList) == 1, "Filter query is non-unique: %s" % filterList
                filtName = filterList[0]
                if filtName in config['fringe']['filters']:
                    if not self.inButler.datasetExists('fringe', ident):
                        raise RuntimeError("Data type fringe does not exist for %s" % ident)
                    self.log.log(self.log.DEBUG, "Reading fringe for %s" % (ident))
                    fringe = self.inButler.get("fringe", ident)
                    fringeList.append(fringe)
            if len(fringeList) > 0:
                detrends['fringe'] = fringeList
        return detrends

    @timecall
    def write(self, dataId, exposure=None, psf=None, sources=None,
              matches=None, matchMeta=None, **kwargs):
        """Write processed data.

        @param dataId Data identifier for butler
        @param exposure Exposure to write, or None
        @param psf PSF to write, or None
        @param sources Sources to write, or None
        @param matches Matches to write, or None
        """
        if exposure is not None:
            self.log.log(self.log.INFO, "Writing exposure: %s" % (dataId))
            self.outButler.put(exposure, 'calexp', dataId)
        if psf is not None:
            self.log.log(self.log.INFO, "Writing PSF: %s" % (dataId))
            self.outButler.put(psf, 'psf', dataId)
        if sources is not None:
            self.log.log(self.log.INFO, "Writing sources: %s" % (dataId))
            self.outButler.put(afwDet.PersistableSourceVector(sources), 'src', dataId)
        if matches is not None:
            try:
                self.log.log(self.log.INFO, "Writing matches: %s" % (dataId))
                smv = afwDet.SourceMatchVector()
                for match in matches:
                    smv.push_back(match)
                self.outButler.put(afwDet.PersistableSourceMatchVector(smv, matchMeta), 'icMatch', dataId)

                matchSources = afwDet.SourceSet()
                for match in matches:
                    matchSources.push_back(match.second)
                self.outButler.put(afwDet.PersistableSourceVector(matchSources), 'icSrc', dataId)
                
            except Exception, e:
                self.log.log(self.log.WARN, "Unable to write matches: %s" % e)
        return
