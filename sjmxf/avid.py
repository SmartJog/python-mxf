# -*- coding: utf-8 -*-

""" Implements basic classes to parse Avid specific MXF objects. """

from sjmxf.common import InterchangeObject, Singleton
from sjmxf.s377m import MXFDataSet, MXFPrimer
from sjmxf.rp210 import RP210Avid, RP210
from sjmxf.rp210types import Reference, Integer

class AvidObjectDirectory(InterchangeObject):
    """ Avid ObjectDirectory parser. """

    def __init__(self, fdesc, debug=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.data = []

        if self.key.encode('hex_codec') != '9613b38a87348746f10296f056e04d2a':
            raise Exception('Not a valid Avid ObjectDirectory key')

    def __str__(self):
        return "<AvidObjectDirectory pos=%d size=%d entries=%d>" % (self.pos, self.length, len(self.data))

    def read(self):

        data = self.fdesc.read(self.length)

        od_list_size = Integer(data[0:8], 'UInt64').read()
        od_item_size = Integer(data[8], 'UInt8').read()
        idx = 9

        self.data = []
        while od_list_size > len(self.data):
            self.data.append((
                Reference(data[idx:idx+16]).read(),            # key
                Integer(data[idx+16:idx+24], 'UInt64').read(), # offset
                Integer(data[idx+24], 'UInt8').read(),         # flag
            ))
            idx += od_item_size

        if self.debug:
            print "%d objects of %d bytes size in Object Directory" % (od_list_size, od_item_size)

    def write(self):

        ret = []
        for key, offset, flag in self.data:
            ret.append(Reference(key).write())
            ret.append(Integer(offset, 'UInt64').write())
            ret.append(Integer(flag, 'UInt8').write())

        ret = Integer(len(self.data), 'UInt64').write() \
            + Integer(len(''.join(ret[0:3])), 'UInt8').write() \
            + ''.join(ret)

        self.pos = self.fdesc.tell()
        self.length = len(ret)
        self.fdesc.write(self.key + self.ber_encode_length(self.length, bytes_num=8).decode('hex_codec') + ret)
        return

    def human_readable(self):
        print "Object".rjust(32, ' '), "Offset".rjust(10, ' '), "Flag"
        for item in self.data:
            print item[0].encode('hex_codec'), '%10d' % item[1], item[2].encode('hex_codec')

        return


class AvidAAFDefinition(MXFDataSet):
    """ Avid AAF definition KLV parser. """

    _extra_mappings = {
        '0003': ('StrongReferenceArray', 'Avid links to compound types', ''),
        '0004': ('StrongReferenceArray', 'Avid links to simple types', ''),
        '0010': ('Boolean', 'Signedness', ''),
        '000f': ('UInt8', 'Length in bytes', ''),
        '001b': ('StrongReference', 'Unkown data 1', ''),
    }

    def __init__(self, fdesc, primer, debug=False):
        # Prepare object specific Primer
        aprim = MXFPrimer.customize(primer, Singleton(RP210, 'AvidAAFDefinition'), self._extra_mappings)
        MXFDataSet.__init__(self, fdesc, aprim, debug=debug, dark=True)
        self.set_type = 'AvidAAFDefinition'


class AvidMetadataPreface(MXFDataSet):
    """ Avid metadata dictionary pseudo Preface parser. """

    _extra_mappings = {
        '0001': ('StrongReference', 'AAF Metadata', 'Avid AAF Metadata Reference'),
        '0002': ('StrongReference', 'Preface', 'Avid Preface Reference'),
        '0003': ('AvidOffset', 'Object Directory', 'Position of the Object Directory'),
        '0004': ('UInt32', 'Audio Channels', 'Number of audio channels in source file'),
    }

    def __init__(self, fdesc, primer, debug=False):
        aprim = MXFPrimer.customize(primer, Singleton(RP210, 'AvidMetadataPreface'), self._extra_mappings)
        MXFDataSet.__init__(self, fdesc, aprim, debug=debug, dark=True)
        self.set_type = 'AvidMetadataPreface'


class AvidMXFDataSet(MXFDataSet):
    """ Avid specific DataSet parser. """

    _extra_mappings = {
        '3c07': ('AvidVersion', 'Avid Version Tag', ''),
        '3c03': ('AvidVersion', 'Avid Version Tag', ''),
    }

    def __init__(self, fdesc, primer, debug=False):
        aprim = MXFPrimer.customize(primer, Singleton(RP210Avid), self._extra_mappings)
        MXFDataSet.__init__(self, fdesc, aprim, debug=debug, dark=True)
        self.set_type = 'Avid' + self.set_type


