import struct,sys,hashlib
def secs(b):
    bom=b[4:6]; e='>' if bom==b'\xfe\xff' else '<'
    hl,ver,fs,n=struct.unpack(e+'HIIH',b[6:18])
    out=[];o=hl
    for i in range(n):
        m=b[o:o+4]; sz=struct.unpack(e+'I',b[o+4:o+8])[0]
        out.append((m.decode('latin1'),o,sz,b[o:o+sz])); o+=sz
    return e,hl,ver,fs,out,o
if __name__=='__main__':
    for p in sys.argv[1:]:
        b=open(p,'rb').read(); e,hl,ver,fs,out,end=secs(b)
        print(p,b[:4],e,'hdr',hl,'ver',hex(ver),'fsize',fs,len(b),'end',end,'nsec',len(out))
        for m,o,sz,d in out: print('   ',m,o,sz,hashlib.md5(d).hexdigest()[:8])
