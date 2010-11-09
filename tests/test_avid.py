#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Unit tests for RP210 types manipulation class. """

import sys
import unittest

from mxf import avid, s377m
import test_s377m as testmxf


class AvidSymetricTest(unittest.TestCase):
    """ Verify read/write methods of Avid objects are symetric. """

    def test_avid_object_directory(self):
        """ Test Avid Object Directory """

        data_read, data_write = testmxf.read_and_write('avid_object_directory', avid.AvidObjectDirectory)
        self.assertEqual(data_read, data_write)

    def test_avid_metadata_preface(self):
        """ Test Avid Metadata Preface """

        primer = testmxf.load_klv('primer', s377m.MXFPrimer)
        data_read, data_write = testmxf.read_and_write('avid_metadata_preface', avid.AvidMetadataPreface, primer)
        self.assertEqual(data_read, data_write)

    def test_avid_aaf_definition(self):
        """ Test Avid AAF Definition """

        primer = testmxf.load_klv('primer', s377m.MXFPrimer)
        data_read, data_write = testmxf.read_and_write('avid_aaf_definition', avid.AvidAAFDefinition, primer)
        self.assertEqual(data_read, data_write)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(AvidSymetricTest)
    RESULT = unittest.TextTestRunner(verbosity=2).run(SUITE)
    sys.exit(len(RESULT.errors) + len(RESULT.failures) > 0)

