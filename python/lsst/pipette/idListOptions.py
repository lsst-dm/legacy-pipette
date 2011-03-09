#
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#
import os
import sys

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import options
import readwrite

class IdListOptionParser(options.OptionParser):
    """An lsst.pipette.options.OptionParser specialized for lists of input data.
    
    Handles different data sources.
    Missing fields are treated as wildcard "all".
    Adds getIdList method.
    
    @todo:
    - Add support for more cameras
    """
    def __init__(self, usage="usage: %prog dataSource [options]", **kwargs):
        """Construct an option parser
        """
        options.OptionParser.__init__(self, usage=usage, **kwargs)
        self._dataSource = None
    
    def _handleDataSource(self):
        """Set attributes based on self._dataSource
        
        Called by parse_args before the main parser is called
        """
        if self._dataSource == "lsstSim":
            import lsst.obs.lsstSim
            self._mappers = lsst.obs.lsstSim.LsstSimMapper
            self._idNameCharTypeList = (
                ("visit",  "V", int),
                ("filter", "f", str),
                ("raft",   "r", str),
                ("sensor", "s", str),
            )
            self._extraFileKeys = ["channel"]
            self._defaultScale = 0.14 # arcsec/pixel
        elif self._dataSource == "suprimecam":
            import lsst.obs.suprimecam
            self._mappers = lsst.obs.suprimecam.SuprimecamMapper
            self._idNameCharTypeList = (
                ("visit",  "V", int),
                ("ccd", "c", str),
            )
            self._extraFileKeys = []
            self._defaultScale = 0.14 # arcsec/pixel
        else:
            raise RuntimeError("Unsupported dataSource: %s" % self._dataSource)
    
    def parse_args(self, policyPath, requiredArgs=()):
        """Parse the arguments
        
        @param[in] policyPath: path to main policy dictionary
        @param[in] requiredArgs: list of required arguments, in addition to the standard ones
        
        @return
        - config: a Configuration object
        - opts: command-line options, as from optparse
        - args: command-line arguments, as from optparse
        
        Must be called before calling getReadWrite, getWcs, getWcsBBox, getIdList
        """
        if requiredArgs:
            requiredArgs = tuple(requiredArgs)
        else:
            requiredArgs = ()
        # dataSource must be the first (non-option) argument
        for arg in sys.argv[1:]:
            if arg.startswith("-"):
                continue
            self._dataSource = arg
            break
        else:
            if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
                print "For detailed help specify dataSource (e.g. lsstSim or suprimecam) followed by --help"
            else:            
                sys.stderr.write("Error: must specify dataSource (e.g. lsstSim or suprimecam)\n")
            self.print_usage()
            sys.exit(1)
        
        try:
            self._handleDataSource()
        except RuntimeError, e:
            sys.stderr.write("%s\n" % e)
            sys.exit(1)
            
        for idName, idChar, idType in self._idNameCharTypeList:
            if idChar:
                self.add_option("-%s" % (idChar,), "--%ss" % (idName,), dest=idName,
                                help="%ss to run, colon-delimited" % (idName,))
            else:
                self.add_option("--%ss" % (idName,), dest=idName,
                                help="%s to run, colon-delimited" % (idName,))

        config, opts, args = options.OptionParser.parse_args(self, policyPath)
    
        for reqArg in requiredArgs:
            if getattr(opts, reqArg) == None:
                sys.stderr.write("Error: must specify --%s\n" % (reqArg,))
                sys.exit(1)
    
        idNameList = [item[0] for item in self._idNameCharTypeList]
        self._readWrite = readwrite.ReadWrite(
            mappers = self._mappers,
            ccdKeys = idNameList,
            fileKeys = idNameList + self._extraFileKeys,
            config = config)

        # determine the valid data IDs that match the user's specifications
        # start by determining a list of IDs that match user's specifications
        argList = list()
        iterList = list()
        idDict = dict()
        for idName, idChar, idType in self._idNameCharTypeList:
            argStr = getattr(opts, idName)
            if not argStr:
                continue
            idDict[idName] = [idType(item) for item in argStr.split(":")]
            argList.append("%s=%sItem" % (idName, idName))
            iterList.append("for %sItem in idDict['%s']" % (idName, idName))
        queryIdListExpr = "[dict(%s) %s]" % (", ".join(argList), " ".join(iterList))
        queryIdList = eval(queryIdListExpr)

        butler = self._readWrite.inButler
        
        goodTupleSet = set() # use set to avoid duplicates but sets cannot contain ID dicts so store tuples
        for queryId in queryIdList:
            # queryMetadata finds all possible matches, even ones that don't exist
            # (and it only works for raw, not calexp)
            # so follow it with datasetExists to find the good data IDs
            candidateTupleList = butler.queryMetadata("raw", None, idNameList, **queryId)
            newGoodIdSet = set(candTup for candTup in candidateTupleList
                if butler.datasetExists("calexp", dict(zip(idNameList, candTup))))
            goodTupleSet |= newGoodIdSet
            
        self._idList = [dict(zip(idNameList, goodTup)) for goodTup in goodTupleSet]
        
        return config, opts, args
    
    def getReadWrite(self):
        """Return a pipette ReadWrite object. You must call parse_args first.
        """
        return self._readWrite
    
    def getIdList(self):
        """Return a list of IDs of data to process
        """
        return self._idList
