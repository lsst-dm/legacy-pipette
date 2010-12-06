# -*- python -*-
#
# Setup our environment
#
import glob, os.path, re
import lsst.SConsUtils as scons

dependencies = "boost python utils daf_base afw pex_logging pex_exceptions pex_policy".split()

env = scons.makeEnv("pipette_engine",
                    r"$HeadURL$",
                    [
                    ])
env.Help("""
LSST Green Blob 3 (Algorithms Testing) Engine package
""")

###############################################################################
# Boilerplate below here

pkg = env["eups_product"]
env.libs[pkg] += env.getlibs(" ".join(dependencies))

#
# Build/install things
#
for d in Split("lib python/lsst/" + re.sub(r'_', "/", pkg) + " examples tests doc"):
    if os.path.isdir(d):
        SConscript(os.path.join(d, "SConscript"))

env['IgnoreFiles'] = r"(~$|\.pyc$|^\.svn$|\.o$)"

Alias("install", [env.Install(env['prefix'], "python"),
                  env.Install(env['prefix'], "policy"),
                  env.InstallAs(os.path.join(env['prefix'], "doc", "doxygen"),
                                os.path.join("doc", "htmlDir")),
                  env.InstallEups(env['prefix'] + "/ups", glob.glob("ups/*.table"))])

scons.CleanTree(r"*~ core *.so *.os *.o")

#
# Build TAGS files
#
files = scons.filesToTag()
if files:
    env.Command("TAGS", files, "etags -o $TARGET $SOURCES")

env.Declare()
