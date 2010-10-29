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
import lsst.pex.policy as pexPolicy

"""This module defines the configuration for LSST Algorithms testing (Green Blob 3)."""

class Config(object):
    """Config is a configuration class for LSST Algorithms testing (Green Blob 3).

    It quacks like a Python dictionary.
    """

    def __init__(self,                  # Config
                 policy=None            # Filename/file/policy for configuration
                 ):
        if policy is None:
            policy = pexPolicy.Policy()
        if isinstance(policy, str):
            policy = pexPolicy.PolicyFile(policy)
        if isinstance(policy, pexPolicy.PolicyFile):
            policy = pexPolicy.Policy.createPolicy(policy)
        if not isinstance(policy, pexPolicy.Policy):
            raise RuntimeError, "Can't interpret provided policy"

        self._policy = policy
        return

    def __str__(self):
        """String version"""
        return self._policy.toString()

    def __len__(self):
        """Number of (top-level) entries"""
        return len(self._policy.names(True))

    def __getitem__(self, key):
        """Retrieve a value"""
        if not self._policy.exists(key):
            raise KeyError, "Policy doesn't contain entry: %s" % key
        value = self._policy.get(key)
        return value if not isinstance(value, pexPolicy.Policy) else Config(value)

    def __setitem__(self, key, value):
        """Set a value; adds if doesn't exist"""
        if isinstance(value, Config):
            value = value._policy
        if self._policy.exists(key): self._policy.set(key, value)
        else: self._policy.add(key, value)
        return value

    def __delitem__(self, key):
        """Delete an entry"""
        if not self._policy.exists(key):
            raise KeyError, "Policy doesn't contain entry: %s" % key
        self._policy.remove(key)
        return

    def __iter__(self):
        """Iterator for keys"""
        return self.iterkeys()

    def __contains__(self, key):
        """Contains the key?"""
        return self._policy.exists(key)

    def iterkeys(self):
        """Iterator for keys"""
        return iter(self.keys())

    def iteritems(self):
        """Iterator for items"""
        return iter(self.items())

    def keys(self):
        """List of keys"""
        return self._policy.names(True)

    def items(self):
        """List of items"""
        itemList = []
        for key in self.keys():
            itemList.append(self.__getitem__(key))
        return itemList

    def has_key(self, key):
        """Contains the key?"""
        return self._policy.exists(key)

    def merge(self, overrides):
        """Merge overrides into defaults"""
        policy = pexPolicy.Policy(overrides._policy)
        policy.mergeDefaults(self._policy)
        self._policy = policy
        return


class DefaultConfig(Config):
    """DefaultConfig is a configuration class for LSST Algorithms testing (Green Blob 3).

    It contains the default configuration from the package dictionary, plus any merges.
    """
    def __init__(self):
        dictFile = pexPolicy.DefaultPolicyFile("gb3", "ConfigDictionary.paf", "policy")
        dictPolicy = pexPolicy.Policy.createPolicy(dictFile, dictFile.getRepositoryPath()) # Dictionary
        Config.__init__(self, dictPolicy)
        return

def optConfigDefinition(option, opt, value, parser):
    key, val = value
    parser.values.config[key] = val
    return

def optConfigOverride(option, opt, value, parser):
    override = Config(value)
    parser.values.config.merge(override)
    return

def optConfigRoot(option, opt, value, parser):
    if not parser.values.config.has_key('roots'):
        parser.values.config['roots'] = Config()
    root = parser.values.config['roots']
    root[option.dest] = value
    return


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

        self.set_default('config', Config())
        return


def configuration(*overrides            # List of particlar configuration(s) to override the defaults
                  ):
    """Set up configuration for LSST Algorithms testing (Green Blob 3)."""
    # XXX This is bass-ackwards because of the way Policy is done....
    defaults = DefaultConfig()
    if overrides is not None:
        config = Config()
        for override in overrides:
            newConfig = override if isinstance(override, Config) else Config(override)
            config.merge(newConfig)
        defaults.merge(config)

    return defaults

