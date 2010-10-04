# -*- coding: utf-8 -*-

""" Implements basic classes to parse Avid specific MXF objects. """

from mxf.common import InterchangeObject

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

        od_list_size = self.ber_decode_length(data[0:8], 8)
        od_item_size = self.ber_decode_length(data[8], 1)
        idx = 9

        self.data = []
        while od_list_size > len(self.data):
            self.data.append((
                data[idx:idx+16],                               # key
                self.ber_decode_length(data[idx+16:idx+24], 9), # offset
                data[idx+24],                                   # flag
            ))
            idx += od_item_size

        if self.debug:
            print "%d objects of %d bytes size in Object Directory" % (od_list_size, od_item_size)

    def human_readable(self):
        print "Object".rjust(32, ' '), "Offset".rjust(10, ' '), "Flag"
        for item in self.data:
            print item[0].encode('hex_codec'), '%10d' % item[1], item[2].encode('hex_codec')

        return


