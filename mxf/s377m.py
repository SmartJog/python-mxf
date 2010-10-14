# -*- coding: utf-8 -*-

""" Implements basic classes to parse SMPTE S377-1-2009 compliant MXF files. """

import re

from mxf.common import InterchangeObject, OrderedDict, Singleton
from mxf.rp210 import RP210Avid as RP210, RP210Exception

class S377MException(Exception):
    """ Raised on non SMPTE 377M input. """

    def __init__(self, error):
        """ Init Method """
        Exception.__init__(self, 'S377M: ' + error)


class KLVFill(InterchangeObject):
    """ KLVFill parser. """

    def __init__(self, fdesc, debug=False):
        InterchangeObject.__init__(self, fdesc, debug)

    def __str__(self):
        return "<KLVFill pos=%d size=%d>" % (self.pos, self.length)

    def read(self):
        """ KLV Fill data has no value. """

        if self.debug:
            print "data:", self.fdesc.read(self.length).encode('hex_codec')
        else:
            self.fdesc.seek(self.fdesc.tell() + self.length)


class KLVDarkComponent(KLVFill):
    """ Generic Dark data handler class. """

    def __init__(self, fdesc, debug=False):
        KLVFill.__init__(self, fdesc, debug)

    def __str__(self):
        return "<KLVDarkComponent pos=%d size=%d ul=%s >" % (self.pos, self.length, self.key.encode('hex_codec'))


class MXFPartition(InterchangeObject):
    """ MXF Partition Pack parser. """

    part_items = [
        ('major_version',       2),
        ('minor_version',       2),
        ('kag_size',            4),
        ('this_partition',      8),
        ('previous_partition',  8),
        ('footer_partition',    8),
        ('header_byte_count',   8),
        ('index_byte_cout',     8),
        ('index_sid',           4),
        ('body_offset',         8),
        ('body_sid',            4),
        ('operational_pattern', 16),
    ]

    def __init__(self, fdesc, debug=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.data = {'essence_containers': [], }

        if not re.search('060e2b34020501010d01020101(0[2-4])(0[0-4])00', self.key.encode('hex_codec')):
            raise S377MException('Not a valid Partition Pack key: %s' % self.key.encode('hex_codec'))

    def __str__(self):
        return '<MXF%(type)sPartition pos=%(pos)s %(openness)s and %(completeness)s>' % {
            'pos': self.pos,
            'type': {'\x02': 'Header', '\x03': 'Body', '\x04': 'Footer'}[self.key[13]],
            'openness': ord(self.key[14]) & 0xfe and 'Closed' or 'Open',
            'completeness': ord(self.key[14]) & 0xfd and 'Complete' or 'Incomplete',
        }

    def __smtpe_377m_check(self):
        """ Check conformance to SMTPE 377M 2004. """

        if self.data['major_version'].encode('hex_codec') != '0001':
            raise S377MException('Invalid Major version for Partition Pack')
        if self.data['minor_version'].encode('hex_codec') not in ('0002', '0003'):
            raise S377MException('Invalid Minor version for Partition Pack')

        # Header Partition Pack checks
        if self.key[14] == '\x02':
            if self.data['this_partition'] != 8 * '\x00':
                raise S377MException('Invalid value for ThisPartition in Header Partition Pack')
            if self.data['previous_partition'] != 8 * '\x00':
                raise S377MException('Invalid value for PreviousPartition in Header Partition Pack')
        # partition_info['operational_pattern'][13] -> 10h –7Fh specialized pattern

        # Footer Patition Pack checks
        if self.key[14] == '\x04':
            if not ord(self.key[14]) & 0xfe:
                raise S377MException('Open Footer Partition is not allowed')

        if len(self.data['essence_containers']) == 0 and self.data['body_sid'] != 4 * '\x00':
            raise S377MException('Invalid value for BodySID in Partition Pack')

    def read(self):
        idx = 0
        data = self.fdesc.read(self.length)

        # Read Partition Pack items
        for pp_item, pp_item_size in self.part_items:
            self.data[pp_item] = data[idx:idx+pp_item_size]
            idx += pp_item_size

        # Read essence containers list, if any
        ec_list_size = self.ber_decode_length(data[idx:idx+4], 4)
        ec_item_size = self.ber_decode_length(data[idx+4:idx+8], 4)

        idx = 8
        while ec_list_size > len(self.data['essence_containers']):
            self.data['essence_containers'].append(data[idx:idx+ec_item_size])
            idx += ec_item_size

        self.__smtpe_377m_check()

        if self.debug:
            print "%d essence containers of %d size in partition:" % (ec_list_size, ec_item_size)

        return

    def human_readable(self):
        for key, item in self.data.items():
            if key == 'essence_containers':
                for i, essence in enumerate(item):
                    print "Essence %d: " % i, essence.encode('hex_codec')
            else:
                print "%s: %s" % (key, item.encode('hex_codec'))
        return


class MXFPrimer(InterchangeObject):
    """ MXF Primer Pack parser. """

    def __init__(self, fdesc, debug=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.data = {}
        self.rp210_convert = RP210()

        if self.key and not re.search('060e2b34020501..0d01020101050100', self.key.encode('hex_codec')):
            raise S377MException('Not a valid Primer Pack key: %s' % self.key.encode('hex_codec'))


    def __str__(self):
        ret = ['<MXFPrimer']
        ret += ['pos=%d' % self.pos]
        ret += ['size=%d' % self.length]
        ret += ['localtags=%d' % len(self.data)]
        if self.debug:
            ret += ['\n']
            data_keys = self.data.keys()
            data_keys.sort()
            for i in data_keys:
                ret += ['%s: %s\n' % (i.encode('hex_codec'), self.data[i].encode('hex_codec'))]
        return ' '.join(ret) + '>'

    def read(self):

        data = self.fdesc.read(self.length)

        lt_list_size = self.ber_decode_length(data[0:4], 4)
        lt_item_size = self.ber_decode_length(data[4:8], 4)

        idx = 8
        while lt_list_size > len(self.data):
            self.data[data[idx:idx+2]] = data[idx+2:idx+lt_item_size]
            idx += lt_item_size

        if self.debug:
            print "%d local tag mappings of %d size in Primer Pack" % (lt_list_size, lt_item_size)

        return

    def convert(self, tag, value):
        etag = tag.encode('hex_codec')
        evalue = value.encode('hex_codec')

        # FIXME: this is a big HACK
        if etag == "0001":
            self.data[tag] = ('060e2b34' + etag).decode('hex_codec')
            self.rp210_convert.data['060e2b34' + etag] = ('StrongReference', 'Avid Dark Metadata Start Reference', '')

        # FIXME: this is a big HACK
        if etag == "0002":
            self.data[tag] = ('060e2b34' + etag).decode('hex_codec')
            self.rp210_convert.data['060e2b34' + etag] = ('StrongReference', 'Avid Preface Reference', '')

        # FIXME: this is a big HACK
        if etag == "0003":
            self.data[tag] = ('060e2b34' + etag).decode('hex_codec')
            self.rp210_convert.data['060e2b34' + etag] = ('StrongReferenceArray', 'Avid StrongReferenceArray to Composited Types', '')

        # FIXME: this is a big HACK
        if etag == "0004":
            self.data[tag] = ('060e2b34' + etag).decode('hex_codec')
            self.rp210_convert.data['060e2b34' + etag] = ('StrongReferenceArray', 'Avid StrongReferenceArray to Simple Types', '')

        if tag not in self.data.keys():
            return "Error: Local key '%s' not found in primer (%s)" % (etag, evalue)

        #if not self.data[tag].startswith('060e2b34'.decode('hex_codec')):
        #    return "Error: '%s' does not map to a SMPTE format UL '%s'" % (etag, self.data[tag].encode('hex_codec'))

        # SMTPE RP 210 conversion
        try:
            return self.rp210_convert.convert(self.data[tag], value)
        except RP210Exception:
            return evalue


class MXFDataSet(InterchangeObject):
    """ MXF parsing class specialized for loading Sets and Packs. """

    def __init__(self, fdesc, primer, debug=False, dark=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.primer = primer
        self.dark = dark
        self.data = {
            'by_tag': OrderedDict(),
            'by_format_ul': OrderedDict(),
        }

        if not self.dark:
            if not self.key.encode('hex_codec').startswith('060e2b34'):
                raise S377MException('Not a SMPTE administrated label')

            if self.key[4] != '\x02':
                raise S377MException('Not an MXF Set/Pack')

            if self.key[5] != '\x53':
                raise S377MException('Non-Local set syntax not supported yet (0x%x)' % ord(self.key[5]))

        self.rp210 = Singleton(RP210)

    def __str__(self):
        ret = ['<MXF' + (self.dark and 'Dark' or '') + 'DataSet']
        ret += ['pos=%d' % self.pos]
        ret += ['size=%d' % self.length]
        ret += ['InstanceUID=%s' % self.i_guid]
        if self.debug:
            ret += ['tags=%d:\n' % len(self.data) \
                + '\n'.join(["%s: %s %d bytes" % (
                    i.encode('hex_codec'),
                    j.encode('hex_codec').ljust(64, ' ')[:64],
                    len(j)
                ) for i, j in self.data['by_tag'].items()])]
        return ' '.join(ret) + '>'

    def __getattribute__(self, attr):
        if attr.startswith('i_'):
            data = object.__getattribute__(self, 'data')
            if data and 'by_format_ul' in data and attr[2:] in data['by_format_ul']:
                return data['by_format_ul'][attr[2:]]

        return object.__getattribute__(self, attr)

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
            offset += set_size + 4

            cvalue = None
            key_name = localtag.encode('hex_codec')
            try:
                cvalue = self.primer.convert(localtag, localdata)
                key_name = self.rp210.get_triplet(self.primer.data[localtag])[1]
            except KeyError, _error:
                print "Primer Pack is missing an entry for:", localtag.encode('hex_codec')

            except RP210Exception, _error:
                print "Could not convert to [data:%s] format %s" % (localdata.encode('hex_codec'), self.primer.data[localtag].encode('hex_codec'))
                cvalue = "[data:%s]" % localdata.encode('hex_codec')

            self.data['by_format_ul'].update({key_name: cvalue})

        return

    def human_readable(self, klv_hash=None, indent=None):

        if not indent:
            indent = 0

        print "%s%s" % (4 * indent * ' ', self)

        for i, j in self.data['by_tag'].items():
            print "%s%s" % (4 * indent * ' ' + '  ', self.primer.convert(i, j))

        return klv_hash


class MXFPreface(MXFDataSet):
    """ MXF Metadata Preface parser. """

    def __init__(self, fdesc, debug=False):
        MXFDataSet.__init__(self, fdesc, debug)

    def __str__(self):
        """ Render function. """
        ret = ['<MXFPreface']
        ret += ['pos=%d' % self.pos]
        ret += ['size=%d' % self.length]
        ret += ['InstanceUID=%s' % self.i_guid]
        if self.debug:
            ret += ['tags=%d:\n' % len(self.data) \
                + '\n'.join(["%s: %s %d bytes" % (
                    i.encode('hex_codec'),
                    j.encode('hex_codec').ljust(64, ' '),
                    len(j)
                ) for i, j in self.data.items()])]
        return ' '.join(ret) + '>'


class RandomIndexMetadata(InterchangeObject):
    """ MXF Random Index Pack metadata parser. """

    def __init__(self, fdesc, debug=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.data = {'partition': []}

    def __str__ (self):
        return '<RandomIndexMetadata pos=%d size=%d entries=%d>' % (self.pos, self.length, len(self.data['partition']))

    def read(self):

        idx = 0
        data = self.fdesc.read(self.length)

        for _ in range(0, (self.length - 4) / 12):
            self.data['partition'].append({
                'body_sid': data[idx:idx+4],
                'byte_offset': data[idx+4:idx+12],
            })
            idx += 12

        total_part_length = self.ber_decode_length(data[idx:idx+4], 4)

        if 16 + self.bytes_num + self.length != total_part_length:
            raise S377MException('Overall length differs from UL length')
        return

