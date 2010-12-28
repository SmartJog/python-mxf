# -*- coding: utf-8 -*-
# FIXME: implement more specialized operational pattern parser.

""" MXF Parser. """

import re
from sjmxf.common import InterchangeObject
from sjmxf.s377m import MXFPartition, MXFDataSet, MXFPreface, MXFPrimer, KLVFill, KLVDarkComponent, RandomIndexMetadata, S377MException
from sjmxf.avid import AvidObjectDirectory, AvidAAFDefinition, AvidMetadataPreface, AvidMXFDataSet
from sjmxf.rp210types import AvidOffset

SMPTE_PARTITION_PACK_LABEL = '060e2b34020501010d010201'

def mxf_kind(filename):
    """ Lookup the MXF data start position and returns appropriate parser. """

    mxf = MXFParser(filename)
    mxf.open()

    # SMTPE 377M: Header Partition Pack, first thing in a MXF file
    header_partition_pack = MXFPartition(mxf.fd)
    try:
        header_partition_pack.read()
    except S377MException, error:
        print error

    op = header_partition_pack.data['operational_pattern'].encode('hex_codec')
    for op_pattern, parser in PARSERS.items():
        if re.match(op_pattern, op):
            print "Selecting", str(parser)
            return parser(filename, debug=True)

    # This is an error
    return None


class MXFParser(object):

    def __init__(self, filename, debug=False):
        self.filename = filename
        self.fd = None
        self.data = {
            'header': {
                'partition': None,
                'primer': None,
                'preface': None,
                'klvs': [],
            },
            'body': {
                'partition': None
            },
            'footer': {
                'partition': None,
                'random_index_pack': None,
                'klvs': [],
            },
        }
        self.debug = debug

    def open(self):
        # SMTPE 377M: ability to skip over RunIn sequence
        self.fd = open(self.filename, 'r')
        data = self.fd.read(65536)
        idx = data.find(SMPTE_PARTITION_PACK_LABEL.decode('hex_codec'))
        if idx == -1:
            raise Exception('Not a valid SMTPE 377m MXF file.')

        # Real MXF data position
        self.fd.seek(idx)

    def close(self):
        self.fd.close()

    def read(self):
        if not self.fd:
            self.open()

        self.header_partition_parse()
        self.header_metadata_parse()

        ### Print out
        if self.debug:
            self.header_dump()
            self.primer_statistics()

        # Continue parsing
        self.body_parse()
        self.footer_partition_parse()
        self.footer_extra_parse()
        return self.data

    def header_partition_parse(self):
        """ Parse MXF header partition. """

        # SMTPE 377M: Header Partition Pack, first thing in a MXF file
        header_partition_pack = MXFPartition(self.fd)
        try:
            header_partition_pack.read()
        except S377MException, error:
            print error
        self.data['header']['partition'] = header_partition_pack

        # SMPTE 377M: klv fill behind Header Partition is not counted in HeaderByteCount
        key = InterchangeObject.get_key(self.fd)
        if key in ('060e2b34010101010201021001000000', \
            '060e2b34010101010301021001000000'):
            # KLV Fill item
            klv = KLVFill(self.fd)
            klv.read()
            self.data['header']['klvs'].append(klv)

    def header_metadata_parse(self):
        raise Exception('To be implemented in specific Operational Pattern Parser')

    def body_parse(self):

        # Read until Footer Partition Pack key
        i = 0
        key = InterchangeObject.get_key(self.fd)
        while not key.startswith('060e2b34020501010d01020101040400'):

            klv = KLVDarkComponent(self.fd)
            klv.read()
            i += 1
            key = InterchangeObject.get_key(self.fd)
            print klv

        print "Skipped", i, "KLVs"

    def footer_partition_parse(self):
        """ Parse MXF footer partition. """

        # SMTPE 377M: Footer Partition Pack
        footer_partition_pack = MXFPartition(self.fd)
        footer_partition_pack.read()
        self.data['footer']['partition'] = footer_partition_pack

        key = InterchangeObject.get_key(self.fd)
        if key in ('060e2b34010101010201021001000000',
            '060e2b34010101010301021001000000'):
            # KLV Fill item
            klv = KLVFill(self.fd)
            klv.read()
            self.data['footer']['klvs'].append(klv)

    def footer_extra_parse(self):

        # Read file's end
        key = InterchangeObject.get_key(self.fd)
        while key != '060e2b34020501010d01020101110100':

            if key in (
             '060e2b34010101010201021001000000',
             '060e2b34010101010301021001000000'
            ):
                # KLV Fill item
                klv = KLVFill(self.fd)
                klv.read()

            else:
                # 060e2b34025301010d01020101100100 -> Index Table Segment
                klv = KLVDarkComponent(self.fd)
                klv.read()
                print klv

            self.data['footer']['klvs'].append(klv)

            key = InterchangeObject.get_key(self.fd)

        # SMTPE 377M: Random Index Pack (optional after Footer Partition)
        if key != '060e2b34020501010d01020101110100':
            raise Exception('Invalid RandomIndexMetadata key: %s' % InterchangeObject.get_key(self.fd))
        random_index_pack = RandomIndexMetadata(self.fd)
        random_index_pack.read()
        self.data['footer']['klvs'].append(random_index_pack)
        self.data['footer']['random_index_pack'] = random_index_pack

    def primer_statistics(self):
        # Primer Pack stats
        smpte377_transcodings = self.data['header']['primer'].data.values()
        smpte377_transcodings.sort()
        custom_encoding = 0
        for item in smpte377_transcodings:
            if not item.startswith('060e2b34'.decode('hex_codec')):
                custom_encoding += 1

        print "Custom encodings:", custom_encoding

    def header_dump(self):
        header_klvs_hash = {}

        for klv in self.data['header']['klvs']:
            if isinstance(klv, MXFDataSet):
                if '\x3c\x0a' in klv.data:
                    header_klvs_hash[klv.data['\x3c\x0a'].read()] = {'klv': klv, 'used': False}

        print "KLVs left:", len([klv for klv in header_klvs_hash.values() if not klv['used']])
        print "<=============================================================>"

        if 'avid_preface' in self.data['header']:
            header_klvs_hash = self.data['header']['avid_preface'].human_readable(header_klvs_hash)
        else:
            header_klvs_hash = self.data['header']['preface'].human_readable(header_klvs_hash)

        print ""
        print "KLVs left:", len([klv for klv in header_klvs_hash.values() if not klv['used']])
        print "<=============================================================>"
        self.data['header']['partition'].human_readable()

        # Below are some dark metadata
        print "<=============================================================>"
        for _, klv in header_klvs_hash.items():
            if not klv['used']:
                print klv
                klv['klv'].human_readable(header_klvs_hash, indent=1)


class AvidParser(MXFParser):


    def header_metadata_parse(self):

        dark = 0

        avid_metadata_preface = None
        header_metadata_preface = None
        header_end = self.fd.tell() + self.data['header']['partition'].data['header_byte_count']

        while self.fd.tell() < header_end:
            fd = self.fd
            key = InterchangeObject.get_key(self.fd)

            if key in ('060e2b34010101010201021001000000', \
                '060e2b34010101010301021001000000'):
                # KLV Fill item
                klv = KLVFill(fd)
                klv.read()

            elif key == '060e2b34020501010d01020101050100':
                # SMTPE 377M: Header Metadata (Primer Pack)
                #if not isinstance(header_klvs[-1], KLVFill) and \
                #    not isinstance(header_klvs[-1], MXFPartition):
                #    raise Exception('Error: MXFPrimer not located after Header Partition Pack')
                header_metadata_primer_pack = MXFPrimer(fd, debug=True)
                header_metadata_primer_pack.read()
                #print header_metadata_primer_pack
                klv = header_metadata_primer_pack
                #continue

            elif key == '060e2b34025301010d01010101012f00':
                # SMTPE 377M: Header Metadata (Preface)
                #if not isinstance(header_klvs[-1], KLVFill) and \
                #    not isinstance(header_klvs[-1], MXFPrimer):
                #    raise Exception('Error: MXFPrimer not located after Header Partition Pack')
                header_metadata_preface = MXFPreface(fd, header_metadata_primer_pack)
                header_metadata_preface.read()
                klv = header_metadata_preface

            elif key == '8053080036210804b3b398a51c9011d4':
                # Avid ???
                avid_metadata_preface = AvidMetadataPreface(fd, header_metadata_primer_pack)
                avid_metadata_preface.read()
                klv = avid_metadata_preface

            elif key in (
             # 416 chunk (dark)
             '060e2b34025301010d01010102010000',
             '060e2b34025301010d01010102020000',
             '060e2b34025301010d01010102040000',
             '060e2b34025301010d01010102050000',
             '060e2b34025301010d01010102060000',
             '060e2b34025301010d01010102070000',
             '060e2b34025301010d01010102080000',
             '060e2b34025301010d01010102090000',
             '060e2b34025301010d010101020a0000',
             '060e2b34025301010d010101020b0000',
             '060e2b34025301010d010101020c0000',
             '060e2b34025301010d010101020d0000',
             '060e2b34025301010d010101020e0000',

             '060e2b34025301010d01010102200000',
             '060e2b34025301010d01010102210000',
             '060e2b34025301010d01010102220000', # Dark Dictionary ?

             '060e2b34025301010d01010102250000',

             # 119 chunk: Metadata of type ???
             '060e2b34025301010d01010101011b00', # Dark Simple Type Definition
             '060e2b34025301010d01010101011f00', # Dark Derived Type Definition
             '060e2b34025301010d01010101012000', # Dark Concent Type Definition
             '060e2b34025301010d01010101012200', # Dark Links to Data/Container/Codecs definitions
            ):
                # Avid DataSet
                klv = AvidAAFDefinition(fd, header_metadata_primer_pack)
                klv.read()

            elif key in (
             # essence descriptions (130~180)
             # SMPTE 377M: Strutural Metadata Sets
             '060e2b34025301010d01010101010900', # Filler

             '060e2b34025301010d01010101010f00', # Sequence

             '060e2b34025301010d01010101011100', # Source Clip
             '060e2b34025301010d01010101011400', # Timecode Component

             '060e2b34025301010d01010101011800', # ContentStorage

             '060e2b34025301010d01010101012e00', # AVID

             '060e2b34025301010d01010101013700', # Source Package (File, Physical)

             '060e2b34025301010d01010101013b00', # Timeline Track

             '060e2b34025301010d01010101014200', # GenericSoundEssenceDescriptor
             '060e2b34025301010d01010101014400', # MultipleDescriptor
             '060e2b34025301010d01010101014800', # WaveAudioDescriptor
             ):
                klv = MXFDataSet(fd, header_metadata_primer_pack)
                klv.read()

            elif key in (
             '060e2b34025301010d01010101012800', # CDCI Essence Descriptor

             # avid does not use standard 10 bytes ProductVersion
             '060e2b34025301010d01010101013000', # Identification

             '060e2b34025301010d01010101013600', # Material Package
             '060e2b34025301010d01010101013f00', # AVID
            ):
                klv = AvidMXFDataSet(fd, header_metadata_primer_pack)
                klv.read()

            elif key == '9613b38a87348746f10296f056e04d2a':
                # Avid ObjectDirectory
                klv = AvidObjectDirectory(fd, True)
                klv.read()

            else:
                klv = KLVDarkComponent(fd)
                klv.read()
                dark += 1

            self.data['header']['klvs'].append(klv)

        ### End of the parsing loop 1

        if self.debug:
            print "Loaded ", len(self.data['header']['klvs']), "KLVs", self.fd.tell()
            print "Skipped", dark, "dark KLVs"

        self.data['header'].update({
            'primer': header_metadata_primer_pack,
            'preface': header_metadata_preface,
            'avid_preface': avid_metadata_preface,
        })
        return

    def write(self):

        fd = open(self.filename, 'w')

        for part in ('header', 'body', 'footer'):
            if not self.data[part]['partition']:
                print "part", part, "is empty"
                continue

            print "Writing part:", part
            value = self.data[part]['partition']
            value.fdesc = fd
            value.write()

            value = self.data[part]['klvs']
            object_directory = []
            for item in value:
                item.fdesc = fd

                # Build AvidObjectDirectory update
                if hasattr(item, 'get_element'):
                    object_directory.append((item.get_element('guid').read(), item.pos, 0))

                if isinstance(item, AvidMetadataPreface):
                    avid_preface = item

                if isinstance(item, AvidObjectDirectory):
                    item.data = object_directory
                    avid_objdir = item

                item.write()

        # Update Avid Metadata Preface
        fd.seek(avid_preface.pos)
        avid_preface.set_element('object_directory',
           AvidOffset(AvidOffset(int(avid_objdir.pos)).write())
        )
        avid_preface.write()

        # Update Header
        fd.seek(0)
        self.data['header']['partition'].data['footer_partition'] = self.data['footer']['partition'].pos
#        self.data['header']['partition'].data['header_byte_count'] = self.data['footer']['partition'].pos - (self.data['header']['partition'].length + 16 + 9)
#
#        if isinstance(self.data['header']['klvs'][0], KLVFill):
#            print "First KLVFill", self.data['header']['klvs'][0].length
#            self.data['header']['partition'].data['header_byte_count'] -= (self.data['header']['klvs'][0].length + 16 + 9)

        self.data['header']['partition'].data['header_byte_count'] = sum(16 + 9 + klv.length for klv in self.data['header']['klvs'][1:])
        self.data['header']['partition'].write()

        # Update Footer
        fd.seek(self.data['footer']['partition'].pos)
        self.data['footer']['partition'].data['footer_partition'] = self.data['footer']['partition'].pos
        self.data['footer']['partition'].data['this_partition'] = self.data['footer']['partition'].pos
        self.data['footer']['partition'].write()

        # Update Random Index Pack
        # No need to seek after footer write
        self.data['footer']['random_index_pack'].data['partition'] = [
            {'body_sid': 0, 'byte_offset': self.data['header']['partition'].pos},
            {'body_sid': 1, 'byte_offset': self.data['footer']['partition'].pos},
        ]
        self.data['footer']['random_index_pack'].write()

        if self.debug:
            print "Sum of header klv length:", sum(klv.length for klv in self.data['header']['klvs']) + self.data['header']['partition'].length
            print "Footer position:", self.data['footer']['partition'].pos

        fd.truncate(fd.tell())


class OP1aParser(MXFParser):

    def header_metadata_parse(self):

        dark = 0
        header_metadata_preface = None
        header_end = self.fd.tell() + self.data['header']['partition'].data['header_byte_count']

        while self.fd.tell() <= header_end:
            fd = self.fd
            key = InterchangeObject.get_key(self.fd)

            if key in ('060e2b34010101010201021001000000', \
                '060e2b34010101010301021001000000'):
                # KLV Fill item
                klv = KLVFill(fd)
                klv.read()

            elif key == '060e2b34020501010d01020101050100':
                # SMTPE 377M: Header Metadata (Primer Pack)
                #if not isinstance(header_klvs[-1], KLVFill) and \
                #    not isinstance(header_klvs[-1], MXFPartition):
                #    raise Exception('Error: MXFPrimer not located after Header Partition Pack')
                header_metadata_primer_pack = MXFPrimer(fd, debug=True)
                header_metadata_primer_pack.read()
                print header_metadata_primer_pack
                klv = header_metadata_primer_pack

            elif key == '060e2b34025301010d01010101012f00':
                # SMTPE 377M: Header Metadata (Preface)
                #if not isinstance(header_klvs[-1], KLVFill) and \
                #    not isinstance(header_klvs[-1], MXFPrimer):
                #    raise Exception('Error: MXFPrimer not located after Header Partition Pack')
                header_metadata_preface = MXFPreface(fd, header_metadata_primer_pack)
                header_metadata_preface.read()
                klv = header_metadata_preface

            elif key in (
             # essence descriptions (130~180)
             # SMPTE 377M: Strutural Metadata Sets
             '060e2b34025301010d01010101010900', # Filler

             '060e2b34025301010d01010101010f00', # Sequence

             '060e2b34025301010d01010101011100', # Source Clip
             '060e2b34025301010d01010101011400', # Timecode Component

             '060e2b34025301010d01010101011800', # ContentStorage

             '060e2b34025301010d01010101013000', # Identification
             '060e2b34025301010d01010101013700', # Source Package (File, Physical)
             '060e2b34025301010d01010101013600', # Material Package
             '060e2b34025301010d01010101013b00', # Timeline Track

             '060e2b34025301010d01010101012300', # EssenceContainerData
             '060e2b34025301010d01010101012800', # CDCI Essence Descriptor
             '060e2b34025301010d01010101014200', # GenericSoundEssenceDescriptor
             '060e2b34025301010d01010101014400', # MultipleDescriptor
             '060e2b34025301010d01010101014700', # AES3PCMDescriptor
             '060e2b34025301010d01010101014800', # WaveAudioDescriptor
             '060e2b34025301010d01010101015100', # MPEG2VideoDescriptor
             ):
                klv = MXFDataSet(fd, header_metadata_primer_pack)
                klv.read()

            else:
                klv = KLVDarkComponent(fd)
                klv.read()
                dark += 1

            self.data['header']['klvs'].append(klv)

        ### End of the parsing loop 1

        if self.debug:
            print "Loaded ", len(self.data['header']['klvs']), "KLVs", self.fd.tell()
            print "Skipped", dark, "dark KLVs"

        self.data['header'].update({
            'primer': header_metadata_primer_pack,
            'preface': header_metadata_preface,
        })
        return


PARSERS = {
    '060e2b34040101030e04020110000000': AvidParser,
    '060e2b34040101010d0102010101..00': OP1aParser,
}

