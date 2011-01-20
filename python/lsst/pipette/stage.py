#!/usr/bin/env python

import lsstDebug
import lsst.pex.logging as pexLog
import lsst.afw.detection as afwDet
import lsst.afw.display.ds9 as ds9
import lsst.ip.isr as ipIsr
import lsst.pipette.util as pipUtil

"""This module defines various types of stages that can be executed."""

class BaseStage(object):
    """BaseStage is the base class for stages.
    Users should subclass BaseStage and override the __init__ and run methods.

    Data flows through stages in the form of a 'clipboard' (a regular Python dict).
    We find it convenient to pass this as **clipboard, so that methods can pick
    out components they're interested in using the function definition, e.g.,
    def run(exposure=None, **clipboard) will pick the exposure out of the clipboard.
    The checkRequire() method can be used to ensure that these will exist, but the
    user is encouraged to assert on them as well.
    """
    
    def __init__(self, name, config=None, log=None, requires=None, provides=None, factory=None):
        # XXX Should I use factory=None and then ignore it, or **kwargs?  Calling out factory
        # explicitly seems to give more error-checking capability.
        """Constructor

        @param name Name of the stage; used for logging
        @param config Configuration
        @param log Logger
        @param requires Set of required data on clipboard
        @param provides Set of provided data on clipboard
        @param factory Ignored; present for children classes
        """
        self.name = name
        self.config = config
        if log is None: log = pexLog.getDefaultLog()
        self.log = pexLog.Log(log, name)
        if requires is not None and isinstance(requires, basestring): requires = [requires,]
        if provides is not None and isinstance(provides, basestring): provides = [provides,]
        self.requires = set(requires) if requires is not None else set()
        self.provides = set(provides) if provides is not None else set()
        display = lsstDebug.Info(__name__).display
        self._display = display[self.name] if display and display.has_key(name) else None
        return

    def __str__(self):
        return "%s: (%s) --> (%s)" % (self.name, ','.join(self.requires), ','.join(self.provides))

    def _check(self, check, which, clipboard):
        """Check that stage dependencies or provisions are met by the clipboard

        @param check Set to check
        @param which Which set is being checked (for log messages)
        @param clipboard Clipboard dict
        """
        if check is None:
            self.log.log(self.log.DEBUG, "Stage %s has no %s" % (self.name, which))
            return True
        for key in check:
            if clipboard is None or not clipboard.has_key(key):
                self.log.log(self.log.WARN, "Stage %s %s not satisfied: %s" %
                             (self.name, which, key))
                return False
        self.log.log(self.log.DEBUG, "Stage %s satisfies %s" % (self.name, which))
        return True


    def checkRequire(self, **clipboard):
        """Check that stage dependencies are met by the clipboard

        @param **clipboard Clipboard dict
        """
        return self._check(self.requires, "requirements", clipboard)

    def checkProvide(self, **clipboard):
        """Check that stage provisions are met by the clipboard

        @param **clipboard Clipboard dict
        """
        return self._check(self.provides, "provisions", clipboard)

    def run(self, **clipboard):
        """Run the stage.  This method needs to be overridden by inheriting classes.

        @param **clipboard Clipboard dict
        """
        raise NotImplementedError("This method needs to be overridden by inheriting classes")

    def display(self, exposure=None, sources=None, matches=None, pause=None, **clipboard):
        """Display image and/or sources

        @param name Name for display dict
        @param exposure Exposure to display, or None
        @param sources Sources to display, or None
        @param matches Matches to display, or None
        @param pause Pause execution?
        """
        if not self._display or self._display <= 0:
            return
        frame = self._display

        if exposure:
            if isinstance(exposure, list):
                if len(exposure) == 1:
                    exposure = exposure[0]
                else:
                    exposure = ipIsr.assembleCcd(exposure, pipUtil.getCcd(exposure[0]))
            mi = exposure.getMaskedImage()
            ds9.mtv(mi, frame=frame, title=self.name)
            x0, y0 = mi.getX0(), mi.getY0()
        else:
            x0, y0 = 0, 0

        if sources and isinstance(sources, afwDet.SourceSet) or isinstance(sources, list):
            for source in sources:
                xc, yc = source.getXAstrom() - x0, source.getYAstrom() - y0
                ds9.dot("o", xc, yc, size=4, frame=frame)
                #try:
                #    mag = 25-2.5*math.log10(source.getPsfFlux())
                #    if mag > 15: continue
                #except: continue
                #ds9.dot("%.1f" % mag, xc, yc, frame=frame, ctype="red")

        if matches:
            for match in matches:
                first = match.first
                x1, y1 = first.getXAstrom() - x0, first.getYAstrom() - y0
                ds9.dot("+", x1, y1, size=8, frame=frame, ctype="yellow")
                second = match.second
                x2, y2 = second.getXAstrom() - x0, second.getYAstrom() - y0
                ds9.dot("x", x2, y2, size=8, frame=frame, ctype="red")

        if pause:
            raw_input("Press [ENTER] when ready....")
        return

class IgnoredStage(BaseStage):
    """A stage that has been ignored for processing.  It does nothing except exist."""
    def __init__(self, *args, **kwargs):
        super(IgnoredStage, self).__init__(*args, **kwargs)
        self.requires = set()
        self.provides = set()
        return

    def run(self, **clipboard):
        self.log.log(self.log.DEBUG, "Stage %s has been ignored." % self.name)
        return

    def __str__(self):
        return "%s: IGNORED" % (self.name)

class MultiStage(BaseStage):
    """A stage consisting of multiple stages.  The stages are executed in turn."""    
    def __init__(self, name, stages, factory=None, *args, **kwargs):
        """Constructor.

        Note that we can work out the requirements and provisions using the
        components, so there's no need to provide those.
        If a factory is provided, it is used to create each of the stages.

        @param name Name of the stage; used for logging
        @param stages Stages to run
        @param factory Factory to create stages, or None
        """
        super(MultiStage, self).__init__(name, *args, **kwargs)
        if factory is None:
            self._stages = stages
        else:
            self._stages = factory.create(stages, *args, **kwargs)
        requires = set()                # Requirement list for set
        provides = set()                # Provision list for set
        for stage in self._stages:
            assert isinstance(stage, BaseStage), \
                   "Stage %s is not of type BaseStage (%s)" % (stage, type(stage))
            stage.log = pexLog.Log(self.log, stage.name) # Make stage log subordinate
            for req in stage.requires:
                if not (req in requires or req in provides):
                    requires.add(req)
            for prov in stage.provides:
                if not prov in provides:
                    provides.add(prov)
        requires.update(self.requires)
        provides.update(self.provides)
        self.requires = requires
        self.provides = provides
        return

    def __str__(self):
        stages = []
        for stage in self._stages:
            stages.append(stage.__str__())
        return "%s [%s]: (%s) --> (%s)" % (self.name, ', '.join(stages),
                                           ','.join(self.requires), ','.join(self.provides))

    def run(self, **clipboard):
        """Run the stage.  Each stage is executed in turn.

        @param **clipboard Clipboard dict
        """
        if not self.checkRequire(**clipboard):
            raise RuntimeError("Stage %s requirements not met: %s vs %s" %
                               (self.name, clipboard, self.requires))
        for stage in self._stages:
            assert stage.checkRequire(**clipboard), \
                   "Stage %s requirements not met within %s: %s vs %s" % \
                               (stage.name, self.name, clipboard, self.requires)
            ret = stage.run(**clipboard)
            if ret is not None:
                assert stage.checkProvide(**ret), \
                       "Stage %s provisions not met within %s: %s vs %s" % \
                       (stage.name, self.name, ret, self.provides)
                clipboard.update(ret)
            stage.display(**clipboard)
        return clipboard


class IterateStage(BaseStage):
    """A stage that runs on a list of components."""
    def __init__(self, name, iterate, stage, *args, **kwargs):
        """Constructor

        @param name Name of the stage; used for logging
        @param iterate Component or list of components to iterate over
        @param stage Stage to execute
        """
        super(IterateStage, self).__init__(name,  *args, **kwargs)
        self.iterate = iterate
        self.stage = stage
        if self.stage is not None:
            self.requires = self.stage.requires
            self.provides = self.stage.provides
        return

    def run(self, **clipboard):
        """Run the stage.  The stage is executed for each of the components.

        The components nominated for iteration must be passed in as lists.

        @param **clipboard Clipboard dict
        """
        assert self.checkRequire(**clipboard), "Stage %s requirements not met: %s vs %s" % \
               (self.name, clipboard, self.requires)
        iterate = dict()                # List of lists to iterate over
        # Pull out things we're iterating over
        length = None                   # Length of iteration
        isArray = None                  # Are the things we're working with in arrays?
        for name in self.iterate:
            data = clipboard[name]
            thisLength = None           # The length of this array
            thisArray = None            # Is this one an array?
            
            if not isinstance(data, basestring) and not isinstance(data, dict) and hasattr(data, "__iter__"):
                thisLength = len(data)
                thisArray = True
            else:
                thisLength = 1
                thisArray = False

            if length is None:
                length = thisLength
            elif thisLength != length:
                raise RuntimeError("Iteration sequences have different length: %s" % self.iterate)
            if isArray is None:
                isArray = thisArray
            elif thisArray != isArray:
                raise RuntimeError("Iteration sequences have different structure: %s" % self.iterate)
            
            iterate[name] = data

        if not isArray:
            # We can execute in the regular manner
            clip = super(IterateStage, self).run(**clipboard)
            clipboard.update(clip)
            assert self.checkProvide(**clipboard), "Stage %s provisions not met: %s vs %s" % \
                   (self.name, clipboard, self.provides)
            return clipboard

        # Set up outputs from iteration
        provides = dict()               # Elements provided by stage
        for name in self.provides:
            provides[name] = list() if isArray else None

        # Iterate over each element set
        for index in range(length):
            self.log.log(self.log.DEBUG, "%s, iteration %d: %s" % (self.name, index, clipboard))
            # Make new clipboard with elements of interest
            clip = clipboard.copy()
            for name in self.iterate:
                array = iterate[name]
                value = array[index]
                clip[name] = value
            if self.stage is not None:
                result = self.stage.run(**clip)
            else:
                result = super(IterateStage, self).run(**clip)
            clip.update(result)
            # Put result back
            for name in self.iterate:
                array = iterate[name]
                array[index] = clip[name]
            # Store outputs
            for name in self.provides:
                array = provides[name]
                array.append(clip[name])
            self.log.log(self.log.DEBUG, "%s, iteration %d done: %s + %s" %
                         (self.name, index, clipboard, provides))
        clipboard.update(provides)
        assert self.checkProvide(**clipboard), "Stage %s provisions not met: %s vs %s" % \
               (self.name, clipboard, self.provides)
        return clipboard

class IterateMultiStage(IterateStage, MultiStage):
    """A stage that runs multiple stages on a list of components

    Note that, by virtue of the order of the multiple inheritance, the
    constructor is __init__(self, name, iterate, None, stages, config, ...)
    and the behaviour of run(self, **clipboard) should be like:
        for each iteration component set:
            for each stage:
                run stage with component set
    """
    # Multiple inheritance should automagically do everything we desire
    pass
