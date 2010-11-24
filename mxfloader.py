#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Small utility to parse MXF files and dump structure on standard output. """

VERSION = "@VERSION@"

from mxf.parser import mxf_kind

import optparse

def main(filename):
    """ Parse MXF file. """

    parser = mxf_kind(filename)
    structure = parser.read()
    parser.close()
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

