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
        self.pos = fdesc.tell()
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

################################################################################
### Singleton
################################################################################

class Singleton(object):

    _instance = {}

    def __init__(self, cls, qualifier=None):

        if qualifier:
            sclass = str(cls) + qualifier
        else:
            sclass = str(cls)

        # Check whether we already have an instance
        if not sclass in Singleton._instance:
            # Create and remember instance
            Singleton._instance[sclass] = cls()

        self._sclass = sclass

    def __getattribute__(self, attribute):
        """ Delegate access to implementation.

        @param self The object pointer.
        @param attr Attribute wanted.
        @return Attribute
        """
        if attribute in ('_sclass', '_instance'):
            return object.__getattribute__(self, attribute)
        else:
            return object.__getattribute__(self._instance[self._sclass], attribute)

    def __setattr__(self, attribute, value):
        """ Delegate access to implementation.

        @param self The object pointer.
        @param attr Attribute wanted.
        @param value Vaule to be set.
        @return Result of operation.
        """
        if attribute == '_sclass':
            return object.__setattr__(self, attribute, value)
        else:
            return object.__setattr__(self._instance[self._sclass], attribute, value)


################################################################################
### OrderedDict
################################################################################

# Copyright (c) 2009 Raymond Hettinger
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
#     The above copyright notice and this permission notice shall be
#     included in all copies or substantial portions of the Software.
#
#     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#     EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
#     OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#     NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#     HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#     WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#     FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#     OTHER DEALINGS IN THE SOFTWARE.

from UserDict import DictMixin

class OrderedDict(dict, DictMixin):

    def __init__(self, *args, **kwds):
        dict.__init__(self, *args, **kwds)
        if len(args) > 1:
            raise TypeError('expected at most 1 arguments, got %d' % len(args))
        try:
            self.__end
        except AttributeError:
            self.clear()
        self.update(*args, **kwds)

    def clear(self):
        self.__end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.__map = {}                 # key --> [key, prev, next]
        dict.clear(self)

    def __setitem__(self, key, value):
        if key not in self:
            end = self.__end
            curr = end[1]
            curr[2] = end[1] = self.__map[key] = [key, curr, end]
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        _, lprev, lnext = self.__map.pop(key)
        lprev[2] = lnext
        lnext[1] = lprev

    def __iter__(self):
        end = self.__end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.__end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def popitem(self, last=True):
        if not self:
            raise KeyError('dictionary is empty')
        if last:
            key = reversed(self).next()
        else:
            key = iter(self).next()
        value = self.pop(key)
        return key, value

    def __reduce__(self):
        items = [[k, self[k]] for k in self]
        tmp = self.__map, self.__end
        del self.__map, self.__end
        inst_dict = vars(self).copy()
        self.__map, self.__end = tmp
        if inst_dict:
            return (self.__class__, (items,), inst_dict)
        return self.__class__, (items,)

    def keys(self):
        return list(self)

    setdefault = DictMixin.setdefault
    update = DictMixin.update
    pop = DictMixin.pop
    values = DictMixin.values
    items = DictMixin.items
    iterkeys = DictMixin.iterkeys
    itervalues = DictMixin.itervalues
    iteritems = DictMixin.iteritems

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, self.items())

    def copy(self):
        return self.__class__(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        d = cls()
        for key in iterable:
            d[key] = value
        return d

    def __eq__(self, other):
        if isinstance(other, OrderedDict):
            if len(self) != len(other):
                return False
            for p, q in  zip(self.items(), other.items()):
                if p != q:
                    return False
            return True
        return dict.__eq__(self, other)

    def __ne__(self, other):
        return not self == other


