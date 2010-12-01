#!/usr/bin/env python

import lsst.pex.logging as pexLog

class Stage(object):
    def __init__(self, name, log=pexLog.getDefaultLog(), depends=None, always=False, crank=None):
        self.name = name
        if log is None:
            self.log = pexLog.Log(name)
        else:
            self.log = pexLog.Log(log, name)
        if depends is not None and isinstance(depends, basestring):
            self.depends = [depends,]
        else:
            self.depends = depends
        self.always = always
        self.crank = crank
        return

    def checkDepend(self, clipboard):
        if self.depends is None:
            self.log.log(self.log.DEBUG, "Stage %s has no dependencies" % self.name)
            return True
        for dep in self.depends:
            if clipboard is None or not clipboard.has_key(dep):
                self.log.log(self.log.WARN, "Not performing stage %s because dependency not satisfied: %s" %
                             (self.name, dep))
                return False
        self.log.log(self.log.DEBUG, "Stage %s satisfies dependencies" % self.name)
        return True
