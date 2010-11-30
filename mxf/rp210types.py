#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Set of classes to help convert RP210 defined types. """

from mxf.common import InterchangeObject
from datetime import datetime
import re

CONVERTERS = ['Reference', 'Version', 'Integer', 'Boolean', 'TimeStamp', 'String', 'Rational', 'Length', 'Array', 'VariableArray', 'AvidOffset', 'AvidVersion', 'XID']

def select_converter(vtype):
    """ Select converter according to @vtype. """

    # FIXME: waiting for PEP #3130
    import sys
    this_module = sys.modules[__name__]

    conv = None
    for conv_class in CONVERTERS:
        conv = getattr(this_module, conv_class)
        if conv.caps:
            if hasattr(conv.caps, 'search'):
                if conv.caps.search(vtype):
                    break
            elif conv.caps == vtype:
                break

    #print "Selecting", str(conv)
    return conv

class RP210TypesException(Exception):

    def __init__(self, message):
        Exception.__init__(self, message)


class Converter(object):
    """ Base class for RP210 type converters.

    Read and write function must be symetric.
    """

    caps = None

    def __init__(self, value):
        self.value = value

    def __str__(self):
        """ Default write function. """
        return self.value.encode('hex_codec')

    def read(self):
        """ Default read function. """
        return self.value

    def write(self):
        """ Default write function. """
        return self.value


class Array(Converter, dict):
    """ RP210 Array converter.

    Helper class to read Batch and Arrays. Auto-converts subtypes.
    """

    caps = re.compile('(?:' + '|'.join([
        r'(StrongReference|WeakReference|AUID)Array',
        r'2 element array of (.+)',
        r'^Batch of (.+)$',
        r'(.+)Batch',
    ]) + ')')

    def __init__(self, value, match):
        Converter.__init__(self, value)
        dict.__init__(self)
        if isinstance(match, basestring):
            match = self.caps.search(match)
        for match_type in match.groups():
            if match_type:
                self.subtype = match_type
                self.subconv = select_converter(self.subtype)
                #print "Array Parser instance of type", match_type
                break
        else:
            raise RP210TypesException('No decoder for %s' % str(match.groups()))

    def __str__(self):
        vector = self.read()
        if isinstance(vector, list) and len(vector) > 0:
            return 'Array of %d items of %d length in bytes.' % (len(vector), len(str(vector[0])))
        else:
            return 'Array of %d items.' % len(vector)

    def read(self):

        value = self.value
        vl_list_size = Integer(value[0:4], 'UInt32').read()
        vl_item_size = Integer(value[4:8], 'UInt32').read()

        idx = 8
        vector = []
        while vl_list_size > len(vector):
            if hasattr(self.subconv.caps, 'search'):
                match = self.subconv.caps.search(self.subtype)
                item = self.subconv(value[idx:idx+vl_item_size], match).read()
            else:
                item = self.subconv(value[idx:idx+vl_item_size]).read()

            #print "Adding item of type", type(item), "to array."
            vector.append(item)
            idx += vl_item_size

        return vector

    def write(self):

        ret = []
        if len(self.value):
            vl_list_size = Integer(len(self.value), 'UInt32').write()
            if hasattr(self.subconv.caps, 'search'):
                match = self.subconv.caps.search(self.subtype)
                vl_item_size = Integer(len(self.subconv(self.value[0], match).write()), 'UInt32').write()
                ret += [self.subconv(item, match).write() for item in self.value]
            else:
                vl_item_size = Integer(len(self.subconv(self.value[0]).write()), 'UInt32').write()
                ret += [self.subconv(item).write() for item in self.value]

        else:
            vl_list_size = Integer(0, 'UInt32').write()
            # Default value from SMPTE 377M
            if self.subconv == Reference:
                vl_item_size = Integer(16, 'UInt32').write()
            else:
                vl_item_size = Integer(0, 'UInt32').write()

        return vl_list_size + vl_item_size + ''.join(ret)


class VariableArray(Array):

    caps = re.compile('(?:' + '|'.join([
        r'(16 bit Unicode String) Array',
        r'Array of (U?Int ?(8|16|32|64))',
    ]) + ')')

    def __init__(self, value, match):
        Array.__init__(self, value, match)

    def read(self):
        vector = []
        if self.subtype == '16 bit Unicode String':
            for item in self.value[0:-2].split('\x00\x00'):
                vector.append(String(item, self.subtype).read())
        else:
            ar_item_size = Integer(None, self.subtype).length
            for item in range(0, len(self.value) / ar_item_size):
                vector.append(Integer(self.value[item*ar_item_size:(item+1)*ar_item_size], self.subtype).read())

        return vector

    def write(self):
        vector = []
        if self.subtype == "16 bit Unicode String":
            for item in self.value:
                vector.append(String(item, self.subtype).write())
            ret = '\x00\x00'.join(vector) + '\x00\x00'
        else:
            for item in self.value:
                vector.append(Integer(item, self.subtype).write())
            ret = ''.join(vector)

        return ret


class Reference(Converter):
    """ RP210 Reference converter.

    StrongReference: “One-to-one” relationship between sets and implemented in
    MXF with UUIDs. Strong references are typed which means that the definition
    identifies the kind of set which is the target of the reference.

    WeakReference: “Many-to-one” relationship between sets implemented in MXF
    with UUIDs. Weak references are typed which means that the definition
    identifies the kind of set which is the target of the reference.
    """

    caps = re.compile('(' + '|'.join([
        r'(Weak|Strong)Reference$',
        r'Primary Package', # WeakReference
        r'As per ISO 11578 standard \(Annex A\)',
        r'^(Universal Label|UL)',
        r'AUID$',
        r'UMID',
        r'UUID',
        r'PackageID',
    ]) + ')')

    def __init__(self, value, match=None):
        Converter.__init__(self, value)
        if not match:
            self.subtype = 'Reference'
        elif isinstance(match, basestring):
            self.subtype = match
        else:
            self.subtype = match.group(0)

    def __str__(self):
        return self.value.encode('hex_codec')


class Version(Converter):
    """ RP210 Version converter. """

    _compound = {
        'ProductVersion': [
            ('major',   'UInt16'),
            ('minor',   'UInt16'),
            ('patch',   'UInt16'),
            ('build',   'UInt16'),
            ('release', 'UInt16'), # Enum
        ],
        'VersionType': [
            ('major', 'UInt8'),
            ('minor', 'UInt8'),
        ],
    }

    caps = re.compile('(ProductVersion|VersionType)')

    def __init__(self, value, match):
        Converter.__init__(self, value)
        if isinstance(match, basestring):
            match = Version.caps.search(match)
        self.type = match.group(1)

    def __str__(self):
        return '.'.join([str(item.__str__()) for item in self.read()])

    def read(self):
        ret = []
        offset = 0
        for _item, itype in self._compound[self.type]:
            value = self.value[offset:offset+Integer(None, itype).length]
            ret.append(Integer(value, itype).read())
            offset += len(value)

        return ret

    def write(self):
        ret = []
        for index, itype in enumerate(self._compound[self.type]):
            ret.append(Integer(self.value[index], itype[1]).write())

        return ''.join(ret)


class TimeStamp(Converter):
    """ RP210 TimeStamp converter. """

    _compound = (
        ('year', 'Int16'),
        ('month', 'UInt8'),
        ('day', 'UInt8'),
        ('hour', 'UInt8'),
        ('minute', 'UInt8'),
        ('second', 'UInt8'),
        ('microsecond', 'UInt8'),
    )

    caps = 'TimeStamp'

    def __str__(self):
        return str(self.read()) or 'Unknown timestamp'

    def read(self):
        ret = []
        offset = 0
        for _item, itype in self._compound:
            value = self.value[offset:offset+Integer(None, itype).length]
            ret.append(Integer(value, itype).read())
            offset += len(value)

        # milliseconds are represented as 1/4 of the real value
        ret[-1] = ret[-1] * 4

        if ret == [0, 0, 0, 0, 0, 0, 0]:
            # SMTPE 337M: timestamp unknown
            return None

        try:
            return datetime(ret[0], ret[1], ret[2], ret[3], ret[4], ret[5], ret[6])
        except:
            raise RP210TypesException('Invalid date format')

    def write(self):
        ret = []
        if self.value:
            for item, itype in self._compound:
                if item == 'microsecond':
                    value = getattr(self.value, item)
                    if value > 0:
                        # python microseconds = range(10000000)
                        # mxf only supports 128 values as value / 4
                        value = value / (100 * 4) / 1000000
                else:
                    value = getattr(self.value, item)
                ret.append(Integer(value, itype).write())
        else:
            for _item, itype in self._compound:
                ret.append(Integer(0, itype).write())

        return ''.join(ret)


class Integer(Converter):
    """ RP210 Integer converter. """

    caps = re.compile(r'^U?Int ?(8|16|32|64)', re.I)

    def __init__(self, value, match=None):
        Converter.__init__(self, value)
        if isinstance(match, basestring):
            match = Integer.caps.search(match)
        self.length = int(match.group(1)) / 8

    def __str__(self):
        return '%d' % self.read()

    def read(self):
        return InterchangeObject.ber_decode_length(self.value, self.length)

    def write(self):
        return InterchangeObject.ber_encode_length(self.value, self.length, prefix=False).decode('hex_codec')


class Length(Integer):
    """ RP210 Length converter. """

    caps = re.compile('(Length|Position)')

    def __init__(self, value, _match=None):
        Integer.__init__(self, value, 'Int64')


class XID(Integer):
    """ RP210 x ID converter. """

    caps = re.compile('Track ?ID')

    def __init__(self, value, _match=None):
        Integer.__init__(self, value, 'Int32')


class Rational(Converter):
    """ RP210 Rational converter. """

    caps = 'Rational'

    def __str__(self):
        return '%d/%d' % self.read()

    def read(self):
        num = Integer(self.value[0:4], 'UInt32').read()
        den = Integer(self.value[4:8], 'UInt32').read()
        return (num, den)

    def write(self):
        return Integer(self.value[0], 'UInt32').write() + Integer(self.value[1], 'UInt32').write()


class Boolean(Converter):
    """ RP210 Boolean converter. """

    caps = 'Boolean'

    def __str__(self):
        return ord(self.value) != 0 and 'True' or 'False'

    def read(self):
        return ord(self.value) != 0

    def write(self):
        return self.value and '\1' or '\0'


class String(Converter):
    """ RP210 String converter. """

    caps = re.compile(r'^(16 bit Unicode String|UTF-16 char string)$')

    def __init__(self, value, _match=None):
        Converter.__init__(self, value)

    def __str__(self):
        ret = self.read()
        if len(ret):
            return ret.rstrip('\0')
        else:
            return 'empty string'

    def read(self):
        try:
            return self.value.decode('utf_16_be')
        except UnicodeDecodeError:
            avid_type = self.value[:17].encode('hex_codec')
            avid_value = self.value[17:]

            if avid_type == '4c0002100100000000060e2b3401040101':
                # Avid string
                cvalue = "au16:" + avid_value.decode('utf_16_le').encode('utf_8')[:-1]

            elif avid_type == '4c0007010100000000060e2b3401040101':
                # Avid Int64 (written in reverse hex order)
                if len(avid_value) > 5:
                    raise Exception("Avid Length too long")
                dur = 0
                for idx in range(1, 5):
                    dur = dur << 8 | ord(self.value[-idx])

                cvalue = "aint32:" + str(dur)
            else:
                cvalue = "a??: [%s:%s]" % (avid_type, avid_value)

            return cvalue

    def write(self):
        if self.value.startswith('au16:'):
            return '4c0002100100000000060e2b3401040101'.decode('hex_codec') + (self.value[5:].decode('utf_8') + '\0').encode('utf_16_le')

        elif self.value.startswith('aint32:'):
            dur = int(self.value[7:])
            cvalue = ""
            for _ in range(1, 5):
                cvalue += "%02x" % (dur & 0x000000FF)
                dur = dur >> 8

            return ('4c0007010100000000060e2b3401040101' + cvalue).decode('hex_codec')

        elif self.value.startswith('a??:'):
            raise Exception('Cannot encode')

        return self.value.encode('utf_16_be')


class AvidOffset(Converter):
    """ Avid Offset converter.

    Used to store (at least) the absolution position of AvidObjectDirectory.
    """

    caps = "AvidOffset"

    def read(self):
        return Integer(self.value[-8:], 'UInt64').read()

    def write(self):
        return Integer(self.value, 'UInt64').write().rjust(24, '\x00')


class AvidVersion(Version):
    """ Avid Version converter. """

    _compound = {
        'AvidVersion': [
            ('major',      'UInt16'),
            ('minor',      'UInt16'),
            ('tertiary',   'UInt16'),
            ('patchLevel', 'UInt16'),
            ('type',       'UInt8'), # Enum
        ],
    }

    caps = re.compile('(AvidVersion)')


