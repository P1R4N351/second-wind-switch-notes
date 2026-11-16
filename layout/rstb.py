import struct,zlib,oead
class Rstb:
    def __init__(s,raw):
        s.comp=raw[:4]==b'Yaz0'; d=bytes(oead.yaz0.decompress(raw)) if s.comp else raw
        s.d=bytearray(d); assert d[:4]==b'RSTB'
        s.ncrc,s.nname=struct.unpack_from('<II',d,4)
        s.crc={struct.unpack_from('<I',d,12+8*i)[0]:12+8*i+4 for i in range(s.ncrc)}
        s.names={}
        o=12+8*s.ncrc
        for i in range(s.nname): s.names[d[o:o+128].split(b'\0')[0].decode()]=o+128; o+=132
        assert o==len(d)
    def off(s,name):
        if name in s.names: return s.names[name]
        return s.crc.get(zlib.crc32(name.encode()))
    def get(s,name):
        o=s.off(name); return None if o is None else struct.unpack_from('<I',s.d,o)[0]
    def set(s,name,v): struct.pack_into('<I',s.d,s.off(name),v)
    def pack(s): return bytes(oead.yaz0.compress(bytes(s.d))) if s.comp else bytes(s.d)
