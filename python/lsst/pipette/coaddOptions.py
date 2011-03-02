import os
import sys

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import options
import readwrite

class CoaddOptionParser(options.OptionParser):
    """OptionParser is an options.OptionParser specialized for coaddition.
    """
    def __init__(self, dataType):
        """Construct an option parser

        @input dataType: type of data you are processing, e.g. "lsstSim"
            Warning: not all data types are supported yet
        """
        options.OptionParser.__init__(self)
        
        if dataType == "lsstSim":
            import lsst.obs.lsstSim
            self._mappers = lsst.obs.lsstSim.LsstSimMapper
            self._idNameCharTypeList = (
                ("visit",  "V", int),
                ("filter", "f", str),
                ("raft",   "r", str),
                ("sensor", "s", str),
            )
            self._extraFileKeys = ["channel"]
        else:
            raise RuntimeError("Unsupported dataType type: %s" % dataType)
            
        self.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                          help="rerun name (default=%default)")
        for idName, idChar, idType in self._idNameCharTypeList:
            if idChar:
                self.add_option("-%s" % (idChar,), "--%ss" % (idName,), dest=idName,
                    help="%ss to run, colon-delimited" % (idName,))
            else:
                self.add_option("--%ss" % (idName,), dest=idName,
                    help="%s to run, colon-delimited" % (idName,))
        self.add_option("--radec", dest="radec", type="float", nargs=2,
                          help="RA, Dec of center of skycell, degrees")
        self.add_option("--scale", dest="scale", type="float",
                          help="Pixel scale for skycell, arcsec/pixel")
        self.add_option("--size", dest="size", nargs=2, type="int",
                          help="Size in x and y for skycell, pixels")
    
        default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "lsstSim_coadd.paf")
    
    def parse_args(self, default):
        """Parse the arguments
        
        @return
        - config: a Configuration object
        - opts: command-line options, as from optparse
        - args: command-line arguments, as from optparse
        
        Must be called before calling getReadWrite, getWcs, getWcsBBox, getIdList
        """
        config, opts, args = options.OptionParser.parse_args(self, default)
    
#         if len(args) > 0 or len(sys.argv) == 1:
#             self.print_help()
#             sys.exit(1)
        for reqArg in ("rerun", "radec", "scale", "size"):
            if getattr(opts, reqArg) == None:
                print "Error: must specify --%s" % (reqArg,)
                self.print_help()
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
    
        crval = afwGeom.makePointD(opts.radec[0], opts.radec[1])
        crpix = afwGeom.makePointD(opts.size[0] / 2.0, opts.size[1] / 2.0)
        self._coaddWcs = afwImage.createWcs(crval, crpix, opts.scale / 3600.0, 0.0, 0.0, opts.scale / 3600.0)
        self._coaddBBox = afwGeom.BoxI(afwGeom.makePointI(0,0), afwGeom.makeExtentI(opts.size[0], opts.size[1]))
        
        roots = config["roots"]
        self._coaddBaseName = os.path.join(roots["output"], opts.rerun)
        
        return config, opts, args
    
    def getReadWrite(self):
        """Return a pipette ReadWrite object. You must call parse_args first.
        """
        return self._readWrite
    
    def getCoaddBasename(self):
        """Return the coadd base name. You must call parse_args first.
        """
        return self._coadBaseName
        
    def getCoaddWcs(self):
        """Return WCS for coadd. You must call parse_args first.
        """
        return self._coaddWcs
    
    def getCoaddBBox(self):
        """Return coadd bounding box (as an afwGeom::BoxI). You must call parse_args first.
        """
        return self._coaddBBox
        
    def getIdList(self):
        """Return a list of data IDs for the input butler
        """
        return self._idList
