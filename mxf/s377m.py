# -*- coding: utf-8 -*-

""" Implements basic classes to parse SMPTE S377-1-2009 compliant MXF files. """

import re

from mxf.common import InterchangeObject, OrderedDict, Singleton
from mxf.rp210 import RP210Exception, RP210
from mxf.rp210types import Array, Reference, Integer, select_converter, RP210TypesException

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
            self.data = self.fdesc.read(self.length)

    def write(self):
        self.pos = self.fdesc.tell()
        self.length = len(self.data)
        self.fdesc.write(self.key + self.ber_encode_length(self.length, bytes_num=8).decode('hex_codec') + self.data)

class KLVDarkComponent(KLVFill):
    """ Generic Dark data handler class. """

    def __init__(self, fdesc, debug=False):
        KLVFill.__init__(self, fdesc, debug)

    def __str__(self):
        return "<KLVDarkComponent pos=%d size=%d ul=%s >" % (self.pos, self.length, self.key.encode('hex_codec'))


class MXFPartition(InterchangeObject):
    """ MXF Partition Pack parser. """

    _compound = [
        ('major_version',       'UInt16', 2),
        ('minor_version',       'UInt16', 2),
        ('kag_size',            'UInt32', 4),
        ('this_partition',      'UInt64', 8),
        ('previous_partition',  'UInt64', 8),
        ('footer_partition',    'UInt64', 8),
        ('header_byte_count',   'UInt64', 8),
        ('index_byte_cout',     'UInt64', 8),
        ('index_sid',           'UInt32', 4),
        ('body_offset',         'UInt64', 8),
        ('body_sid',            'UInt32', 4),
        ('operational_pattern', 'Universal Label', 16),
        #('essence_containers',  'Batch of Universal Labels', 8 + 16n),
    ]

    def __init__(self, fdesc, debug=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.data = OrderedDict()

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

        if self.data['major_version'] != 1:
            raise S377MException('Invalid Major version for Partition Pack')
        if self.data['minor_version'] not in (2, 3):
            raise S377MException('Invalid Minor version for Partition Pack')

        # Header Partition Pack checks
        if self.key[13] == '\x02':
            if self.data['this_partition'] != 0:
                raise S377MException('Invalid value for ThisPartition in Header Partition Pack')
            if self.data['previous_partition'] != 0:
                raise S377MException('Invalid value for PreviousPartition in Header Partition Pack')
        # partition_info['operational_pattern'][13] -> 10h –7Fh specialized pattern

        # Footer Patition Pack checks
        if self.key[13] == '\x04':
            if not ord(self.key[14]) & 0xfe:
                raise S377MException('Open Footer Partition is not allowed')

        if len(self.data['essence_containers']) == 0 and self.data['body_sid'] != 0:
            raise S377MException('Invalid value for BodySID in Partition Pack')

    def read(self):
        idx = 0
        data = self.fdesc.read(self.length)

        # Read Partition Pack items
        for pp_item, pp_type, pp_size in self._compound:
            conv = select_converter(pp_type)
            self.data[pp_item] = conv(data[idx:idx+pp_size], pp_type).read()
            idx += pp_size

        # Read essence containers list, if any
        self.data['essence_containers'] = Array(data[idx:], 'Batch of Universal Labels').read()

        self.__smtpe_377m_check()

        if self.debug:
            print "%d essences in partition:" % len(self.data['essence_containers'])

        return

    def write(self):
        ret = ""
        for pp_item, pp_type, _ in self._compound:
            conv = select_converter(pp_type)
            ret += conv(self.data[pp_item], pp_type).write()

        ret += Array(self.data['essence_containers'], 'Batch of Universal Labels').write()

        self.pos = self.fdesc.tell()
        self.length = len(ret)
        self.fdesc.write(self.key + self.ber_encode_length(self.length, bytes_num=8).decode('hex_codec') + ret)
        return

    def human_readable(self):
        for key, item in self.data.items():
            if key == 'essence_containers':
                for i, essence in enumerate(item):
                    print "Essence %d: " % i, essence.encode('hex_codec')
            elif key == 'operational_pattern':
                print "%s: %s" % (key, item.encode('hex_codec'))
            else:
                print "%s: %s" % (key, item)
        return


class MXFPrimer(InterchangeObject):
    """ MXF Primer Pack parser. """

    def __init__(self, fdesc, rp210=None, debug=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.data = OrderedDict()

        if rp210:
            self.rp210 = rp210
        else:
            self.rp210 = Singleton(RP210)

        if self.key and not re.search('060e2b34020501..0d01020101050100', self.key.encode('hex_codec')):
            raise S377MException('Not a valid Primer Pack key: %s' % self.key.encode('hex_codec'))

    def __str__(self):
        ret = ['<MXFPrimer']
        ret += ['pos=%d' % self.pos]
        ret += ['size=%d' % self.length]
        ret += ['localtags=%d' % len(self.data)]
        if self.debug:
            ret += ['\n']
            for i, j in self.data.items():
                ret += ['%s: %s\n' % (i.encode('hex_codec'), j.encode('hex_codec'))]
        return ' '.join(ret) + '>'

    @staticmethod
    def customize(primer, spec, mappings=None):
        """ Modifies a primer to abide @spec rules with optional @mappings.

        @spec: instance of a mxf.rp210 like object
        @mappings: a dictionary that is passed to inject method

        @returns: custimized Primer object.
        """

        import copy
        aprim = copy.copy(primer)

        if mappings:
            spec.inject(mappings)

        aprim.data = {}
        aprim.data.update(primer.data)
        aprim.rp210 = spec

        if mappings:
            aprim.inject(mappings.keys())

        return aprim

    def inject(self, mappings):
        """ Insert new mappings in Primer.

        Allows insertion of new local tag to format UL mappings with their
        RP210 basic type.
        """

        for item in mappings:
            self.data[item.decode('hex_codec')] = item.rjust(32, '0').decode('hex_codec')
        return

    def read(self):

        data = self.fdesc.read(self.length)

        lt_list_size = Integer(data[0:4], 'UInt32').read()
        lt_item_size = Integer(data[4:8], 'UInt32').read()

        idx = 8
        while lt_list_size > len(self.data):
            self.data[data[idx:idx+2]] = Reference(data[idx+2:idx+lt_item_size], 'Universal Label').read()
            idx += lt_item_size

        if self.debug:
            print "%d local tag mappings in Primer Pack" % len(self.data)

        return

    def write(self):

        ret = ""
        for tag, ful in self.data.items():
            ret += tag + Reference(ful, 'Universal Label').write()

        lt_list_size = Integer(len(self.data), 'UInt32').write()
        lt_item_size = Integer(len(ret) / len(self.data), 'UInt32').write()
        ret = lt_list_size + lt_item_size + ret

        self.pos = self.fdesc.tell()
        self.length = len(ret)
        self.fdesc.write(self.key + self.ber_encode_length(self.length, bytes_num=8).decode('hex_codec') + ret)
        return

    def decode_from_local_tag(self, tag, value):
        """ Decode data according to local tag mapping to format Universal Labels. """

        etag = tag.encode('hex_codec')
        evalue = value.encode('hex_codec')

        if tag not in self.data.keys():
            print "Error: Local key '%s' not found in primer" % etag
            return etag, evalue

        #if not self.data[tag].startswith('060e2b34'.decode('hex_codec')):
        #    return "Error: '%s' does not map to a SMPTE format UL '%s'" % (etag, self.data[tag].encode('hex_codec'))

        key = "unkown_data_format"
        # SMTPE RP 210 conversion
        try:
            key = self.rp210.get_triplet_from_format_ul(self.data[tag])[1]
            return key, self.rp210.convert(self.data[tag], value)
        except RP210Exception, error:
            print error
            return key, evalue

    def encode_from_local_tag(self, tag, value):
        """ Encode data according to local tag mapping to format Universal Labels. """

        etag = tag.encode('hex_codec')

        if tag not in self.data.keys():
            return "Error: Local key '%s' not found in primer" % etag

        # SMTPE RP 210 conversion
        try:
            return tag, self.rp210.convert(self.data[tag], value)
        except RP210Exception:
            return tag, value

    def get_mapping(self, tag):
        """ Shows Primer/RP210 mapping for @tag local tag. """

        try:
            format_ul = self.data[tag]
        except KeyError:
            return tag, ('unkown_tag', 'unknown_data_format', '')

        try:
            return format_ul, self.rp210.get_triplet_from_format_ul(format_ul)
        except RP210Exception, error:
            print error
            return format_ul, ('unknown_type', 'unknown_data_format', '')


class MXFDataSet(InterchangeObject):
    """ MXF parsing class specialized for loading Sets and Packs. """

    dataset_names = {
         # SMPTE 377M: Strutural Metadata Sets
         '060e2b34025301010d01010101010900': 'Filler',
         '060e2b34025301010d01010101010f00': 'Sequence',

         '060e2b34025301010d01010101011100': 'SourceClip',
         '060e2b34025301010d01010101011400': 'TimecodeComponent',

         '060e2b34025301010d01010101012300': 'EssenceContainerData',
         '060e2b34025301010d01010101012800': 'CDCIEssenceDescriptor',

         '060e2b34025301010d01010101011800': 'ContentStorage',

         '060e2b34025301010d01010101012e00': 'EssenceDescription',
         '060e2b34025301010d01010101013000': 'Identification',

         '060e2b34025301010d01010101013600': 'MaterialPackage',
         '060e2b34025301010d01010101013700': 'SourcePackage',

         '060e2b34025301010d01010101013b00': 'TimelineTrack',
         '060e2b34025301010d01010101013f00': 'TaggedValue', # Avid Dark 2

         '060e2b34025301010d01010101014200': 'GenericSoundEssenceDescriptor',
         '060e2b34025301010d01010101014400': 'MultipleDescriptor',
         '060e2b34025301010d01010101014700': 'AES3PCMDescriptor',
         '060e2b34025301010d01010101014800': 'WaveAudioDescriptor',

         '060e2b34025301010d01010101015100': 'MPEG2VideoDescriptor',
    }

    def __init__(self, fdesc, primer, debug=False, dark=False):
        InterchangeObject.__init__(self, fdesc, debug)
        self.primer = primer
        self.dark = dark
        self.data = OrderedDict()
        self.set_type = 'DataSet'
        self.element_mapping = {}

        if self.key.encode('hex_codec') not in MXFDataSet.dataset_names.keys():
            #print "MXFDataSet is dark", self.key.encode('hex_codec')
            self.dark = True
            self.set_type = 'Dark' + self.set_type
        else:
            self.set_type = MXFDataSet.dataset_names[self.key.encode('hex_codec')]

        if not self.dark:
            if not self.key.encode('hex_codec').startswith('060e2b34'):
                raise S377MException('Not a SMPTE administrated label')

            if self.key[4] != '\x02':
                raise S377MException('Not an MXF Set/Pack')

            if self.key[5] != '\x53':
                raise S377MException('Non-Local set syntax not supported yet (0x%x)' % ord(self.key[5]))

    def __str__(self):
        ret = ['<MXF' + self.set_type]
        ret += ['pos=%d' % self.pos]
        ret += ['size=%d' % self.length]
        ret += ['InstanceUID=%s' % self.data['\x3c\x0a']]
        if self.debug:
            ret += ['tags=%d:\n' % len(self.data) \
                + '\n'.join(["%s: %s" % (
                    i.encode('hex_codec'), j
                ) for i, j in self.data.items()])]
        return ' '.join(ret) + '>'

    def get_element(self, element_name):
        return self.data.get(self.element_mapping.get(element_name, None), None)

    def set_element(self, element_name, value):
        self.data[self.element_mapping[element_name]] = value

    def rm_element(self, element_name):
        if self.element_mapping.get(element_name, None):
            del self.data[self.element_mapping[element_name]]
            del self.element_mapping[element_name]
            return True

        return False

    def get_strong_references(self):
        ref_list = []
        for _, j in self.data.items():
            if isinstance(j, Reference) and j.subtype == 'StrongReference':
                ref_list.append(j.read())
            elif isinstance(j, Array) and j.subtype == 'StrongReference':
                [ref_list.append(k) for k in j.read()]

        return ref_list

    def read(self):
        """ Generic read method for sets and packs. """

        idx = 0
        data = self.fdesc.read(self.length)

        # Get all items
        offset = idx
        while offset < idx + self.length:
            set_size = Integer(data[offset+2:offset+4], 'UInt16').read()
            localtag = data[offset:offset+2]
            localdata = data[offset+4:offset+set_size+4]
            offset += set_size + 4

            element_name, cvalue = self.primer.decode_from_local_tag(localtag, localdata)
            self.element_mapping.update({element_name: localtag})
            self.data.update({localtag: cvalue})

        return

    def write(self):

        ret = []
        for tag, value in self.data.items():
            # Not all values are decoded
            if isinstance(value, basestring):
                localtag = tag
                cvalue = value.decode('hex_codec')
            else:
                localtag, conv = self.primer.encode_from_local_tag(tag, value.read())
                cvalue = conv.write()
            ret.append(localtag + self.ber_encode_length(len(cvalue), bytes_num=2, prefix=False).decode('hex_codec') + cvalue)

        ret = ''.join(ret)
        self.pos = self.fdesc.tell()
        self.length = len(ret)
        self.fdesc.write(self.key + self.ber_encode_length(self.length, bytes_num=8).decode('hex_codec') + ret)
        return

    def human_readable(self, klv_hash=None, indent=None):

        if not indent:
            indent = 0

        print "%s%s" % (4 * indent * ' ', self)

        for i, j in self.data.items():

            element_name = self.primer.get_mapping(i)[1][1]
            if len(element_name) == 0:
                element_name = self.primer.get_mapping(i)[1][2]


            if element_name == 'guid':
                continue

            elif isinstance(j, Reference):
                if j.subtype in ('AUID', 'PackageID', 'Universal Label'):
                    print "%s%s: %s" % (4 * indent * ' ' + '  ', element_name, j)
                elif klv_hash and j.read() not in klv_hash:
                    print "%s%s: broken reference, %s %s" % (4 * indent * ' ' + '  ', element_name, j, j.subtype)
                elif klv_hash and not klv_hash[j.read()]['used']:

                    print "%s%s: New reference" % (4 * indent * ' ' + '  ', element_name)
                    klv_hash[j.read()]['used'] = True
                    klv_hash[j.read()]['klv'].human_readable(klv_hash, indent+1)
                else:
                    print "%s%s: <-> %s" % (4 * indent * ' ' + '  ', element_name, j)

            elif isinstance(j, Array):
                if j.subconv is Reference:
                    print "%s%s: Array (%d items)" % (4 * indent * ' ' + '  ', element_name, len(j.read()))
                    #print "%s" % (4 * indent * ' ' + '  '), [_.encode('hex_codec') for _ in j.read()]
                    for x, k in enumerate(j.read()):
                        if j.subtype in ('AUID', 'Universal Labels'):
                            print "%sitem %d: %s" % (4 * indent * ' ' + '  ', x, Reference(k))
                        elif klv_hash and k not in klv_hash:
                            print "%sitem %d: broken reference, %s" % (4 * indent * ' ' + '  ', x, Reference(k))
                        elif klv_hash and not klv_hash[k]['used']:
                            klv_hash[k]['used'] = True
                            klv_hash[k]['klv'].human_readable(klv_hash, indent+1)
                        else:
                            print "%sitem %d: <-> %s" % (4 * indent * ' ' + '  ', x, Reference(k))
                else:
                    for k in j.read():
                        print "%s%s: %s" % (4 * indent * ' ' + '  ', element_name, k)
            else:
                try:
                    print "%s%s: %s %s" % (4 * indent * ' ' + '  ', element_name, j, type(j))
                except RP210TypesException, error:
                    print error

        print ""
        if klv_hash:
            return klv_hash
        return


class MXFPreface(MXFDataSet):
    """ MXF Metadata Preface parser. """

    def __init__(self, fdesc, debug=False):
        MXFDataSet.__init__(self, fdesc, debug)
        self.set_type = 'Preface'


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
                'body_sid': Integer(data[idx:idx+4], 'UInt32').read(),
                'byte_offset': Integer(data[idx+4:idx+12], 'UInt64').read(),
            })
            idx += 12

        total_part_length = Integer(data[idx:idx+4], 'UInt32').read()

        if 16 + self.bytes_num + self.length != total_part_length:
            raise S377MException('Overall length differs from UL length')
        return

    def write(self):
        ret = ""
        for partition in self.data['partition']:
            ret += Integer(partition['body_sid'], 'UInt32').write() + Integer(partition['byte_offset'], 'UInt64').write()

        total_part_length = Integer(16 + 9 + 4 + len(ret), 'UInt32').write()

        self.pos = self.fdesc.tell()
        self.length = len(ret) + 4
        self.fdesc.write(self.key + self.ber_encode_length(self.length, bytes_num=8).decode('hex_codec') + ret + total_part_length)
        return


