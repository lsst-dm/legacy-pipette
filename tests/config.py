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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#


import unittest
import lsst.utils.tests as utilsTests

import lsst.gb3.engine.config as cfg


def compare(config,                     # Configuration being tested
            truth                       # dict with same entries
            ):
    for key in truth.keys():
        value = config[key]
        trueValue = truth[key]
        #print "%s: %s vs %s" % (key, str(value), str(trueValue))
        if isinstance(trueValue, dict):
            if not compare(value, trueValue): return False
        elif isinstance(trueValue, list):
            for index, entry in enumerate(trueValue):
                if value[index] != entry: return False
        else:
            if value != trueValue: return False
    return True

class ConfigTestCase(unittest.TestCase):
    """A test case for configuration"""

    def setUp(self):
        self.config = cfg.Config("tests/test_config.paf")
        self.truth = { 'integer': 1,
                       'float': 3.21,
                       'truth': True,
                       'falsehood': False,
                       'string': 'this is a string',
                       'policy': { 'subpolicy': True },
                       'array': [1, 2, 3, 4, 5, ],
                       }

    def tearDown(self):
        del self.config

    def testLen(self):
        self.assertEqual(len(self.config), len(self.truth), "Length matches truth")

    def testKeys(self):
        config = self.config.keys()
        truth = self.truth.keys()
        self.assertEqual(len(config), len(truth), "Key lengths match")
        ok = True
        for key in truth:
            if not key in config:
                ok = False
            if not self.config.has_key(key):
                ok = False
        self.assertTrue(ok, "Key lists match")

    def testEntries(self):
        self.assertTrue(compare(self.config, self.truth), "Entries match truth")

    def testAdd(self):
        self.config['new'] = "this is new!"
        self.truth['new'] = "this is new!"
        self.assertTrue(compare(self.config, self.truth), "Entries match truth after addition")
        self.config['new_array'] = [ 1, 2, 3, 4, 5, ]
        self.truth['new_array'] = [ 1, 2, 3, 4, 5, ]
        self.assertTrue(compare(self.config, self.truth), "Entries match truth after array addition")

    def testSet(self):
        self.config['integer'] = 42
        self.truth['integer'] = 42
        self.assertTrue(compare(self.config, self.truth), "Entries match truth after set")

    def testDel(self):
        del self.config['integer']
        del self.truth['integer']
        self.assertTrue(compare(self.config, self.truth), "Entries match truth after deletion")



def suite():
    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(ConfigTestCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)
    return unittest.TestSuite(suites)

def run(shouldExit = False):
    utilsTests.run(suite(), shouldExit)

if __name__ == '__main__':
    run(True)
