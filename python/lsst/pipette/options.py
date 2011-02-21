#!/usr/bin/env python
#
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import sys
import optparse
import lsst.pex.logging as pexLog
import lsst.pipette.config as pipConfig

"""This module defines the option parsing for pipette LSST Algorithms testing."""

class OptionParser(optparse.OptionParser):
    """OptionParser is an optparse.OptionParser that
    provides some standard arguments.  These are used to
    populate the 'config' attribute as a lsst.pipette.config.Config
    """
    def __init__(self, *args, **kwargs):
        optparse.OptionParser.__init__(self, *args, **kwargs)
        self.add_option("-D", "--define", type="string", nargs=2,
                        action="callback", callback=optConfigDefinition,
                        help="Configuration definition (single value)")
        self.add_option("-O", "--override", type="string", action="callback", callback=optConfigOverride,
                        help="Configuration override file")
        self.add_option("--output", dest="output", type="string", action="callback", callback=optConfigRoot,
                        help="Output root directory")
        self.add_option("--data", dest="data", type="string", action="callback", callback=optConfigRoot,
                        help="Data root directory")
        self.add_option("--calib", dest="calib", type="string", action="callback", callback=optConfigRoot,
                        help="Calibration root directory")
        self.add_option("--debug", dest="debug", default=False, action="callback", callback=optConfigDebug,
                        help="Debugging output?")
        self.add_option("--log", dest="log", type="string", default=None, help="Logging destination")

        self.set_default('config', pipConfig.Config())
        return

    def parse_args(self,                # OptionParser
                   overrides, # List of particlar configuration(s) to override the defaults
                   argv=None,           # Arguments
                   ):
        """Set up configuration for pipette LSST Algorithms testing from option parsing.

        @params overrides Configurations to override default configuration
        """
        if isinstance(overrides, basestring):
            overrides = [overrides]
        config = pipConfig.configuration(*overrides)
        opts, args = optparse.OptionParser.parse_args(self, args=argv)
        config.merge(opts.config)

        if opts.log is not None:
            log = pexLog.Log.getDefaultLog()
            log.addDestination(opts.log)

        return config, opts, args


# optparse callback to set a configuration value
def optConfigDefinition(option, opt, value, parser):
    key, val = value
    parser.values.config[key] = val
    return

# optparse callback to override configurations
def optConfigOverride(option, opt, value, parser):
    override = pipConfig.Config(value)
    parser.values.config.merge(override)
    return

# optparse callback to set root directories
def optConfigRoot(option, opt, value, parser):
    if not parser.values.config.has_key('roots'):
        parser.values.config['roots'] = pipConfig.Config()
    root = parser.values.config['roots']
    root[option.dest] = value
    return

# optparse callback to set debugging
def optConfigDebug(option, opt, value, parser):
    try:
        import debug
        parser.values.debug = True
    except ImportError:
        print "No 'debug' module found"
        parser.values.debug = False
    return

