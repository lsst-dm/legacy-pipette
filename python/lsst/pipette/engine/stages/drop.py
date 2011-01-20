#!/usr/bin/env python

from lsst.pipette.engine.stage import BaseStage
import gc

def drop(clipboard,                     # Clipboard with components to drop
         name,                          # Name of component to drop
         log,                           # Logger
         ):
    # We choose to set the component to None instead of merely deleting it, since that can give an indication
    # that there was something there in the first place, which might be useful.  It might also be copied over
    # some other existing reference, which would serve to delete it.
    if clipboard.has_key(name):
        log.log(log.DEBUG, "Dropping component %s" % name)
        clipboard[name] = None
    return

class Drop(BaseStage):
    def __init__(self, name, which=["exposure"], *args, **kwargs):
        super(Drop, self).__init__(name, *args, **kwargs)
        self.which = which
        return

    def run(self, **clipboard):
        """Drop pixels
        """
        if isinstance(self.which, basestring):
            drop(clipboard, self.which, self.log)
        elif hasattr(self.which, "__iter__"):
            for component in self.which:
                drop(clipboard, component, self.log)
        else:
            raise RuntimeError("Unable to interpret: %s" % self.drop)

        gc.collect() # Ensure it gets blown away now
        return clipboard
