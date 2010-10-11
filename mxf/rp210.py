#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Helper module to convert MXF data to python types according to SMPTE RP210. """

import csv
from pprint import pprint

import mxf.rp210types

class RP210Exception(Exception):
    """ Raised on RP210 operation problem. """

    def __init__(self, error):
        """ Init Method """
        Exception.__init__(self, 'RP210: ' + error)


class RP210(object):
    """ SMTPE RP210 helper class.

    Helper class to convert MXF data types to python objects and vice-versa.
    """

    def __init__(self):
        csv_file = open('data/RP210v10-pub-20070121-1600.csv', 'r')
        spec = csv.DictReader(csv_file)
        self.data = {}

        try:
            while True:
                eul = ""
                row = spec.next()
                try:
                    eul = row['Formatted as UL'].replace('.', '').lower()
                    self.data[eul] = (
                        row['Type'],
                        self._flat_style(row['Data Element Name']),
                        row['Data Element Definition']
                    )
                except KeyError:
                    # Non valuable data
                    continue

                # Drop lines with a field set to 'None'
                if None in self.data[eul]:
                    del self.data[eul]

        except StopIteration:
            csv_file.close()

        extra_items = {
            # Hacks from short tags supposed to be present in Primer Pack for
            # AAF compatibility but missing in OPavid
            '00000000000000000000000000000001': ('StrongReference', 'AAF Metadata', 'Avid AAF Metadata Reference'),
            '00000000000000000000000000000002': ('StrongReference', 'Preface', 'Avid Preface Reference'),
            '00000000000000000000000000000003': ('StrongReferenceArray', 'Avid StrongReferenceArray to Composited Types', ''),
            '00000000000000000000000000000004': ('StrongReferenceArray', 'Avid StrongReferenceArray to Simple Types', ''),

            '00000000000000000000000000000010': ('Boolean', 'Signedness', ''),
            '0000000000000000000000000000000f': ('UInt8',   'Length in bytes', ''),

            '0000000000000000000000000000001b': ('Reference', 'Unkown data 1', ''),


            # Looks like regular SMPTE label but not present in RP210v10
            '060e2b34010101050e0b01030101010a': ('UInt16', 'SMPTE UInt16', 'Unkown format 1'),
        }

        for key, items in extra_items.iteritems():
            extra_items[key] = (items[0], self._flat_style(items[1]), items[2])

        self.data.update(extra_items)

    @staticmethod
    def _flat_style(vtype):
        """ Convert random type string to a PEP compatible class attribute name.

        @param vtype: RP210 type string (from SMTPE spreadsheet)
        @return: PEP compatible class attribute string
        """

        ret = vtype.lstrip().capitalize().replace(' ', '_')
        return ret.lower()

    def get_triplet(self, format_ul):
        """ Returns RP210 triplet for given format UL. """

        eul = format_ul.encode('hex_codec')
        if eul not in self.data.keys():
            raise RP210Exception("UL '%s' not found in %s." % (eul, self.__class__))

        return self.data[eul]

    def convert(self, format_ul, value):
        """ Convert @value according to @format_ul type. """

        eul = format_ul.encode('hex_codec')
        edata = value.encode('hex_codec')

        if eul not in self.data.keys():
            print "Error: UL '%s' not found in SMPTE RP210." % eul
            return None

        vtype, vname, _ = self.data[eul]

        for conv_class in mxf.rp210types.CONVERTERS:
            conv = getattr(mxf.rp210types, conv_class)
            if conv.caps:
                if hasattr(conv.caps, 'search'):
                    if conv.caps.search(vtype):
                        match = conv.caps.search(vtype)
                        return conv(value, match)

                elif conv.caps == vtype:
                    return conv(value)
        else:
            raise RP210Exception("No converter for %s, %s" % (vtype, vname))

        return "Cannot convert type %s: %s" % (eul, edata)


class RP210Avid(RP210):
    """ Avid RP210 variant helper class.

    Helper class to convert MXF data types to python objects and vice-versa.
    """

    def __init__(self):
        RP210.__init__(self)
        # Adding Avid format UL
        avid_items = {
            '8b4ebaf0ca0940b554405d72bfbd4b0e': ('Int32', 'Avid Int32? 1', ''),
            '8bb3ad5a842b0585f6e59f10248e494c': ('Int16', 'Avid Int16? 2', ''),
            '93c0b44a156ed52a945df2faf4654771': ('Int16', 'Avid Int16? 3', ''),

            'a01c0004ac969f506095818347b111d4': ('StrongReferenceArray', 'Avid Metadata 1', 'AvidDef1'),
            'a01c0004ac969f506095818547b111d4': ('StrongReferenceArray', 'Avid Metadata 2', 'AvidDef2'),

            'a024006094eb75cbce2aca4d51ab11d3': ('Int32', 'Avid Int32? 4', ''),
            'a024006094eb75cbce2aca4f51ab11d3': ('Int32', 'Avid Int32? 5', ''),
            'a024006094eb75cbce2aca5051ab11d3': ('Int32', 'Avid Int32? 6', ''),
            'a029006094eb75cb9d15fca354c511d3': ('Int32', 'Avid Int32? 7', ''),
            'a9bac6e98e92018d36a2806248054b21': ('Int32', 'Avid Int32? 8', ''),

            'a573fa765aa6468a06e929b37d154fd7': ('Int16', 'Avid Int16? 9', ''),
            'a577a500581c9f050fbf8f904d984e06': ('Int8',  'Avid Int8?  10',  ''),

            'b1f07750aad8875d7839ba85999b4d60': ('Int16', 'Avid Int16? 11', ''),
            'b94a62f973fe6063f3e9dc41bbec46bd': ('Int8',  'Avid Int8?  12',  ''),
            'bf734ae52b16b9eaf8fd061dea7e46ba': ('Int16', 'Avid Int16? 13', ''),

            '82149f0b14ba0ce0473f46bf562e49b6': ('Int32', 'Avid Int32? 14', ''),
        }

        for key, items in avid_items.iteritems():
            avid_items[key] = (items[0], self._flat_style(items[1]), items[2])

        self.data.update(avid_items)


if __name__ == "__main__":
    pprint(RP210().data)

