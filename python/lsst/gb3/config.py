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
        if self._policy.exists(key):
            value = self._policy.get(key)
            return value if not isinstance(value, pexPolicy.Policy) else Config(value)
        raise KeyError, "Policy doesn't contain entry: %s" % key

    def __setitem__(self, key, value):
        """Set a value; adds if doesn't exist"""
        if self._policy.exists(key): return self._policy.set(key, value)
        self._policy.add(key, value)

    def __delitem__(self, key):
        """Delete an entry"""
        if self._policy.exists(key): return self._policy.remove(key)
        raise KeyError, "Policy doesn't contain entry: %s" % key

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


class CommandConfig(Config):
    """CommandConfig is a configuration class for LSST Algorithms testing (Green Blob 3).

    It reads configuration settings from the command-line
    """
    def __init__(self):
        import optparse
        parser = optparse.OptionParser()
        parser.add_option("-D", "--define", dest="defines",
                          action="append", nargs=2,
                          help="Configuration definition")
        parser.add_option("--data", dest="data", help="Data root directory")
        parser.add_option("--calib", dest="calib", help="Calibration root directory")
        (options, args) = parser.parse_args()
        sys.argv[1:] = args            # Remove instances so other parsers don't worry about them

        Config.__init__(self)

        if options.defines is not None:
            for key, value in options.defines:
                self[key] = value

        if options.data is not None or options.calib is not None:
            roots = Config()
            roots['root'] = options.data
            roots['calib'] = options.calib
            self['roots'] = roots

        return


def configuration(overrides=None        # List of particlar configuration(s) to override the defaults
                  ):
    """Set up configuration for LSST Algorithms testing (Green Blob 3)."""
    config = DefaultConfig()
    if overrides is not None:
        for override in overrides:
            newConfig = override if isinstance(override, Config) else Config(override)
            config.merge(newConfig)
    config.merge(CommandConfig())

    return config

