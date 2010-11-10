#/usr/bin/env python

import re
import pickle
import subprocess
import shlex

import lsst.pex.logging as pexLog

"""This module provides a mechanism for queuing a common Python script with different inputs."""

class PbsQueue(object):

    """PbsQueue is for queuing Python scripts via PBS (or Open-PBS or Torque, etc).
    A common script is defined which may be queued with different inputs.
    Inputs must be picklable.
    """

    def __init__(self, script, importList=None, command="qsub -V", resourceList=None, queue=None):
        """Initialisation

        @param script Text of script to execute
        @param importList List of imports; may be specified as a 2-tuple for 'import X as Y'
        @param command Command to run to submit to queue
        @param resourceList List of resources for PBS
        @param queue Name of queue
        """

        # Remove common indentation
        lines = re.split("\n", script)
        exemplar = None                 # First non-blank line
        for line in lines:
            if re.search("\S", line):
                exemplar = line
                break
        if exemplar is None:
            raise RuntimeError("Empty script provided.")
        match = re.match("(\s+)", exemplar)
        if match:
            indent = match.group(0)     # Indentation used
            newLines = []
            for line in lines:
                if not re.search("\S", line):
                    continue
                newLine = re.sub("^" + indent, "", line)
                if newLine is None:
                    raise RuntimeError("Inconsistent indentation in script: " + script)
                newLines.append(newLine)
            script = "\n".join(newLines)

        self.script = script
        self.importList = importList
        self.command = command
        self.resourceList = resourceList
        self.queue = queue
        self.log = pexLog.Log(pexLog.getDefaultLog(), "PbsQueue")
        return

    def sub(self, name, **kwargs):
        """Submit to queue

        @param name Filename for python script
        @param **kwargs Variables to set before calling the script
        """
        filename = (name + ".py") if not re.search(r"\.py$", name) else name
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
        return
