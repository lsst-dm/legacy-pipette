#!/usr/bin/env python
import os
import lsst.pex.logging as pexLog
import lsst.daf.persistence as dafPersist
import lsst.afw.cameraGeom as cameraGeom
import lsst.afw.cameraGeom.utils as cameraGeomUtils
import lsst.afw.image as afwImage
import lsst.afw.detection as afwDet

"""This module provides I/O for pipette (LSST algorithms testing)"""



def initMapper(mapper, config, log, inMap=True):
    """Utility function to initialize an input or output mapper"""
    
    if issubclass(mapper, dafPersist.Mapper):
        # It's a class that we're to instantiate
        if config is None:
            # We'll try this, but don't expect it will work...
            log.log(self.log.WARN, "No configuration provided for mapper.")
            mapp = mapper()
        else:
            roots = config['roots']
            if inMap:
                mapp = mapper(root=roots['data'], calibRoot=roots['calib'])
            else:

                # if there's no output registry, use the input registry
                outRegistry = os.path.join(roots['output'], "registry.sqlite3")
                inRegistry = os.path.join(roots['data'], "registry.sqlite3")
                if os.path.exists(outRegistry):
                    registry = outRegistry
                elif (os.path.exists(inRegistry)):
                    registry = inRegistry
                else:
                    raise RuntimeError("Unable to find a registry for output mapper")
                
                mapp = mapper(root=roots['output'], registry=registry)

    elif isinstance(mapper, dafPersist.Mapper):
        self.mapp = mapper
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
        identifiers = self.lookup(dataId)
        exposures = list()
        for ident in identifiers:
            ident.update(dataId)
            self.log.log(self.log.INFO, "Reading: %s" % (ident))
            exp = self.inButler.get('raw', ident)
            if isinstance(exp, afwImage.ExposureU):
                exp = exp.convertF()
            exposures.append(exp)
        return exposures

    def read(self, which, dataId):
        """Read some data.

        @param which Type of data to read
        @param dataId Data identifier for butler
        @returns Raw exposures
        """
        identifiers = self.lookup(dataId)
        data = list()
        for ident in identifiers:
            ident.update(dataId)
            self.log.log(self.log.INFO, "Reading %s: %s" % (which, ident))
            data.append(self.inButler.get(which, ident))
        return data

    def detrends(self, dataId, config):
        """Read detrends for a CCD.

        @param dataId Data identifier for butler
        @param config Configuration (for which detrends to read)
        @returns List of dicts with detrend exposures
        """
        identifiers = self.lookup(dataId)
        detrends = list()
        for ident in identifiers:
            ident.update(dataId)
            do = config['do']
            dets = dict()
            if do['bias']:
                self.log.log(self.log.INFO, "Reading bias for %s" % (ident))
                dets['bias'] = self.inButler.get('bias', ident)
            if do['dark']:
                self.log.log(self.log.INFO, "Reading dark for %s" % (ident))
                dets['dark'] = self.inButler.get('dark', ident)
            if do['flat']:
                self.log.log(self.log.INFO, "Reading flat for %s" % (ident))
                dets['flat'] = self.inButler.get('flat', ident)
            if do['fringe']:
                self.log.log(self.log.INFO, "Reading fringe for %s" % (ident))
                dets['fringe'] = self.inButler.get('fringe', ident)
            detrends.append(dets)
        return detrends

    def write(self, dataId, exposure=None, psf=None, sources=None, matches=None, **kwargs):
        """Write processed data.

        @param dataId Data identifier for butler
        @param exposure Exposure to write, or None
        @param psf PSF to write, or None
        @param sources Sources to write, or None
        @param mathces Matches to write, or None
        """
        if exposure is not None:
            self.log.log(self.log.INFO, "Writing exposure: %s" % (dataId))
            self.outButler.put(exposure, 'postISRCCD', dataId)
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
                self.outButler.put(afwDet.PersistableSourceMatchVector(smv), 'matches', dataId)
            except Exception, e:
                self.log.log(self.log.WARN, "Unable to write matches: %s" % e)
        return
