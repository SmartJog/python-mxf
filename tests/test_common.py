#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Unit tests for MXF manipulation class. """

import sys
import unittest

from sjmxf.common import InterchangeObject


class InterchangeObjectTest(unittest.TestCase):
    """ Test BER encoding routine complies to SMTPE 377M. """

    def test_runtime_short_encode(self):
        """ Test encoding returns an even sized string for short values. """
        for i in range(0, 127):
            self.assertEqual(len(InterchangeObject.ber_encode_length(i, prefix=False)) % 2, 0)

    def test_runtime_long_encode(self):
        """ Test encoding returns an even sized string for longer values. """
        for i in range(128, 4096):
            self.assertEqual(len(InterchangeObject.ber_encode_length(i)) % 2, 0)

    def test_ber_short_decoding(self):
        """ Test short BER decoding compliance. """
        self.assertEqual(InterchangeObject.ber_decode_length('00'.decode('hex_codec')), 0)
        self.assertEqual(InterchangeObject.ber_decode_length('01'.decode('hex_codec')), 1)
        self.assertEqual(InterchangeObject.ber_decode_length('7f'.decode('hex_codec')), 127)
        self.assertEqual(InterchangeObject.ber_decode_length('80'.decode('hex_codec')), 0)

    def test_ber_long_decoding(self):
        """ Test long BER decoding compliance. """
        self.assertEqual(InterchangeObject.ber_decode_length('811C'.decode('hex_codec')), 28)
        self.assertEqual(InterchangeObject.ber_decode_length('82001C'.decode('hex_codec')), 28)
        self.assertEqual(InterchangeObject.ber_decode_length('840000001C'.decode('hex_codec')), 28)
        self.assertEqual(InterchangeObject.ber_decode_length('88000000000000001C'.decode('hex_codec')), 28)

    def test_ber_decoding_limits(self):
        """ Long form decoding cannot exceed 8 bytes. """
        self.assertRaises(ValueError, InterchangeObject.ber_decode_length, '89000000000000000001'.decode('hex_codec'))

    def test_non_ber_decoding(self):
        """ Test usability of the method for non BER decoding. """
        self.assertEqual(InterchangeObject.ber_decode_length('0100'.decode('hex_codec'), 2), 256)
        self.assertEqual(InterchangeObject.ber_decode_length('01e5'.decode('hex_codec'), 2), 485)

    def test_ber_short_encoding(self):
        """ Test short BER encoding compliance. """
        self.assertEqual(InterchangeObject.ber_encode_length(0, prefix=False), '00')
        self.assertEqual(InterchangeObject.ber_encode_length(1, prefix=False), '01')
        self.assertEqual(InterchangeObject.ber_encode_length(127, prefix=False), '7f')
        self.assertEqual(InterchangeObject.ber_encode_length(128, prefix=False), '80')
        self.assertEqual(InterchangeObject.ber_encode_length(255, prefix=False), 'ff')

    def test_ber_long_encoding(self):
        """ Test long BER encoding compliance. """
        self.assertEqual(InterchangeObject.ber_encode_length(0), '00')
        self.assertEqual(InterchangeObject.ber_encode_length(1), '01')
        self.assertEqual(InterchangeObject.ber_encode_length(127), '7f')
        self.assertEqual(InterchangeObject.ber_encode_length(128), '8180')
        self.assertEqual(InterchangeObject.ber_encode_length(255), '81ff')
        self.assertEqual(InterchangeObject.ber_encode_length(256), '820100')

    def test_ber_long_encoding_with_bytes(self):
        """ Test long BER encoding compliance with forced bytes length. """
        self.assertEqual(InterchangeObject.ber_encode_length(1, bytes_num=2), '820001')
        self.assertEqual(InterchangeObject.ber_encode_length(127, bytes_num=4), '840000007f')
        self.assertEqual(InterchangeObject.ber_encode_length(128, bytes_num=4), '8400000080')
        self.assertEqual(InterchangeObject.ber_encode_length(256, bytes_num=8), '880000000000000100')

    def test_ber_encoding_limits(self):
        """ Long form encoding cannot exceed 8 bytes. """
        self.assertRaises(ValueError, InterchangeObject.ber_encode_length, 1, bytes_num=9)

    def test_non_ber_encoding(self):
        """ Test usability of the method for non BER encoding. """
        self.assertEqual(InterchangeObject.ber_encode_length(256, prefix=False), '0100')
        self.assertEqual(InterchangeObject.ber_encode_length(485, prefix=False), '01e5')

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(InterchangeObjectTest)
    RESULT = unittest.TextTestRunner(verbosity=2).run(SUITE)
    sys.exit(len(RESULT.errors) + len(RESULT.failures) > 0)

