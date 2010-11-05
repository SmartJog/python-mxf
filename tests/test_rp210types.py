#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Unit tests for RP210 types manipulation class. """

import sys
import unittest
from datetime import datetime

import mxf.rp210types as conv


class RP210TypesSymetricTest(unittest.TestCase):
    """ Test RP210 conversion methods are symetric. """

    def test_reference(self):
        """ Test Reference conversion methods. """

        value = 'c11bf020cb1a448c904c4013e508cbce'
        self.assertEqual(value, conv.Reference(conv.Reference(value).read()).write())

    def test_integer(self):
        """ Test Integer conversion methods. """

        for i in range(0, 127):
            self.assertEqual(i, conv.Integer(conv.Integer(i, 'Int8').write(), 'Int8').read())

        for i in range(0, 1024):
            self.assertEqual(i, conv.Integer(conv.Integer(i, 'Int16').write(), 'Int16').read())
            self.assertEqual(i, conv.Integer(conv.Integer(i, 'Int32').write(), 'Int32').read())
            self.assertEqual(i, conv.Integer(conv.Integer(i, 'Int64').write(), 'Int64').read())

    def test_boolean(self):
        """ Test Boolean conversion methods. """

        self.assertEqual(True, conv.Boolean(conv.Boolean(True).write()).read())
        self.assertEqual(False, conv.Boolean(conv.Boolean(False).write()).read())

    def test_length(self):
        """ Test Length conversion methods. """

        for i in (0, 1, 9, 42, 69, 380, 787, 130556):
            self.assertEqual(i, conv.Length(conv.Length(i, 'Length').write(), 'Length').read())

    def test_rational(self):
        """ Test Rational conversion methods. """

        for i in ((1, 25), (1, 36), (1, 50)):
            self.assertEqual(i, conv.Rational(conv.Rational(i).write()).read())

    def test_version(self):
        """ Test Version conversion methods. """

        test_values = (
            ('ProductVersion', [1, 2, 0, 0, 1]),
            ('VersionType', [1, 2]),
        )

        for vtype, value in test_values:
            cvalue = conv.Version(conv.Version(value, vtype).write(), vtype).read()
            self.assertEqual(value, cvalue)

    def test_timestamp(self):
        """ Test TimeStamp conversion methods. """

        for i in (None, datetime(2010, 1, 1, 1, 1, 1, 4), datetime.today()):
            if isinstance(i, datetime):
                # An MXF timestamp cannot represent all python timestamps
                # Make sure we round up values so assertion as a change to succeed
                i = i.replace(microsecond = i.microsecond / 100 / 1000000)
            self.assertEqual(i, conv.TimeStamp(conv.TimeStamp(i).write()).read())

    def test_string(self):
        """ Test String conversion methods. """

        for i in ("Toto", "Toast\0", "Tete\0toto", "au16:__AttributeList", "aint32:8",):
            cvalue = conv.String(conv.String(i).write()).read()
            self.assertEqual(i, cvalue)
            self.assertEqual(len(i), len(cvalue))

    def test_variablearray(self):
        """ Test VariableArray conversion methods. """

        test_values = (
            ("Array of UInt8", range(0, 16)),
            ("16 bit Unicode String Array", ['Toto', 'titi', 'tata']),
        )

        for vtype, value in test_values:
            cvalue = conv.VariableArray(conv.VariableArray(value, vtype).write(), vtype).read()
            self.assertEqual(value, cvalue)

    def test_array(self):
        """ Test VariableArray conversion methods. """

        test_values = (
            ('2 element array of Int32', [258, 750]),
            ('Batch of Universal Labels', ['060e2b34010101050102021002010000'.encode('hex_codec'), '060e2b340101010501050f0000000000'.encode('hex_codec'), '060e2b34010101050107010600000000'.encode('hex_codec')])
        )

        for vtype, value in test_values:
            cvalue = conv.Array(conv.Array(value, vtype).write(), vtype).read()
            self.assertEqual(value, cvalue)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(RP210TypesSymetricTest)
    RESULT = unittest.TextTestRunner(verbosity=2).run(SUITE)
    sys.exit(len(RESULT.errors) + len(RESULT.failures) > 0)

