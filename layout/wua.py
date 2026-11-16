# Read files from a ZArchive (.wua) on the device via ranged adb reads (read-only).
import subprocess, struct, sys, zstandard, os
import os
DEV=os.environ['ADB_SERIAL']   # the handheld's adb serial
PATH='/sdcard/Games/Wii U/The Legend of Zelda - Breath of the Wild (USA) (DLC) (v208).wua'
SIZE=13660330872
def rd(off,n):
    # block-aligned dd
    bs=65536; s=off//bs; e=(off+n+bs-1)//bs
    out=subprocess.run(['adb','-s',DEV,'exec-out',f'dd if="{PATH}" bs={bs} skip={s} count={e-s} 2>/dev/null'],capture_output=True,check=True).stdout
    return out[off-s*bs:off-s*bs+n]
ft=rd(SIZE-144,144)
# footer: 6 x (offset u64, size u64) sections, sha256[32], totalSize u64, version u32, magic u32  (big endian)
secs=[struct.unpack('>QQ',ft[i*16:i*16+16]) for i in range(6)]
total,ver,magic=struct.unpack('>QII',ft[128:144])
print(secs,total,hex(ver),hex(magic),file=sys.stderr)
names=['data','offrec','names','tree','metadir','metadata']
S=dict(zip(names,secs))
cache='/'.join(__file__.split('/')[:-1])+'/wua_idx.bin'
if os.path.exists(cache): blob=open(cache,'rb').read()
else:
    blob=rd(S['offrec'][0], S['tree'][0]+S['tree'][1]-S['offrec'][0]); open(cache,'wb').write(blob)
b0=S['offrec'][0]
offrec=blob[:S['offrec'][1]]; nm=blob[S['names'][0]-b0:S['names'][0]-b0+S['names'][1]]; tree=blob[S['tree'][0]-b0:S['tree'][0]-b0+S['tree'][1]]
def name(o):
    if o>=len(nm): return ""
    l=nm[o]
    if l&0x80: l=(l&0x7f)|(nm[o+1]<<7); o+=1
    return nm[o+1:o+1+l].decode()
def ent(i):
    a,b,c,d=struct.unpack('>IIII',tree[i*16:i*16+16])
    isfile=a>>31; n=name(a&0x7fffffff)
    if isfile:
        return n,True,(b|((d&0xffff)<<32)),(c|((d>>16)<<32))
    return n,False,b,c
def find(path):
    cur=ent(0)
    for p in path.split('/'):
        _,f,start,cnt=cur; assert not f
        for i in range(start,start+cnt):
            e=ent(i)
            if e[0].lower()==p.lower(): cur=e;break
        else: raise KeyError(p+' in '+str([ent(i)[0] for i in range(start,start+cnt)]))
    return cur
def ls(path):
    _,f,start,cnt=find(path) if path else ent(0)
    return [ent(i) for i in range(start,start+cnt)]
def blockinfo(bi):
    r=offrec[(bi//16)*40:(bi//16)*40+40]
    base=struct.unpack('>Q',r[:8])[0]; sizes=struct.unpack('>16H',r[8:])
    off=base+sum(s+1 for s in sizes[:bi%16]); return off,sizes[bi%16]+1
def read(path):
    _,f,off,size=find(path); assert f
    b0_=off//65536; b1=(off+size-1)//65536
    o0,_=blockinfo(b0_); o1,s1=blockinfo(b1)
    raw=rd(S['data'][0]+o0,o1+s1-o0)
    out=b''
    d=zstandard.ZstdDecompressor()
    for bi in range(b0_,b1+1):
        o,s=blockinfo(bi); c=raw[o-o0:o-o0+s]
        out+= c if s==65536 else d.decompress(c,max_output_size=65536)
    return out[off-b0_*65536:off-b0_*65536+size]
if __name__=='__main__':
    if sys.argv[1]=='ls':
        for e in ls(sys.argv[2] if len(sys.argv)>2 else ''): print(e)
    else:
        open(sys.argv[3],'wb').write(read(sys.argv[2]))
