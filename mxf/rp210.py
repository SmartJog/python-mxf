#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Helper module to convert MXF data to python types according to SMPTE RP210. """

from mxf.common import InterchangeObject
import csv
import re
from pprint import pprint, pformat

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
                        row['Data Element Name'],
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

    def get_triplet(self, format_ul):
        """ Returns RP210 triplet for given format UL. """

        eul = format_ul.encode('hex_codec')
        if eul not in self.data.keys():
            raise RP210Exception("UL '%s' not found in %s." % (eul, self.__class__))

        return self.data[eul]

    @staticmethod
    def _convert_single(vtype, value):
        """ Convert non-Array types. """

        edata = value.encode('hex_codec')

        if vtype in ('StrongReference', 'WeakReference'):
            return edata

        elif vtype == "As per ISO 11578 standard (Annex A)":
            return edata

        elif vtype in ('AUID', 'UMID', 'UL', 'UUID', 'Universal Label', 'PackageID', 'Universal Labels'):
            return edata

        elif vtype in ('DataStream'):
            return "Raw data stream"

        elif vtype in ('UTF-16 char string'):
            return "u16 %s" % (value.decode('utf_16_be'))

        elif vtype in ('16 bit Unicode String'):
            try:
                return "u16 %s" % (value.decode('utf_16_be')[:-1])
            except UnicodeDecodeError:
                return None

        elif re.match('U?Int ?(8|16|32|64)', vtype, re.I):
            length = InterchangeObject.ber_decode_length(value, len(value))
            return '%d' % (length)

        elif vtype == 'Boolean':
            return '%s' % (ord(value) and 'True' or 'False')

        elif vtype in ('Length'):
            length = InterchangeObject.ber_decode_length(value[0:8], 8)
            return "%d" % (length)

        elif vtype in ('VersionType'):
            major = InterchangeObject.ber_decode_length(value[0], 1)
            minor = InterchangeObject.ber_decode_length(value[1], 1)
            return "%d.%d" % (major, minor)

        elif vtype == 'Rational':
            den = InterchangeObject.ber_decode_length(value[0:4], 4)
            num = InterchangeObject.ber_decode_length(value[4:8], 4)
            return "%d/%d" % (num, den)

        elif vtype == 'TimeStamp':
            year = InterchangeObject.ber_decode_length(value[0:2], 2)
            month = InterchangeObject.ber_decode_length(value[2], 1)
            day = InterchangeObject.ber_decode_length(value[3], 1)
            hour = InterchangeObject.ber_decode_length(value[4], 1)
            minute = InterchangeObject.ber_decode_length(value[5], 1)
            second = InterchangeObject.ber_decode_length(value[6], 1)
            millisec = InterchangeObject.ber_decode_length(value[7], 1)

            if (year, month, day, hour, minute, second, millisec) == (0, 0, 0, 0, 0, 0, 0):
                return "SMTPE 377M: unknown timestamp"

            from datetime import datetime
            date = datetime(year, month, day, hour, minute, second, millisec)
            return "%s" % (str(date))

        return None

    def convert(self, format_ul, value):
        """ Convert @value according to @format_ul type. """

        eul = format_ul.encode('hex_codec')
        edata = value.encode('hex_codec')

        if eul not in self.data.keys():
            print "Error: UL '%s' not found in SMPTE RP210." % eul
            return None

        vtype, vname, _ = self.data[eul]

        if vtype.startswith('Batch of') or vtype.endswith('Batch') \
           or vtype in ('StrongReferenceArray', 'WeakReferenceArray', 'AUIDArray'):
            vl_list_size = InterchangeObject.ber_decode_length(value[0:4], 4)
            vl_item_size = InterchangeObject.ber_decode_length(value[4:8], 4)

            if vtype.startswith('Batch of'):
                item_vtype = vtype[8:]
            elif vtype.endswith('Batch') or vtype.endswith('Array'):
                item_vtype = vtype[:-5]
            else:
                raise Exception('Unknown vtype:' + vtype)

            vector = []
            if vl_list_size != 0 and vl_item_size != 0:
                idx = 8

                while vl_list_size > len(vector):
                    item = self._convert_single(item_vtype, value[idx:idx+vl_item_size])
                    vector.append(item)
                    idx += vl_item_size

            print  "%s (%s): %d item(s) of %d length (%s)" % (vtype, vname, vl_list_size, vl_item_size, "")
            return vector

        elif vtype == '16 bit Unicode String Array':
            array = []
            # Drop ending UTF-16 \0
            for item in value[0:-2].split('\x00\x00'):
                array.append(self._convert_single('UTF-16 char string', item))

            print "Array of %s u16 string(s): %s" % (len(array), pformat(array))
            return array

        elif re.match('Array of U?Int*', vtype, re.I):
            array = []
            ar_search = re.search('Array of (U?Int(8|16|32|64))', vtype)
            ar_item_size = int(ar_search.group(2)) / 8

            for item in range(0, len(value) / ar_item_size):
                array.append(self._convert_single(ar_search.group(1), value[item*ar_item_size:(item+1)*ar_item_size]))

            print "%s (%s) List of %s: %s items" % (vtype, vname, ar_search.group(0), len(array))
            return array

        elif vtype == '2 element array of Int32':
            array = []
            ar_list_size = InterchangeObject.ber_decode_length(value[0:4], 4)
            ar_item_size = InterchangeObject.ber_decode_length(value[4:8], 4)

            idx = 8
            while ar_list_size > len(array):
                item = self._convert_single('Int32', value[idx:idx+ar_item_size])
                array.append(item)
                idx += ar_item_size

            print "%s (%s): %d item(s) of %d length" % (vtype, vname, ar_list_size, ar_item_size)
            return array

        elif vtype in ('VideoSignalType', 'Enumerated', 'ColorimetryCode', 'ProductVersion'):
            return "%s (%s): %s" % (vname, vtype, edata)

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

        self.data.update(avid_items)

    @staticmethod
    def _convert_single(vtype, value):
        cvalue = RP210._convert_single(vtype, value)

        if cvalue:
            return cvalue

        if vtype == '16 bit Unicode String':
            avid_type = value[:17].encode('hex_codec')
            avid_value = value[17:]

            if avid_type == '4c0002100100000000060e2b3401040101':
                # Avid string
                cvalue = "au16:" + avid_value.decode('utf_16_le').encode('utf_8')[:-1]

            elif avid_type == '4c0007010100000000060e2b3401040101':
                # Avid Int64 (written in reverse hex order)
                if len(avid_value) > 5:
                    raise Exception("Length too long")
                dur = 0
                for idx in range(1, 5):
                    dur = dur << 8 | ord(value[-idx])

                cvalue = "aint64:" + str(dur)

        else:
            cvalue = "a??: [%s:%s]" % (value[:17].encode('hex_codec'), value[17:])

        return cvalue


if __name__ == "__main__":
    pprint(RP210().data)

