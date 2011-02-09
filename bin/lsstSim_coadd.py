#!/usr/bin/env python

import os
import sys

import lsst.afw.geom as afwGeom
import lsst.afw.image as afwImage
import lsst.coadd.utils as coaddUtils
import lsst.obs.lsstSim as lsstSim
import lsst.pipette.config as pipConfig
import lsst.pipette.stack as pipStack
import lsst.pipette.options as pipOptions
import lsst.pipette.readwrite as pipReadWrite

def coadd(idList, butler, radec, scale, size, policy):
    """Warp and stack images

    @param idList: list of image identity dictionaries
    @param butler: data butler for input images
    @param radec: right ascension, declination of center of coadd (radians)
    @param scale: scale of coadd (arcsec/pixel)
    @param size: x,y size of coadd (pixels)
    @param policy: a Policy object that must contain these policies:
        warpPolicy: see coadd_utils/policy/WarpDictionary.paf
        coaddPolicy: see coadd_utils/policy/CoaddDictionary.paf
    @output Stacked image
    """
    warpPolicy = policy.getPolicy("warpPolicy")
    coaddPolicy = policy.getPolicy("coaddPolicy")
    
    crval = afwGeom.makePointD(radec[0], radec[1])
    crpix = afwGeom.makePointD(size[0] / 2.0, size[1] / 2.0)
    coaddWcs = afwImage.createWcs(crval, crpix, scale / 3600.0, 0.0, 0.0, scale / 3600.0)
    coaddBBox = afwGeom.BoxI(afwGeom.makePointI(0,0), afwGeom.makeExtentI(size[0], size[1]))
    warper = coaddUtils.Warp.fromPolicy(warpPolicy)
    coadd = coaddUtils.Coadd.fromPolicy(coaddBBox, coaddWcs, coaddPolicy)
    for ident in idList:
#        print "Processing", ident
        # this will work once I start using commas in rafts and sensors. Meanwhile...
        #exposure = butler.get("calexp", ident)
        try:
            fileName = butler.mapper.calexpTemplate % ident
            filePath = os.path.join(butler.mapper.root, fileName)
        except Exception, e:
            print "Failed on %s: %s" % (ident, e)
        if not os.path.exists(filePath):
            print "Could not find file; skipping:", filePath
            continue
        print "Processing", filePath
        exposure = afwImage.ExposureF(filePath)
        warpedExposure = warper.warpExposure(coaddWcs, exposure, maxBBox = coaddBBox)
        coadd.addExposure(exposure)

    coaddExposure = coadd.getCoadd()
    weightMap = coadd.getWeightMap()

    return coaddExposure, weightMap


if __name__ == "__main__":
    idNameCharTypeList = (
        ("visit",  "V", int),
        ("filter", "f", str),
        ("raft",   "r", str),
        ("sensor", "s", str),
    )
    idNameList = [item[0] for item in idNameCharTypeList]

    parser = pipOptions.OptionParser()
    parser.add_option("-R", "--rerun", default=os.getenv("USER", default="rerun"), dest="rerun",
                      help="rerun name (default=%default)")
    for idName, idChar, idType in idNameCharTypeList:
        if idChar:
            parser.add_option("-%s" % (idChar,), "--%ss" % (idName,), dest=idName,
                help="%ss to run, colon-delimited" % (idName,))
        else:
            parser.add_option("--%ss" % (idName,), dest=idName,
                help="%s to run, colon-delimited" % (idName,))
    parser.add_option("--radec", dest="radec", type="float", nargs=2,
                      help="RA, Dec of center of skycell, degrees")
    parser.add_option("--scale", dest="scale", type="float",
                      help="Pixel scale for skycell, arcsec/pixel")
    parser.add_option("--size", dest="size", nargs=2, type="int",
                      help="Size in x and y for skycell, pixels")

    default = os.path.join(os.getenv("PIPETTE_DIR"), "policy", "lsstSim_coadd.paf")
    config, opts, args = parser.parse_args(default)

    if len(args) > 0 or len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    for reqArg in ("rerun", "radec", "scale", "size"):
        if getattr(opts, reqArg) == None:
            print "Error: must specify --%s" % (reqArg,)
            parser.print_help()
            sys.exit(1)

    argList = list()
    iterList = list()
    idDict = dict()
    for idName, idChar, idType in idNameCharTypeList:
        argStr = getattr(opts, idName)
        if not argStr:
            print "Error: must specify --%s (as colon-separated values)" % (idName,)
            parser.print_help()
            sys.exit(1)
        idDict[idName] = [idType(item) for item in argStr.split(":")]
        argList.append("%s=%sItem" % (idName, idName))
        iterList.append("for %sItem in idDict['%s']" % (idName, idName))
    idListExpr = "[dict(%s) %s]" % (", ".join(argList), " ".join(iterList))
    idList = eval(idListExpr)

    # at the moment ReadWrite simply instantiates the input butler;; maybe later it will be more useful
    io = pipReadWrite.ReadWrite(lsstSim.LsstSimMapper, idNameList,
                                fileKeys=idNameList+["channel"], config=config)
                                
    roots = config["roots"]
    baseName = os.path.join(roots["output"], opts.rerun)

    coaddExposure, weightMap = coadd(idList, io.inButler, opts.radec, opts.scale, opts.size, config.getPolicy())
    coaddExposure.writeFits(baseName + "Coadd.fits")
    weightMap.writeFits(baseName + "WeightMap.fits")
