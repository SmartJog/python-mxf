# -*- coding: utf-8 -*-
# FIXME: implement more specialized operational pattern parser.

""" MXF Parser. """

from mxf.common import InterchangeObject
from mxf.s377m import MXFPartition, MXFDataSet, MXFPreface, MXFPrimer, KLVFill, KLVDarkComponent, RandomIndexMetadata
from mxf.avid import AvidObjectDirectory, AvidAAFDefinition, AvidMetadataPreface, AvidMXFDataSet

SMPTE_PARTITION_PACK_LABEL = '060e2b34020501010d010201'

# FIXME: this is actually an avid OP parser
class MXFParser(object):

    def __init__(self, filename):
        self.filename = filename
        self.fd = None

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

        # SMTPE 377M: Header Partition Pack, first thing in a MXF file
        header_partition_pack = MXFPartition(self.fd)
        header_partition_pack.read()

        header_klvs = []
        header_klvs_hash = {}
        header_end = self.fd.tell() + InterchangeObject.ber_decode_length(header_partition_pack.data['header_byte_count'], len(header_partition_pack.data['header_byte_count']))

        header_metadata_preface = None
        avid_metadata_preface = None
        dark = 0

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
                continue

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
                continue

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

            header_klvs.append(klv)
            if isinstance(klv, MXFDataSet):
                if 'guid' in klv.data['by_format_ul']:
                    header_klvs_hash[klv.i_guid.read()] = klv

        ### End of the parsing loop 1

        print "Loaded ", len(header_klvs), "KLVs", self.fd.tell()
        print "Referenced ", len(header_klvs_hash), "KLVs"
        print "Skipped", dark, "dark KLVs"

        i = 0
        while not InterchangeObject.get_key(self.fd).startswith('060e2b34020501010d01020101040400'):
            klv = KLVDarkComponent(fd)
            klv.read()
            i += 1

        print "Skipped", i, "KLVs"

        ### End of the parsing loop 2

        # SMTPE 377M: Footer Partition Pack
        if InterchangeObject.get_key(self.fd) != '060e2b34020501010d01020101040400':
            raise Exception('Invalid Footer Partition Pack key: %s' % InterchangeObject.get_key(self.fd))

        footer_partition_pack = MXFPartition(fd)
        footer_partition_pack.read()
        print footer_partition_pack

        if InterchangeObject.get_key(self.fd) in \
            ('060e2b34010101010201021001000000', '060e2b34010101010301021001000000'):
            # KLV Fill item
            klv = KLVFill(fd)
            klv.read()
            print ">>> Found KLVFill"
            #print klv


        # SMTPE 377M: Random Index Pack (optional after Footer Partition)
        if InterchangeObject.get_key(self.fd) != '060e2b34020501010d01020101110100':
            raise Exception('Invalid RandomIndexMetadata key: %s' % InterchangeObject.get_key(self.fd))
        random_index_pack = RandomIndexMetadata(fd)
        random_index_pack.read()
        print random_index_pack

        ### End of the parsing ###

        # Header Partition Pack
        # Fill (opt)
        # Primer
        # Fill (opt)
        # Avid Sets/Packs (OP avid ?)
        # Preface
        # Header Metadata
        # Avid Object Directory (OP avid ?)
        # Footer Partition Pack
        # Random Index Pack

        ### Printout

        print "KLVs left:", len(header_klvs_hash)
        print "<=============================================================>"

        if avid_metadata_preface:
            header_klvs_hash = avid_metadata_preface.human_readable(header_klvs_hash)
        else:
            header_klvs_hash = header_metadata_preface.human_readable(header_klvs_hash)

        print ""
        print "KLVs left:", len(header_klvs_hash)
        print "<=============================================================>"
        header_partition_pack.human_readable()

        # Below are some dark metadata
        print "<=============================================================>"
        for _, klv in header_klvs_hash.items():
            print klv
            klv.human_readable(header_klvs_hash, indent=1)

        return {
            'header': {
                'partition': header_partition_pack,
                'primer': header_metadata_primer_pack,
                'preface': header_metadata_preface,
                'metadata': header_klvs,
            },
            'body': {},
            'footer': {
                'partition': footer_partition_pack,
                'random_index': random_index_pack,
            }
        }

