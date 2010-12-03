#!/usr/bin/env python

import os
import lsst.afw.geom as afwGeom
import lsst.meas.astrom as measAst
import lsst.meas.astrom.net as astromNet
import lsst.meas.astrom.sip as astromSip
import lsst.meas.astrom.verifyWcs as astromVerify
from lsst.pipette.engine.stage import BaseStage

class Ast(BaseStage):
    def __init__(self, *args, **kwargs):
        super(Ast, self).__init__(requires=['exposure', 'sources'], provides=['matches', 'wcs'],
                                  *args, **kwargs)
        return

    def run(self, exposure=None, sources=None, distortion=None, **kwargs):
        """Solve WCS

        @param exposure Exposure to process
        @param sources Sources with undistorted (actual) positions
        @param distortion Distortion to apply
        """
        assert exposure, "No exposure provided"
        assert sources, "No sources provided"
        
        policy = self.config['ast']
        path=os.path.join(os.environ['ASTROMETRY_NET_DATA_DIR'], "metadata.paf")
        solver = astromNet.GlobalAstrometrySolution(path)
        #solver.allowDistortion(self.policy.get('allowDistortion'))
        self.log.log(self.log.INFO, "Solving astrometry")

        try:
            menu = self.config['filters']
            filterName = menu[exposure.getFilter().getName()]
        except:
            self.log.log(self.log.WARN, "Unable to determine catalog filter from lookup table using %s" %
                         exposure.getFilter().getName())
            filterName = policy['defaultFilterName']
        self.log.log(self.log.INFO, "Using catalog filter: %s" % filterName)

        if distortion is not None:
            self.log.log(self.log.INFO, "Applying distortion correction.")
            distSources = distortion.actualToIdeal(sources)

            # Get distorted image size, and remove offset
            xMin, xMax, yMin, yMax = 0, exposure.getWidth(), 0, exposure.getHeight()
            for x, y in ((0.0, 0.0), (0.0, exposure.getHeight()), (exposure.getWidth(), 0.0),
                         (exposure.getHeight(), exposure.getWidth())):
                point = afwGeom.makePointD(x, y)
                x, y = point.getX(), point.getY()
                if x < xMin: xMin = x
                if x > xMax: xMax = x
                if y < yMin: yMin = y
                if y > yMax: yMax = y
            xMin = int(xMin)
            yMin = int(yMin)
            for source in distSources:
                x, y = source.getXAstrom(), source.getYAstrom()
                source.setXAstrom(x - xMin)
                source.setYAstrom(y - yMin)

            size = afwGeom.makePointI(int(xMax - xMin + 0.5), int(yMax - yMin + 0.5))
        else:
            distSources = sources
            size = afwGeom.makePointI(exposure.getWidth(), exposure.getHeight())

        if True:
            solver.setMatchThreshold(policy['matchThreshold'])
            solver.setStarlist(distSources)
            solver.setNumBrightObjects(min(policy['numBrightStars'], len(distSources)))
            solver.setImageSize(size.getX(), size.getY())
            if not solver.solve(exposure.getWcs()):
                raise RuntimeError("Unable to solve astrometry")
            wcs = solver.getWcs()
            matches = solver.getMatchedSources(filterName)
            sipFitter = astromSip.CreateWcsWithSip(matches, wcs, policy['sipOrder'])
            wcs = sipFitter.getNewWcs()
            scatter = sipFitter.getScatterInArcsec()
            self.log.log(self.log.INFO, "Astrometric scatter: %f" % scatter)
        else:
            matches, wcs = measAst.determineWcs(policy.getPolicy(), exposure, distSources,
                                                solver=solver, log=self.log)
            if matches is not None or len(matches) == 0:
                raise RuntimeError("Unable to find any matches")

        exposure.setWcs(wcs)
        for index, source in enumerate(sources):
            distSource = distSources[index]
            sky = wcs.pixelToSky(distSource.getXAstrom(), distSource.getYAstrom())
            source.setRa(sky[0])
            source.setDec(sky[1])

        verify = dict()                    # Verification parameters
        verify.update(astromSip.sourceMatchStatistics(matches))
        verify.update(astromVerify.checkMatches(matches, exposure, self.log))
        for k, v in verify.items():
            exposure.getMetadata().set(k, v)
        return {'matches': matches,
                'wcs': wcs
                }
