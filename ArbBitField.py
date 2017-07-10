#! /usr/bin/env python
# encoding: utf-8
"""
    ArbBitField implements a class for handling bitfields as text.
    Say you have a serial hardware device with dozens, or hundreds of individual
    bitfields of various widths, each controlling or indicating some function of the hardware.
    A JTAG interface to a JESD-204 DAC, for example. Manipulating all those
    bitfields can be quite error-prone since they might only randomly line up
    on nibble (4 bit) boundaries. ArbBitField provides
        Easy ways to define, modify, and display the fields.
        set_bool and get_bool methods to easily read from and write to the hardware.
        Options to reverse the bits within a field and/or the fields in the sequence
            during input and output.
    Key to the ArbBitField class is the format string. The format string defines
    the widths of the individual bit fields.
    Example using 4 fields, each 3 bits wide:
        >>> foo = ArbBitField.ArbBitField('3333')
        >>> foo
        ArbBitField('3333','0000')
        >>> str(foo)
        '000 000 000 000'
        >>> foo[1:3] = '35'
        str(foo)
        '000 011 101 000'
        >>> foo.bool()
        [False, False, False, False, True, True, True, False, True, False, False, False]
        >>> foo.set_bool([False,True,False]*4)
        >>> foo
        ArbBitField('4444','2222')
        >>> foo.value
        '2222'
    Fields can be different and any width from 1 to 36 bits wide.
    Zero width makes no sense, so is illegal.
    Though widths of 5 are legal, it's usually easier to read in 4 bit nibbles,
        e.g. if you specify a 5 bit width as '24' and set it to all 1s, it reads '1F'.
        if you specify the width as '5', then all 1s reads 'V' which is (31-10)
        characters after 'A' - not so useful.
"""

import copy

class ArbBitField(object):
    """ Arbitrary bit field representation: class string of chars organized by a format line.
    The format line indicates the widths of each of the field that makes up the instance.
    Default ordering left-to-right is MSB to LSB.
    """
    def __init__(self, fmt, val=None):
        """ The only required arg is the widths of the fields: the format.
            Characters in the format indicate how many bits to group together...
            Essentially, the base of the field.
            Legal value characters are 1..9, A..V (case insensitive)
            Legal format characters are 1..5
            NB: 16 bits is represented by 'G', not 'H'.
            Slices are partially supported (field-wise) but not the slice step
        """
        assert not '0' in fmt       # zero-length field is probably a mistake
        ArbBitField.legalValChars = ['%d'%x for x in range(10)]
        ArbBitField.legalValChars += ['%s'%chr(x+ord('A')) for x in range(16)]
        ArbBitField.legalFmtChars = ['%d'%x for x in range(1, 6)]
        self.fmt = ''.join([x for x in fmt.upper() if x in ArbBitField.legalFmtChars])
        self.val = self._clean_val_(val)

    def _clean_val_(self, val):
        """ returns a text str of legal charss in val that is the same length as fmt
        """
        if val is None:
            val = ''
        else:
            val = ''.join([x for x in val.upper() if x in ArbBitField.legalValChars])
        val = val[:len(self.fmt)]                       # truncate to fmt length
        val = val + '0'*(len(self.fmt)-len(val))     # pad the val out to the len of fmt
        return val

    def set_val(self, val):
        """ property setter
        """
        self.val = self._clean_val_(val)

    def get_val(self):
        """ property getter
        """
        return self.val

    value = property(get_val, set_val)

    @staticmethod
    def _field_to_int_(field):
        """ field MUST be 1 digit or upper case char. Internal use.
        """
        assert len(field) == 1
        if field in ''.join(['%d'%x for x in range(10)]):
            count = int(field)
        else:
            count = 10 + ord(field) - ord('A')
        return count

    @staticmethod
    def _to_int_(field):
        """ support lists but still return a single int if that's what's passed
            field may be a slice. Internal use.
        """
        if len(field) == 1:
            ret = ArbBitField._field_to_int_(field)
        else:
            ret = [ArbBitField._field_to_int_(x) for x in field]
        return ret

    @staticmethod
    def _to_char_(val):
        """ v is str of binary such as "00101" which returns "5". Internal Use.
        """
        vint = sum([(1 << bit_n) if val_c == '1' else 0 for bit_n, val_c in enumerate(val[::-1])])
        offset = ord('A')-10 if vint > 9 else ord('0')
        tmp = chr(vint+offset)
        if ArbBitField.debug:
            print '-- debug _to_char_("%s")  vint %d, offset %d, char %s'%(val, vint, offset, tmp)
            if vint > 36:
                print 'vint', vint
                assert False
        return tmp

    @staticmethod
    def _to_bin_(val_c, fmt_c, rev_bits=False):
        """ Single char conversion for internal use.
            e.g. '5' in format '6' is '000101' (padded to fmt_c size)
        """
        assert len(val_c) == 1
        assert len(fmt_c) == 1
        count = ArbBitField._to_int_(fmt_c)
        # print 'f is %r  count is %r'%(f,count)
        tmp = ArbBitField._to_int_(val_c)
        if rev_bits:                                            # reverse is LSB to MSB
            val_ret = ''.join(str(1 & tmp >> bit_n) for bit_n in range(count))
        else:                                                   # normal is MSB to LSB
            val_ret = ''.join(str(1 & tmp >> bit_n) for bit_n in range(count)[::-1])
        if ArbBitField.debug:
            print '-- _to_bin_("%s","%s",%r)'%(val_c, fmt_c, rev_bits),
            print 'count=%d, tmp=%r, val_c=%s'%(count, tmp, val_ret)
        return val_ret

    def __str__(self):
        """ Returns the value bits as 1s and 0s, grouped with space chars,
            e.g. zero in '34' format is '000 0000'
        """
        assert len(self.val) == len(self.fmt)   # depends on fmt and val being the same length.
        return ' '.join([self._to_bin_(*vftup) for vftup in zip(self.val, self.fmt)])

    def __repr__(self):
        """ Return str that eval can use to re-create the object.
        """
        return "ArbBitField('"+self.fmt+"','"+self.val+"')"

    def __add__(self, rhs):
        """ Concatenates two arb bit objects with all format and val.
        """
        ret = copy.copy(self)
        ret.fmt = ret.fmt + rhs.fmt
        ret.val = ret.val + rhs.val
        return ret

    def __getitem__(self, key):
        return ArbBitField._to_int_(self.val[key])

    def __setitem__(self, key, val_c):
        tmp = bytearray(self.val)
        assert len(tmp[key]) == len(val_c)
        tmp[key] = val_c
        self.val = str(tmp)

    def __len__(self):
        return len(self.fmt)

    def bool(self, rev_bits=False, rev_fields=False):
        """ returns a list of bools; Options to reverse bit-wise and field-wise.
            Normal order is left to right fields and MSB to LSB bits
        """
        if rev_fields:
            tmp_fmt, tmp_val = self.fmt[::-1], self.val[::-1]
        else:
            tmp_fmt, tmp_val = self.fmt[::], self.val[::]
        ret = []
        for fmt_idx, fmt_c in enumerate(tmp_fmt):
            count = ArbBitField._to_int_(fmt_c)
            if rev_bits:                 # reverse is LSB to MSB
                ret += [bool(1 & ArbBitField._to_int_(tmp_val[fmt_idx]) >> c) for c in range(count)]
            else:                       # normal is MSB to LSB
                ret += [bool(1 & ArbBitField._to_int_(tmp_val[fmt_idx]) >> c)
                        for c in range(count)[::-1]]
        return ret


    def set_bool(self, b_lst, rev_bits=False, rev_fields=False):
        """ sets val from a list of bools (read from the hardware, e.g.)
            Normal input order is left to right fields and MSB to LSB bits
        """
        if rev_fields:
            tmp_fmt = self.fmt[::-1]
        else:
            tmp_fmt = self.fmt[::]
        vstr = ''
        tmp_val = ['%s'%('1' if x else '0') for x in b_lst]   # convert bools to chars, if needed
        offset = 0
        for fmt_c in tmp_fmt:
            count = ArbBitField._to_int_(fmt_c)
            if rev_bits:
                vstr = vstr + ArbBitField._to_char_(tmp_val[offset:offset+count][::-1])
            else:
                vstr = vstr + ArbBitField._to_char_(tmp_val[offset:offset+count])
            offset += count
            if ArbBitField.debug:
                print '-- debug set_bool("%s")'%(tmp_val), count, vstr, offset
        self.val = vstr[::-1] if rev_fields else vstr

ArbBitField.debug = False

def bool_to_str(b_lst, zero_val=' '):
    """  Handy formatter from list of bools to text
    """
    return ''.join(['%s'%('1' if b_val else zero_val) for b_val in b_lst])

if __name__ == '__main__':
    print '*'*72
    print '*'*30, 'Begin Test', '*'*30
    print '*'*72
    X = ArbBitField('34', '31')
    Y = ArbBitField('55', '5b')
    Z = X+Y

    print 'X %30s'%X, '%r'%X
    print 'Y %30s'%Y, '%r'%Y
    print 'Z %30s'%Z, '%r'%Z
    print 'Z[1:3] %25s'%Z[1:3], '%r'%Z
    Z[1:3] = '24'
    print 'put 24 inthe middle of Z:'
    print 'Z %30s'%Z, repr(Z)

    print 'Z in decimal:', ' '.join(['%d'%Z[i] for i in range(len(Z))])
    print '\nY %30s'%Y, '%r'%Y


    print bool_to_str(Y.bool())
    print bool_to_str(Y.bool(rev_bits=True)), 'Y rev_bits'
    print bool_to_str(Y.bool(rev_fields=True)), 'Y rev_fields'
    print bool_to_str(Y.bool(rev_fields=True, rev_bits=True)), 'Y both'

    T = ArbBitField('34', '3b')
    T_SET = [False, False, True, True, True, False, True,]
    print ''.join(['%s'%('1' if i else '0') for i in T_SET]), 'T_SET'
    T.set_bool(T_SET)
    print 'T %30s'%T, '%r'%T
    T.set_bool(T_SET, rev_bits=True)
    print 'T %30s'%T, '%r'%T, 'bits'
    T.set_bool(T_SET, rev_fields=True)
    print 'T %30s'%T, '%r'%T, 'fields'
    T.set_bool(T_SET, rev_fields=True, rev_bits=True)
    print 'T %30s'%T, '%r'%T, 'both'
    T.set_bool(T_SET)
    print 'T %30s'%T, '%r'%T, 'none'

    ArbBitField.debug = False
    print '-'*30, ' test done', '-'*30
