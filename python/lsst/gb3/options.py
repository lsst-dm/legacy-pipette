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

import optparse
import lsst.gb3.config as config

"""This module defines the option parsing for LSST Algorithms testing (Green Blob 3)."""

class OptionParser(optparse.OptionParser):
    """OptionParser is an optparse.OptionParser that
    provides some standard arguments.  These are used to
    populate the 'config' attribute as a lsst.gb3.Config
    """
    def __init__(self, *args, **kwargs):
        optparse.OptionParser.__init__(self, *args, **kwargs)
        self.add_option("-D", "--define", type="string", nargs=2,
                        action="callback", callback=optConfigDefinition,
                        help="Configuration definition (single value)")
        self.add_option("-O", "--override", type="string", action="callback", callback=optConfigOverride,
                        help="Configuration override file")
        self.add_option("--data", dest="data", type="string", action="callback", callback=optConfigRoot,
                        help="Data root directory")
        self.add_option("--calib", dest="calib", type="string", action="callback", callback=optConfigRoot,
                        help="Calibration root directory")
        self.add_option("--debug", dest="debug", action="callback", callback=optConfigDebug,
                        help="Debugging output?")

        self.set_default('config', config.Config())
        return

def optConfigDefinition(option, opt, value, parser):
    key, val = value
    parser.values.config[key] = val
    return

def optConfigOverride(option, opt, value, parser):
    override = config.Config(value)
    parser.values.config.merge(override)
    return

def optConfigRoot(option, opt, value, parser):
    if not parser.values.config.has_key('roots'):
        parser.values.config['roots'] = config.Config()
    root = parser.values.config['roots']
    root[option.dest] = value
    return

def optConfigDebug(option, opt, value, parser):
    try:
        import debug
    except ImportError:
        print "No 'debug' module found"
    return

