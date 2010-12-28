#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Unit tests for RP210 types manipulation class. """

import os
import sys
import unittest

from sjmxf import s377m


def load_klv(filename, mxfobj, *args, **kwargs):
    """ Loads KLV in file @filename.raw using @mxfobj class. """
    source_file = os.path.sep.join([os.path.dirname(sys.argv[0]), 'data', filename + '.raw'])
    fread = open(source_file, 'r')
    klv = mxfobj(fread, *args, **kwargs)
    klv.read()
    fread.close()
    return klv

def read_and_write(filename, mxfobj, primer=None):
    """ Reads @filename.raw and writes it as @filename.new.

    @returns: a tuple containing raw data of the original filename and the
              rewritten one for comparison purpose.
    """
    source_file = os.path.sep.join([os.path.dirname(sys.argv[0]), 'data', filename + '.raw'])
    dest_file = filename + '.new'

    fread = open(source_file, 'r')
    fwrite = open(dest_file, 'w')
    if primer:
        klv = mxfobj(fread, primer)
    else:
        klv = mxfobj(fread)
    klv.read()
    klv.fdesc = fwrite
    klv.write()

    fwrite.close()

    fwrite = open(dest_file, 'r')
    fread.seek(0)
    data_read = fread.read()
    data_write = fwrite.read()

    fread.close()
    fwrite.close()

    return data_read, data_write


class S377MSymetricTest(unittest.TestCase):
    """ Verify read/write methods of S377M objects are symetric. """

    def test_klv_fill(self):
        """ Test KLVFill """
        data_read, data_write = read_and_write('klvfill', s377m.KLVFill)
        self.assertEqual(data_read, data_write)

    def test_klv_dark(self):
        """ Test KLVDark """
        data_read, data_write = read_and_write('klvfill', s377m.KLVDarkComponent)
        self.assertEqual(data_read, data_write)

    def test_partition(self):
        """ Test MXFPartition """
        data_read, data_write = read_and_write('header_partition', s377m.MXFPartition)
        self.assertEqual(data_read, data_write)
        data_read, data_write = read_and_write('footer_partition', s377m.MXFPartition)
        self.assertEqual(data_read, data_write)

    def test_random_index_pack(self):
        """ Test Random Index Pack """
        data_read, data_write = read_and_write('random_index_metadata', s377m.RandomIndexMetadata)
        self.assertEqual(data_read, data_write)

    def test_primer(self):
        """ Test Primer Pack """
        data_read, data_write = read_and_write('primer', s377m.MXFPrimer)
        self.assertEqual(data_read, data_write)

    def test_dataset(self):
        """ Test data set """
        primer = load_klv('primer', s377m.MXFPrimer)
        data_read, data_write = read_and_write('dataset', s377m.MXFDataSet, primer)
        self.assertEqual(data_read, data_write)

    def test_preface(self):
        """ Test Preface """
        primer = load_klv('primer', s377m.MXFPrimer)
        data_read, data_write = read_and_write('preface', s377m.MXFPreface, primer)
        self.assertEqual(data_read, data_write)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(S377MSymetricTest)
    RESULT = unittest.TextTestRunner(verbosity=2).run(SUITE)
    sys.exit(len(RESULT.errors) + len(RESULT.failures) > 0)

