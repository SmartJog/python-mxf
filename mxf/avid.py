# -*- coding: utf-8 -*-

""" Implements basic classes to parse Avid specific MXF objects. """

from mxf.common import InterchangeObject, OrderedDict
from mxf.s377m import MXFDataSet
from mxf.rp210types import Reference, Integer

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
        self.fdesc.write(self.key + self.ber_encode_length(len(ret), bytes_num=8).decode('hex_codec') + ret)
        return

    def human_readable(self):
        print "Object".rjust(32, ' '), "Offset".rjust(10, ' '), "Flag"
        for item in self.data:
            print item[0].encode('hex_codec'), '%10d' % item[1], item[2].encode('hex_codec')

        return


class AvidMetadataPreface(MXFDataSet):
    """ Avid metadata dictionary pseudo Preface parser. """

    def __init__(self, fdesc, primer, debug=False):
        MXFDataSet.__init__(self, fdesc, primer, debug, dark=True)
        self.data = {
            'by_tag': OrderedDict(),
            'by_format_ul': OrderedDict(),
        }

    def __str__(self):
        ret = ['<AvidMetadataPreface']
        ret += ['pos=%d' % self.pos]
        ret += ['size=%d' % self.length]
        ret += ['InstanceUID=%s' % self.data['by_tag']['\x3c\x0a'].encode('hex_codec')]
        return ' '.join(ret) + '>'

    def read(self):
        """ Generic read method for sets and packs. """

        idx = 0
        data = self.fdesc.read(self.length)

        # Get all items
        offset = idx
        while offset < idx + self.length:
            set_size = self.ber_decode_length(data[offset+2:offset+4], 2)
            localtag = data[offset:offset+2]
            localdata = data[offset+4:offset+set_size+4]
            self.data['by_tag'].update({localtag: localdata})

            cvalue = None
            key_name = None
            if localtag.encode('hex_codec') == '0003':
                cvalue = 'Duration in a very long form ?'
                key_name = 'duration'
            elif localtag.encode('hex_codec') == '0004':
                cvalue = 'Number of audio channels in an Int64 ?'
                key_name = 'audio_channels'
            else:
                try:
                    key_name, cvalue = self.primer.decode_from_local_tag(localtag, localdata)

                except Exception, _error:
                    print "Could not convert to [data:%s] format %s" % (localdata.encode('hex_codec'), self.primer.data[localtag].encode('hex_codec'))
                    raise

            self.data['by_format_ul'].update({key_name: cvalue})

            offset += set_size + 4

        return

    def human_readable(self, klv_hash=None, indent=None):

        if not indent:
            indent = 0

        print "%s%s" % (4 * indent * ' ', self)

        for i, j in self.data['by_format_ul'].items():
            if i in ('preface', 'aaf_metadata'):
                if j.read() not in klv_hash:
                    print "%s%s: broken reference, %s" % (4 * indent * ' ' + '  ', i, j)
                else:
                    print ""
                    klv_hash.pop(j.read()).human_readable(klv_hash, indent+1)

            elif i == 'guid':
                continue

            else:
                print "%s%s: %s %s" % (4 * indent * ' ' + '  ', i, j, type(j))

        return klv_hash


