#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Helper module with utility classes for MXF parsing. """

class InterchangeObject(object):
    """ Base class for all MXF objects.

    Provides a couple of utility functions in order to help parsing of MXF KLVs.
    Defines a read method that should be implemented by derived classes in order
    to load the data in a python form and a write method that should be able to
    return the data to its binary form.

    The class takes a File like object in order to perform its operations and
    modifies its cursor position.
    """

    def __init__(self, fdesc, debug=False):
        self.length = 0
        self.debug = debug
        self.data = None

        self.fdesc = fdesc
        self.key, self.length, self.bytes_num = \
            InterchangeObject.get_key_length(fdesc, decoded=False)

        # Set cursor to the begining of the actual data
        self.fdesc.seek(16 + self.bytes_num, 1)

    @staticmethod
    def get_key_length(fdesc, decoded=True):
        """ Get the Key and Length for this KLV. """
        data = fdesc.read(25)
        fdesc.seek(-25, 1)

        length, bytes_num = InterchangeObject.ber_decode_length_details(data[16:25])
        if decoded:
            return data[0:16].encode('hex_codec'), length, bytes_num
        else:
            return data[0:16], length, bytes_num

    @staticmethod
    def get_key(fdesc, decoded=True):
        """ Get the Key for this KLV."""
        return InterchangeObject.get_key_length(fdesc, decoded)[0]

    @staticmethod
    def ber_decode_length_details(size_string, bytes_num=None):
        """ Decode BER encoded length.

        @return: a tuple containing the decoded length and the amount of bytes
        consumed to decode.
        """
        consumed_bytes = 0

        if bytes_num:
            size_string = size_string[0:bytes_num]
            consumed_bytes = bytes_num
        else:
            size = ord(size_string[0])
            if size & 0x80:
                bytes_num = size & 0x7f
                size_string = size_string[1:1+bytes_num].rjust(bytes_num, '\x00')
                if bytes_num > 8:
                    raise ValueError('bytes cannot be > 8')
                consumed_bytes = bytes_num + 1
            else:
                size_string = size_string[0]
                consumed_bytes = 1

        size = 0
        for char in size_string:
            size = size << 8 | ord(char)

        return size, consumed_bytes

    @staticmethod
    def ber_decode_length(size_string, bytes_num=None):
        """ Decode BER encoded length.

        @return: the decoded length.
        """
        return InterchangeObject.ber_decode_length_details(size_string, bytes_num)[0]

    @staticmethod
    def ber_encode_length(length, bytes_num=None, prefix=True):
        """ Encode length with BER encoding.

        @length: length value to encode
        @bytes: number of bytes to encode the data on.
        @prefix: wether to add the bytes count prefix.
        """

        ret = "%x" % length

        if bytes_num:
            if bytes_num > 8:
                raise ValueError('bytes cannot be > 8')
        else:
            bytes_num = (len(ret) + 1)/ 2
            if length < 128:
                return ret.rjust(2 * bytes_num, '0')

        if prefix:
            return "%d%s" % (80 + bytes_num, ret.rjust(2 * bytes_num, '0'))
        else:
            return ret.rjust(2 * bytes_num, '0')

    def read(self):
        """ Loads KLV. """
        raise Exception('To be implemented in derived class')

    def write(self):
        """ Dumps KLV. """
        raise Exception('To be implemented in derived class')

    def __str__(self):
        return '<InterchangeObject "if you see this, it is a bug">'

