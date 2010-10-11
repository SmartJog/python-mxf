#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Helper module with utility classes for MXF parsing. """

from collections import MutableMapping
from operator import eq as _eq
from itertools import imap as _imap

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

    _instance = None

    def __init__(self, cls):
        # Check whether we already have an instance
        if Singleton._instance is None:
            # Create and remember instance
            Singleton._instance = cls()

    def __getattr__(self, attribute):
        """ Delegate access to implementation.

        @param self The object pointer.
        @param attr Attribute wanted.
        @return Attribute
        """
        return getattr(self._instance, attribute)

    def __setattr__(self, attribute, value):
        """ Delegate access to implementation.

        @param self The object pointer.
        @param attr Attribute wanted.
        @param value Vaule to be set.
        @return Result of operation.
        """
        return setattr(self._instance, attribute, value)


################################################################################
### OrderedDict
################################################################################

class OrderedDict(dict, MutableMapping):
    'Dictionary that remembers insertion order'
    # An inherited dict maps keys to values.
    # The inherited dict provides __getitem__, __len__, __contains__, and get.
    # The remaining methods are order-aware.
    # Big-O running times for all methods are the same as for regular dictionaries.

    # The internal self.__map dictionary maps keys to links in a doubly linked list.
    # The circular doubly linked list starts and ends with a sentinel element.
    # The sentinel element never gets deleted (this simplifies the algorithm).
    # Each link is stored as a list of length three:  [lprev, lnext, lkey].

    def __init__(self, *args, **kwds):
        '''Initialize an ordered dictionary.  Signature is the same as for
        regular dictionaries, but keyword arguments are not recommended
        because their insertion order is arbitrary.

        '''
        dict.__init__(self, *args, **kwds)

        if len(args) > 1:
            raise TypeError('expected at most 1 arguments, got %d' % len(args))
        try:
            self.__root
        except AttributeError:
            self.__root = root = [None, None, None]     # sentinel node
            lprev = 0
            lnext = 1
            root[lprev] = root[lnext] = root
            self.__map = {}
        self.update(*args, **kwds)

    def __setitem__(self, key, value, lprev=0, lnext=1, dict_setitem=dict.__setitem__):
        'od.__setitem__(i, y) <==> od[i]=y'
        # Setting a new item creates a new link which goes at the end of the linked
        # list, and the inherited dictionary is updated with the new key/value pair.
        if key not in self:
            root = self.__root
            last = root[lprev]
            last[lnext] = root[lprev] = self.__map[key] = [last, root, key]
        dict_setitem(self, key, value)

    def __delitem__(self, key, lprev=0, lnext=1, dict_delitem=dict.__delitem__):
        'od.__delitem__(y) <==> del od[y]'
        # Deleting an existing item uses self.__map to find the link which is
        # then removed by updating the links in the predecessor and successor nodes.
        dict_delitem(self, key)
        link = self.__map.pop(key)
        link_prev = link[lprev]
        link_next = link[lnext]
        link_prev[lnext] = link_next
        link_next[lprev] = link_prev

    def __iter__(self, lnext=1, lkey=2):

        'od.__iter__() <==> iter(od)'
        # Traverse the linked list in order.
        root = self.__root
        curr = root[lnext]
        while curr is not root:
            yield curr[lkey]
            curr = curr[lnext]

    def __reversed__(self, lprev=0, lkey=2):
        'od.__reversed__() <==> reversed(od)'
        # Traverse the linked list in reverse order.
        root = self.__root
        curr = root[lprev]
        while curr is not root:
            yield curr[lkey]
            curr = curr[lprev]

    def __reduce__(self):
        'Return state information for pickling'
        items = [[k, self[k]] for k in self]
        tmp = self.__map, self.__root
        del self.__map, self.__root
        inst_dict = vars(self).copy()
        self.__map, self.__root = tmp
        if inst_dict:
            return (self.__class__, (items,), inst_dict)
        return self.__class__, (items,)

    def clear(self):
        'od.clear() -> None.  Remove all items from od.'
        try:
            for node in self.__map.itervalues():
                del node[:]
            self.__root[:] = [self.__root, self.__root, None]
            self.__map.clear()
        except AttributeError:
            pass
        dict.clear(self)

    setdefault = MutableMapping.setdefault
    update = MutableMapping.update
    pop = MutableMapping.pop
    keys = MutableMapping.keys
    values = MutableMapping.values
    items = MutableMapping.items
    iterkeys = MutableMapping.iterkeys
    itervalues = MutableMapping.itervalues
    iteritems = MutableMapping.iteritems
    __ne__ = MutableMapping.__ne__

    def popitem(self, last=True):
        '''od.popitem() -> (k, v), return and remove a (key, value) pair.
        Pairs are returned in LIFO order if last is true or FIFO order if false.

        '''
        if not self:
            raise KeyError('dictionary is empty')
        key = next(reversed(self) if last else iter(self))
        value = self.pop(key)
        return key, value

    def __repr__(self):
        'od.__repr__() <==> repr(od)'
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, self.items())

    def copy(self):
        'od.copy() -> a shallow copy of od'
        return self.__class__(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        '''OD.fromkeys(S[, v]) -> New ordered dictionary with keys from S
        and values equal to v (which defaults to None).

        '''
        dict_inst = cls()
        for key in iterable:
            dict_inst[key] = value
        return dict_inst

    def __eq__(self, other):
        '''od.__eq__(y) <==> od==y.  Comparison to another OD is order-sensitive
        while comparison to a regular mapping is order-insensitive.

        '''
        if isinstance(other, OrderedDict):
            return len(self)==len(other) and \
                   all(_imap(_eq, self.iteritems(), other.iteritems()))
        return dict.__eq__(self, other)

    def __del__(self):
        self.clear()                # eliminate cyclical references

