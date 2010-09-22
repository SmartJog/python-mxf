#!/usr/bin/python
# -*- coding: utf-8 -*-

VERSION = "@VERSION@"

from mxf.parser import MXFParser
import optparse

def main(filename):
    """ Parse MXF file. """

    parser = MXFParser(filename)
    structure = parser.read()
    parser.close()

    # Primer Pack stats
    smpte377_transcodings = structure['header']['primer'].data.values()
    smpte377_transcodings.sort()
    custom_encoding = 0
    for item in smpte377_transcodings:
        if not item.startswith('060e2b34'.decode('hex_codec')):
            custom_encoding += 1

    print "Custom encodings:", custom_encoding

    return


if __name__ == "__main__":
    PARSER = optparse.OptionParser(
        version="%prog " + VERSION,
        usage="%prog FILE",
        option_list=[],
    )
    (_, ARGS) = PARSER.parse_args()

    if len(ARGS) < 1:
        PARSER.print_help()
    else:
        main(ARGS[0])

