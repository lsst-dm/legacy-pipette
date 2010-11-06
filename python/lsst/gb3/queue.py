#/usr/bin/env python

import pickle
import subprocess
import shlex

import lsst.pex.logging as pexLog

class Queue(object):
    def __init__(self, script, importList=None, command="qsub -V", resourceList=None, queue=None):
        self.script = script
        self.importList = importList
        self.command = command
        self.resourceList = resourceList
        self.queue = queue
        self.log = pexLog.Log(pexLog.getDefaultLog(), "Queue")
        return

    def sub(self, name, **kwargs):
        filename = name + ".py"
        fp = open(filename, 'w')
        fp.write("#!/usr/bin/env python\n")
        fp.write("import pickle\n")
        for imp in self.importList:
            if not isinstance(imp, str) and getattr(imp, '__iter__', None) is not None:
                if len(imp) == 1:
                    imp = imp[0]
                elif len(imp) == 2:
                    imp = "%s as %s" % (imp[0], imp[1])
                else:
                    raise RuntimeError("Can't understand attempted import: %s" % imp)
            fp.write("import %s\n" % imp)
        for key, val in kwargs.items():
            fp.write("%s = pickle.loads(\"\"\"%s\n\"\"\")\n" % (key, pickle.dumps(val)))
        fp.write(self.script + "\n")
        fp.close()

        command = self.command
        if self.resourceList is not None:
            if isinstance(self.resourceList, str):
                command += " -l " + self.resourceList
            else:
                command += " -l " + ','.join(self.resourceList)
        if self.queue is not None:
            command += " -q %s" % self.queue
        command += " " + filename
        self.log.log(self.log.INFO, "Executing: %s" % command)
        subprocess.call(shlex.split(command))
