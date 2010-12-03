#!/usr/bin/env python

import lsst.pex.logging as pexLog

class BaseStage(object):
    def __init__(self, name, config=None, log=None, requires=None, provides=None):
        self.name = name
        self.config = config
        if log is None: log = pexLog.getDefaultLog()
        self.log = pexLog.Log(log, name)
        if requires is not None and isinstance(requires, basestring): requires = [requires,]
        if provides is not None and isinstance(provides, basestring): provides = [provides,]
        self.requires = set(requires) if requires is not None else set()
        self.provides = set(provides) if provides is not None else set()
        return

    def __str__(self):
        return "%s: (%s) --> (%s)" % (self.name, ','.join(self.requires), ','.join(self.provides))

    def check(self, **clipboard):
        if self.requires is None:
            self.log.log(self.log.DEBUG, "Stage %s has no dependencies" % self.name)
            return True
        for dep in self.requires:
            if clipboard is None or not clipboard.has_key(dep):
                self.log.log(self.log.WARN, "Not performing stage %s because dependency not satisfied: %s" %
                             (self.name, dep))
                return False
        self.log.log(self.log.DEBUG, "Stage %s satisfies dependencies" % self.name)
        return True

    def run(self, **clipboard):
        raise NotImplementedError("This method needs to be overridden by inheriting classes")


class IgnoredStage(BaseStage):
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
    def __init__(self, name, stages, factory=None, *args, **kwargs):
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
        if not self.check(**clipboard):
            raise RuntimeError("Stage %s dependencies not met" % self.name)
        for stage in self._stages:
            assert stage.check(**clipboard), \
                   "Stage %s dependencies not met within %s" % (stage.name, self.name)
            ret = stage.run(**clipboard)
            if ret is not None:
                clipboard.update(ret)
        return clipboard


class IterateStage(BaseStage):
    def __init__(self, name, iterate, *args, **kwargs):
        super(IterateStage, self).__init__(name, *args, **kwargs)
        self.iterate = iterate
        return

    def run(self, **clipboard):
        iterate = dict()                # List of lists to iterate over
        # Pull out things we're iterating over
        length = None                   # Length of iteration
        for name in self.iterate:
            array = clipboard[name]
            if length is None:
                length = len(array)
            elif len(array) != length:
                raise RuntimeError("Iteration sequences have different length: %s" % self.iterate)
            iterate[name] = array
        # Iterate over each element set
        for index in range(length):
            # Make new clipboard with elements of interest
            clip = clipboard.copy()
            for name in self.iterate:
                array = iterate[name]
                value = array[index]
                clip[name] = value                
            clip = super(IterateStage, self).run(**clip)
            # Put result back
            for name in self.iterate:
                array = iterate[name]
                array[index] = clip[name]
        return clipboard

class IterateMultiStage(IterateStage, MultiStage):
    # Multiple inheritance should automagically do everything we desire
    # Note that the init is __init__(self, name, iterate, stages, config, ...)
    pass
