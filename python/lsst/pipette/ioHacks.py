import re
import os, sys
import numpy
import pyfits
import math

import lsst.afw.detection as afwDet
import lsst.afw.geom      as afwGeom

try:
    from IPython.core.debugger import Tracer;
    debug_here = Tracer()
except:
    pass

class NoLogging(object):
    DEBUG = 0
    INFO = 0
    WARN = 0
    FATAL = 0
    def log(self, *args):
        pass

###################################################################
#
# We'll define all the values we're interested in right here.  There are four functions
# below which will read or write these values in either text or FITS.
#
# As long as the 'outlist' has a full description for the values we want.
#
###################################################################

def genOutputDict(outlist):
    # lets put the entries in a dictionary,
    # ... we'll never remember which index has, say, the 'get' method stored.
    dictList = []
    for out in outlist:
        outdict = { "label":out[0],      # The label to use in the header
                    "get": out[1],       # the method to call to get the value
                    "set": out[2],       # the method to call to set the value
                    "headform": out[3],  # the format string (c-style) for the header label
                    "dataform": out[4],  # the format string (c-style) for the data
                    "pytype": out[5],    # the python type function to cast an input value to
                    "dtype": out[5].__name__ + str(out[6]),  # the dtype string (eg int32) for fits header
                    "bits": out[6],      # the number of bits for the value (needed as flags are 16 bit)
                    "fitstype": out[7],  # The fits type (I, E, etc) to write file
                    "side": out[8],      # For matchlists, the side to call
                    "angle": out[9],
                    "units": out[10],
                    }
        dictList.append(outdict)
    return dictList

def getSourceOutputListHsc(addRefFlux=False, simple=False):

    # We have pulled all the schema-based entries out. There are still a few stragglers:
    outlistSimple = [
        ["objId",    "getId",               "setId",               "%5s",        "%06d",       int,     32,   "K", 0, False, None ],
        ["objFlags", "getFlagForDetection", "setFlagForDetection", "%6s",        "0x%04x",     int,     16,   "I", 0, False, None ],
        ["ra",       "getRa",               "setRa",               "%10s",       "%10.6f",     float,   64,   "D", 0, True,  'deg'],
        ["dec",      "getDec",              "setDec",              "%10s",       "%10.6f",     float,   64,   "D", 0, True,  'deg'],
        #["raErr",   "getRaErrForWcs",      "setRaErrForWcs",      "%10s",       "%10.6f",     float,   32,   "E", 0, True,  'deg'],
        #["decErr",  "getDecErrForWcs",     "setDecErrForWcs",     "%10s",       "%10.6f",     float,   32,   "E", 0, True,  'deg'],
        ]
    
    outlist1 = [
        # label    get method        set method       headformat   dataformat   pytype   bits  fitstype
        ["amp",   "getAmpExposureId",    "setAmpExposureId",    "%4s",  "%04d",   int,   32, "I", 0, False, None],
        ["x",     "getXAstrom",          "setXAstrom",          "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ["xerr",  "getXAstromErr",       "setXAstromErr",       "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ["y",     "getYAstrom",          "setYAstrom",          "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ["yerr",  "getYAstromErr",       "setYAstromErr",       "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ["Ixx",   "getIxx",              "setIxx",              "%9s",  "%9.3f",  float, 32, "E", 0, False, None],
        ["Ixy",   "getIxy",              "setIxy",              "%9s",  "%9.3f",  float, 32, "E", 0, False, None],
        ["Iyy",   "getIyy",              "setIyy",              "%9s",  "%9.3f",  float, 32, "E", 0, False, None],
        ["f_psf", "getPsfFlux",          "setPsfFlux",          "%11s", "%11.1f", float, 32, "E", 0, False, None],
        ["f_ap",  "getApFlux",           "setApFlux",           "%11s", "%11.1f", float, 32, "E", 0, False, None],
        ["flags", "getFlagForDetection", "setFlagForDetection", "%6s",  "0x%04x", int,   16, "I", 0, False, None],
        ]
    
    outlistRef = [
        ["f_ref_psf", "getPsfFlux",      "setPsfFlux",          "%11s",   "%g",   float, 32, "E", 0, False, None],
        ]
    
    outlist = outlistSimple[:]
    if not simple:
        outlist.extend(outlist1[:])
    if addRefFlux:
        outlist.extend(outlistRef[:])
    return genOutputDict(outlist)

def getMatchOutputList():
    outlist = [
        ["catId",     "getId",               None,                  "%8s",  "%08df",  int,   32, "K", 1, False, None],
        ["catRa",     "getRa",               None,                  "%10s", "%10.6f", float, 64, "D", 1, True,  'deg'],
        ["catDec",    "getDec",              None,                  "%10s", "%10.6f", float, 64, "D", 1, True,  'deg'],
        ["catFlux",   "getPsfFlux",          None,                  "%8s",  "%8.3f",  float, 32, "E", 1, False, None],
        ["objId",     "getId",               "setId",               "%6s",  "%06d",   int,   32, "K", 0, False, None],
        ["objFlags",  "getFlagForDetection", "setFlagForDetection", "%6s",  "0x%04x", int,   16, "I", 0, False, None],
        ["ra",        "getRa",               "setRa",               "%10s", "%10.6f", float, 64, "D", 0, True,  'deg'],
        ["dec",       "getDec",              "setDec",              "%10s", "%10.6f", float, 64, "D", 0, True,  'deg'],
        ["x",         "getXAstrom",          "setXAstrom",          "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ["xerr",      "getXAstromErr",       "setXAstromErr",       "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ["y",         "getYAstrom",          "setYAstrom",          "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ["yerr",      "getYAstromErr",       "setYAstromErr",       "%8s",  "%8.3f",  float, 32, "E", 0, False, 'pixels'],
        ]
    return genOutputDict(outlist)
        
def writeMatchListAsFits(matchList, fileName, log=NoLogging()):
    """ write matchList to a given filename with pyfits. """

    if matchList != None and len(matchList) > 0:
        nSource = len(matchList)
        outputs = getMatchOutputList()
        nOut = len(outputs)

        log.log(log.DEBUG, "Writing %d matches" % nOut)

        # create the arrays and fill them
        arrays = {}
        for i in range(nOut):
            columnName = outputs[i]["label"]
            arrays[columnName] = numpy.zeros(nSource, dtype=outputs[i]["dtype"])

        for i in range(nOut):
            columnName = outputs[i]["label"]
            isangle = outputs[i]['angle']
            for j,sourceMatch in enumerate(matchList):
                s1 = sourceMatch.first
                s2 = sourceMatch.second
                if outputs[i]['side'] == 1:
                    s = s1              # catalog
                else:
                    s = s2              # source
                getMethod = getattr(s, outputs[i]["get"])
                X = getMethod()
                if isangle:
                    arrays[columnName][j] = X.asDegrees()
                else:
                    arrays[columnName][j] = X

        # create the column defs
        columnDefs = []
        for i in range(nOut):
            columnName = outputs[i]["label"]
            columnDefs.append(pyfits.Column(name=columnName,
                                            format=outputs[i]["fitstype"],
                                            unit=outputs[i]['units'],
                                            array=arrays[columnName]))

        tabhdu = pyfits.new_table(columnDefs, nrows=nSource)
        hdulist = pyfits.HDUList([pyfits.PrimaryHDU(), tabhdu])
        hdulist.writeto(fileName, clobber=True)


###############################################################################
#
# read data from a FITS file with pyfits, and load the values into a SourceSet.
#
###############################################################################
def readSourcesetFromFits(baseName, hdrKeys=[], outputStyle="hsc"):

    fits = pyfits.open("%s.fits" % (baseName))
    hdu = 1
    data = fits[hdu].data
    hdr = fits[0].header
    fits.close()

    outputs = getOutputList(outputStyle)
    nOut = len(outputs)

    # get any requested hdrs
    hdrInfo = {}
    for hdrKey in hdrKeys:
        hdrInfo[hdrKey] = hdr[hdrKey]

    sourceSet = afwDet.SourceSet()
    for i in range(len(data)):

        source = afwDet.Source()
        sourceSet.append(source)

        for j in range(nOut):
            setMethod = getattr(source, outputs[j]["set"])
            thistype = outputs[j]["pytype"]
            value = data[i].field(outputs[j]["label"])
            if outputs[j]['angle']:
                setMethod(value * afwGeom.degrees)
            else:
                try:
                    setMethod(thistype(value))
                except:
                    setMethod(thistype("nan"))



    #################################################
    # input the matchlist
    ################################################
    matchList = readMatchListFits(baseName, outputStyle)

    return sourceSet, matchList, hdrInfo


###############################################################################
#
# read match lists from a FITS file with pyfits
#
###############################################################################
def readMatchListFits(baseName, outputStyle="hsc"):

    #################################################
    # input the matchlist
    # Unless basename is an instance of str,
    # it is assumed to be an `file-like' object
    ################################################

    matchList = []

    if isinstance(baseName, str):
        if os.path.exists("%s.match.fits" % (baseName)):
            fits = pyfits.open("%s.match.fits" % (baseName))
        else:
            fits = None
    else:
        # baseName is actually an file-like object
        fits = pyfits.open(baseName)

    if fits:

        hdu = 1
        data = fits[hdu].data
        fits.close()

        outputs = getOutputList(outputStyle)
        nOut = len(outputs)

        for i in range(len(data)):

            s1 = afwDet.Source()
            s2 = afwDet.Source()
            matchList.append(afwDet.SourceMatch(s1, s2, 0.0))

            for j in range(nOut):
                if outputs[j]['label'] in ['ra','dec']:
                    s = s1
                else:
                    s = s2

                setMethod = getattr(s, outputs[j]["set"])
                thistype = outputs[j]["pytype"]
                value = data[i].field(outputs[j]["label"])
                if outputs[j]['angle']:
                    setMethod(value * afwGeom.degrees)
                else:
                    setMethod(thistype(value))

    return matchList

class SchemaDuck(object):
    """ Pretend to be a Schema. Unused for now, because we need to access the schema
        from the object, which I can't fake that easily.
    """
    
    class SchemumDuck(object):
        def __init__(self, name, type, unit):
            self.name = name
            self.type = type
            self.unit = unit

        def getType(self):
            return self.type
        def getName(self):
            return self.name
        def getUnit(self):
            return self.unit

        def isArray(self):
            return False
        
    def __init__(self):
        ''' Incorporate, say, the following:
        ["id",     "getId",          "setId",                    "%5s",       "%06d",       int,   32,   "K"],
        ["amp",    "getAmpExposureId","setAmpExposureId",        "%4s",       "%04d",   int,   32,   "I"],
        ["flags",  "getFlagForDetection", "setFlagForDetection", "%6s",        "0x%04x",      int,     16,   "I"],
        '''

        self.schema = []

    def me(self):
        return self

    def getSchema(self):
        return self.schema


schema2FitsTypes = {
    afwDet.Schema.CHAR: 'B',
    afwDet.Schema.SHORT: 'I',
    afwDet.Schema.INT: 'J',
    afwDet.Schema.LONG: 'K',
    afwDet.Schema.FLOAT: 'E',
    afwDet.Schema.DOUBLE: 'D'
    }

schema2NumpyTypes = {
    afwDet.Schema.CHAR: 'i1',
    afwDet.Schema.SHORT: 'i2',
    afwDet.Schema.INT: 'i4',
    afwDet.Schema.LONG: 'i8',
    afwDet.Schema.FLOAT: 'f4',
    afwDet.Schema.DOUBLE: 'f8'
    }

def getValue(measurement,               # Meaurement from which to get value
             entry,                     # Entry in schema for meaurement of interest
             ):
    if entry.getType() in (afwDet.Schema.CHAR, afwDet.Schema.SHORT, afwDet.Schema.INT, afwDet.Schema.LONG):
        value = measurement.getAsLong(entry)
    else:
        value = measurement.get(entry)
    return value


def getFitsColumns(sourceSet, outputs):
    """ Return pyfits columns defined by the outputs structure.

    This is hopefully temporary, until schemas define everything
    we want to write. It uses the existing io.writeFits data structures.
    """

    nSource = len(sourceSet)
    nOut = len(outputs)

    # create the arrays and fill them
    arrays = {}
    for i in range(nOut):
        columnName = outputs[i]["label"]
        arrays[columnName] = numpy.zeros(nSource, dtype=outputs[i]["dtype"])

        for j,source in enumerate(sourceSet):
            getMethod = getattr(source, outputs[i]["get"])
            X = getMethod()
            if outputs[i]['angle']:
                X = X.asDegrees()
            arrays[columnName][j] = X

    # create the column defs
    columnDefs = []
    for i in range(nOut):
        columnName = outputs[i]["label"]
        columnDefs.append(pyfits.Column(name=columnName,
                                        format=outputs[i]["fitstype"],
                                        unit=outputs[i]['units'],
                                        array=arrays[columnName]))
    return columnDefs

    
def schema2pyfits(objs, schemaNamePrefix, getterName, log=NoLogging()):
    """ Return pyfits Columns for all the schema entries """

    nobj = len(objs)
    if nobj == 0:
        raise RuntimeError("If you need to construct a FITS table from an empty list, do it yourself...")
    
    npCols = []
    colSchemas = []
    colNames = []
    getter = getattr(objs[0], getterName)
    log.log(log.DEBUG, "Getting schema for %s with %s" % (schemaNamePrefix, getterName))
    values = getter()
    for i, val in enumerate(values):
        if hasattr(val, 'getAlgorithm'):
            # "getAlgorithm" is the camel's nose under the tent of abstraction -- CPL
            schemaName = "%s_%s" % (schemaNamePrefix, val.getAlgorithm())
        else:
            schemaName = schemaNamePrefix
            
        for s in val.getSchema():
            # Need to recurse? CPL
            try:
                fitsType = schema2FitsTypes[s.getType()]
                numpyType = schema2NumpyTypes[s.getType()]
            except KeyError:
                raise RuntimeError("schema type %s does not (yet) have a corresponding FITS type.")
            
            if s.isArray():
                n = s.getDimen()
                numpyType = '%d%s' % (n, numpyType)
                print "WARNING!!!!! schema arrays have not been tested yet!"
            else:
                n = 1

            npCols.append(numpy.zeros(nobj, dtype=numpyType))
            colSchemas.append(s)
            if schemaName:
                colName = "%s_%s" % (schemaName, s.getName())
            else:
                colName = s.getName()
            # A better behaved person might do: colName = colName.lower()
            colNames.append(colName)
    log.log(log.DEBUG, "Column names for %s: %s" % (schemaNamePrefix, ",".join(colNames)))

    for i in range(nobj):
        getter = getattr(objs[i], getterName)
        s_i = 0
        for val in getter():
            for s in val.getSchema():
                # I'm guessing about arrays in schemas. -- CPL
                if s.isArray():
                    v = getValue(val, s)
                    for v_i in range(s.getDimens()):
                        npCols[s_i][i][v_i] = v[v_i]
                else:
                    npCols[s_i][i] = getValue(val, s)
                s_i += 1

    log.log(log.DEBUG, "Generating columns for %s" % schemaNamePrefix)
    fitsCols = []
    for npCol, colSchema, colName in zip(npCols, colSchemas, colNames):
        fitsType = schema2FitsTypes[colSchema.getType()]
        if colSchema.isArray():
            fitsType = "%d%s" % (s.getDimens(), fitsType)

        col = pyfits.Column(name=colName,
                            format=fitsType,
                            unit=colSchema.getUnits(),
                            array=npCol)
        fitsCols.append(col)

    log.log(log.DEBUG, "Done parsing schema for %s" % schemaNamePrefix)
    return fitsCols

def writeSourceSetAsFits(sourceSet, filename, hdrInfo=[], clobber=False, log=NoLogging()):
    """Write a SourceSet as a FITS file. Crawls the Scheme for most columns, uses manual hacks for the rest. """
    log.log(log.DEBUG, "Writing source FITS table...")

    if not sourceSet:
        raise RuntimeError("Please provide at least one Source")

    source = sourceSet[0]

    measurementTypes = (("astrometry", "getAstrometry"),
                        ("photometry", "getPhotometry"),
                        ("shape", "getShape"),
                        )
    columns = []

    # Start with hacky manual columns
    log.log(log.DEBUG, "Adding manual columns...")
    columns.extend(getFitsColumns(sourceSet, getSourceOutputListHsc(addRefFlux=True)))
                   
    # Add in nice schema-based columns
    for measureType, getterName in measurementTypes:
        log.log(log.DEBUG, "Parsing schema from %s..." % getterName)
        fitsCols = schema2pyfits(sourceSet, measureType, getterName, log=log)
        columns.extend(fitsCols)

    log.log(log.DEBUG, "Opening table with %d columns..." % len(columns))
    tblHdu = pyfits.new_table(columns)

    log.log(log.DEBUG, "Setting header...")
    primHdu = pyfits.PrimaryHDU()
    hdr = primHdu.header
    for key, value in hdrInfo.items():
        if not (isinstance(value, list) or isinstance(value, tuple)):
            value = [value,]

        for v in value:
            cardName = key if len(key) <= 8 else "HIERARCH %s" % (key)
            hdr.update(cardName, v, key)

    log.log(log.DEBUG, "Writing out %d columns to %s..." % (len(columns), filename))
    hdulist = pyfits.HDUList([primHdu, tblHdu])
    hdulist.writeto(filename, clobber=clobber)

def readSourceSetFromFits(filename):
    """Read a SourceSet from a FITS file"""
    raise NotImplementedError("some other day...")

