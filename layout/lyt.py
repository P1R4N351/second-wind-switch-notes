"""BFLYT / BFLAN helpers: section walking, pai1 BE->LE conversion, semantic normalisers."""
import struct
def secs(b):
    assert b[:4] in (b'FLYT',b'FLAN')
    e='>' if b[4:6]==b'\xfe\xff' else '<'
    assert b[4:6] in (b'\xfe\xff',b'\xff\xfe')
    hl,ver,fs,n=struct.unpack(e+'HIIH',b[6:18])
    assert hl==20 and fs==len(b),(hl,fs,len(b))
    out=[];o=hl
    for i in range(n):
        sz=struct.unpack(e+'I',b[o+4:o+8])[0]; assert sz>=8 and sz%4==0 and o+sz<=len(b),(i,o,sz)
        out.append((b[o:o+4].decode('latin1'),b[o:o+sz])); o+=sz
    assert o==len(b),(o,len(b))
    return e,ver,out
def build(magic,ver,sections):
    body=b''.join(sections)
    return magic+b'\xff\xfe'+struct.pack('<HIIHH',20,ver,20+len(body),len(sections),0)+body
def cstr(b,o): return b[o:b.index(b'\0',o)].decode('latin1')
PANES=('pan1','pic1','txt1','wnd1','prt1','bnd1','scr1','ali1','cpt1')
def pane_name(d): return d[12:36].split(b'\0')[0].decode()
def pane_base(d,e):
    f=struct.unpack(e+'10f',d[44:84])
    return dict(flags=d[8],origin=d[9],alpha=d[10],mag=d[11],name=pane_name(d),user=d[36:44],T=f[0:3],R=f[3:6],S=f[6:8],size=f[8:10])
# ---- pai1 (animation data) big-endian v5 -> little-endian (layout identical in v8) ----
def pai1_be2le(d):
    o=bytearray(d)
    def sw(off,fmt):
        v=struct.unpack_from('>'+fmt,d,off); struct.pack_into('<'+fmt,o,off,*v); return v
    assert d[:4]==b'pai1'
    size,frames,loop,pad,ntex,nent,eoo=sw(4,'IHBBHHI')
    assert size==len(d)
    if ntex:
        offs=sw(0x14,'%dI'%ntex)
    eo=sw(eoo,'%dI'%nent)
    for e in eo:
        ntags=d[e+28]; etype=d[e+29]
        to=sw(e+32,'%dI'%ntags)
        for t in to:
            t+=e; magic=d[t:t+4]; assert magic[:2]==b'FL',magic
            ntar=d[t+4]
            if magic==b'FLEU': raise NotImplementedError('FLEU')
            ta=sw(t+8,'%dI'%ntar)
            for a in ta:
                a+=t; idx,target,ctype,p=d[a:a+4]
                nk,p2,ko=sw(a+4,'HHI')
                k=a+ko
                for i in range(nk):
                    if ctype==2: sw(k+12*i,'fff')
                    elif ctype==1: sw(k+8*i,'fHH')
                    elif ctype==0: sw(k+8*i,'ff')
                    else: raise NotImplementedError('curve %d'%ctype)
    return bytes(o)
def pai1_dump(d,e):
    """semantic dump (for reports): list of (pane, type, tag, index, target, curve, keys)"""
    size,frames,loop,pad,ntex,nent,eoo=struct.unpack_from(e+'IHBBHHI',d,4)
    out=[('frames',frames,'loop',loop,'ntex',ntex)]
    for en in struct.unpack_from(e+'%dI'%nent,d,eoo):
        nm=cstr(d,en); ntags=d[en+28]
        for t in struct.unpack_from(e+'%dI'%ntags,d,en+32):
            t+=en
            for a in struct.unpack_from(e+'%dI'%d[t+4],d,t+8):
                a+=t; nk,p2,ko=struct.unpack_from(e+'HHI',d,a+4); ct=d[a+2]
                keys=[struct.unpack_from(e+{2:'fff',1:'fHH',0:'ff'}[ct],d,a+ko+{2:12,1:8,0:8}[ct]*i) for i in range(nk)]
                out.append((nm,d[en+29],d[t:t+4].decode(),d[a],d[a+1],ct,keys))
    return out
# ---- semantic normalisers for v5 big-endian sections (used to tell editor re-serialisation noise from real edits) ----
def norm_usd1(d,e='>'):
    n,=struct.unpack_from(e+'H',d,8); out=[]
    for i in range(n):
        b=12+12*i
        no,do,cnt,typ,p=struct.unpack_from(e+'IIHBB',d,b)
        name=cstr(d,b+no)
        if typ==0: val=d[b+do:b+do+cnt]
        elif typ==1: val=struct.unpack_from(e+'%di'%cnt,d,b+do)
        elif typ==2: val=struct.unpack_from(e+'%df'%cnt,d,b+do)
        else: raise NotImplementedError('usd type %d'%typ)
        out.append((name,typ,val))
    return out
def norm_txt1(d,e='>'):
    base=d[8:84]
    tl,tml,mat,font,al_,la,fl,pd=struct.unpack_from(e+'HHHHBBBB',d,84)
    ital,toff=struct.unpack_from(e+'fI',d,96)
    cols=d[104:112]; fl2=struct.unpack_from(e+'4f',d,112)
    noff,=struct.unpack_from(e+'I',d,128)
    sh=d[132:160]
    text=d[toff:toff+tl] if toff else b''
    name=cstr(d,noff) if noff else None
    # anything between 160 and the text that is not all-zero is flagged
    return ('txt1',base,tl,tml,mat,font,al_,la,fl,pd,ital,cols,fl2,sh,text,name)
def norm_any(m,d,e='>'):
    if m=='usd1': return norm_usd1(d,e)
    if m=='txt1': return norm_txt1(d,e)
    if m=='prt1': return norm_prt1(d,e)
    return d
def norm_prt1(d,e='>'):
    base=d[8:84]
    cnt,mx,my=struct.unpack_from(e+'Iff',d,84)
    props=[]
    for i in range(cnt):
        b=96+40*i
        name=d[b:b+24].split(b'\0')[0].decode(); flags=d[b+24:b+28]
        po,uo,io=struct.unpack_from(e+'III',d,b+28)
        def sub(o):
            if not o: return None
            sz,=struct.unpack_from(e+'I',d,o+4); mg=d[o:o+4].decode('latin1')
            return (mg,norm_any(mg,d[o:o+sz],e))
        props.append((name,flags,sub(po),sub(uo),d[io:io+52] if io else None))
    lname=cstr(d,96+40*cnt)
    return ('prt1',base,cnt,mx,my,props,lname)
