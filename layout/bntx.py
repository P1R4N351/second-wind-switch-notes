"""Minimal BNTX (Switch, v0.4) parser / rebuilder. Round-trips stock files byte-exactly."""
import struct
def al(x,a): return (x+a-1)//a*a
class Tex: pass
class Bntx: pass
def parse(b):
    assert b[:4]==b'BNTX' and b[12:14]==b'\xff\xfe'
    B=Bntx(); B.raw_hdr=b[:0x20]
    B.ver,=struct.unpack_from('<I',b,8); B.align=b[14]; B.addr=b[15]
    fn,flag,blk,rlt,fsz=struct.unpack_from('<IHHII',b,0x10)
    assert fsz==len(b)
    B.flag=flag
    assert b[0x20:0x24]==b'NX  '
    n,info,datablk,dic,mempool,cur,base=struct.unpack_from('<IqqqqqI',b,0x24)
    assert mempool==0x58 and info==0x198, (mempool,info)
    assert b[0x58:0x198]==bytes(0x140)
    B.target=b[0x20:0x24]
    ptrs=struct.unpack_from('<%dq'%n,b,info)
    stro=al(info+8*n,8); assert b[stro:stro+4]==b'_STR' and blk==stro,(stro,blk)
    nxt,ssz,scnt=struct.unpack_from('<IqI',b,stro+4)
    # strings
    o=stro+0x14; strs=[]; pos={}
    for i in range(scnt+1):
        l,=struct.unpack_from('<H',b,o); s=b[o+2:o+2+l].decode(); assert b[o+2+l]==0
        pos[o]=s
        if i: strs.append(s)
        else: assert l==0
        o=al(o+2+l+1,2)
    B.strs=strs
    assert al(o,8)==dic and b[dic:dic+4]==b'_DIC'
    assert pos[fn-2]; B.name=pos[fn-2]
    dn,=struct.unpack_from('<I',b,dic+4); assert dn==n
    B.dic_raw=b[dic:dic+8+16*(n+1)]
    assert stro+nxt==dic+8+16*(n+1)==ptrs[0] and ssz==nxt
    B.tex=[]
    for i,p in enumerate(ptrs):
        assert b[p:p+4]==b'BRTI'
        t=Tex(); nx,bs=struct.unpack_from('<Iq',b,p+4)
        t.hdr=bytearray(b[p+0x10:p+0x60])   # flags..dim  (0x50 bytes)
        (t.flags,t.dim,t.tile,t.swz,t.mips,t.samples,_r,t.fmt,t.access,t.w,t.h,t.d,t.arr,t.layout,t.layout2)=struct.unpack_from('<BBHHHHHIIiiiiII',b,p+0x10)
        t.size,t.talign,t.compsel,t.ttype=struct.unpack_from('<IIII',b,p+0x50)
        nm,par,mp,ud,tp,tvp,ds,udd=struct.unpack_from('<8q',b,p+0x60)
        t.name=pos[nm]; assert par==0x20 and ud==0 and ds==0 and udd==0 and tp==p+0xa0 and tvp==p+0x1a0 and mp==p+0x2a0
        assert b[p+0xa0:p+0x2a0]==bytes(0x200)
        assert bs==nx and (bs==0x2a0+8*t.mips or (i==n-1 and p+bs==datablk)), (bs,nx,t.mips)
        t.mipoffs=list(struct.unpack_from('<%dq'%t.mips,b,mp))
        t.data=b[t.mipoffs[0]:t.mipoffs[0]+t.size]
        t.rel=[m-t.mipoffs[0] for m in t.mipoffs]
        t.off=t.mipoffs[0]; t.brti=p; t.nx=nx
        B.tex.append(t)
    assert b[datablk:datablk+4]==b'BRTD'
    B.datablk=datablk; B.rlt=rlt
    dsz,=struct.unpack_from('<q',b,datablk+8); assert datablk+dsz==rlt
    B.rlt_raw=b[rlt:]
    return B
def dict_gen(names):
    # Nintendo ResDic patricia trie (same algorithm as BFRES v8+/BNTX)
    def bit(s,i):
        by=i>>3
        if by>=len(s): return 0
        return (s[len(s)-1-by]>>(i&7))&1
    def fdb(a,b):
        ln=max(len(a),len(b))
        for i in range(ln*8):
            if bit(a,i)!=bit(b,i): return i
        return -1
    class N: pass
    root=N(); root.ref=-1; root.key=b''; root.ch=[root,root]
    nodes=[root]
    for nm in names:
        k=nm.encode()
        # search
        prev=root; cur=root.ch[0]
        while prev.ref<cur.ref:
            prev=cur; cur=cur.ch[bit(k,cur.ref)]
        d=fdb(k,cur.key); assert d>=0,'dup key '+nm
        prev=root; cur=root.ch[0]
        while prev.ref<cur.ref and cur.ref<d:
            prev=cur; cur=cur.ch[bit(k,cur.ref)]
        n=N(); n.ref=d; n.key=k
        n.ch=[None,None]; n.ch[bit(k,d)]=n; n.ch[1-bit(k,d)]=cur
        if prev is root: root.ch[0]=n
        else: prev.ch[bit(k,prev.ref)]=n
        nodes.append(n)
    idx={id(n):i for i,n in enumerate(nodes)}
    return [(n.ref&0xffffffff, idx[id(n.ch[0])], idx[id(n.ch[1])]) for n in nodes]
def rlt_entries(ptrs):
    ptrs=sorted(ptrs); runs=[]
    for p in ptrs:
        if runs and runs[-1][0]+8*runs[-1][1]==p and runs[-1][1]<255: runs[-1][1]+=1
        else: runs.append([p,1])
    used=[False]*len(runs); out=[]
    for i,(p,l) in enumerate(runs):
        if used[i]: continue
        used[i]=True; cnt=1; pad=None; last=p; j=i+1
        while True:
            while j<len(runs) and (used[j] or runs[j][1]!=l): j+=1
            if j>=len(runs): break
            gap=runs[j][0]-(last+8*l)
            g=gap//8
            if g>255 or (pad is not None and g!=pad) or cnt>=0xffff: break
            pad=g; used[j]=True; cnt+=1; last=runs[j][0]; j+=1
        out.append((p,cnt,l,pad or 0))
    return out
def rlt_expand(raw):
    nsec,=struct.unpack_from('<I',raw,8); res=[]
    for s in range(nsec):
        ptr,pos,size,idx,cnt=struct.unpack_from('<qIIII',raw,0x10+s*0x18)
        st=set()
        for e in range(idx,idx+cnt):
            p,sc,oc,pc=struct.unpack_from('<IHBB',raw,0x10+nsec*0x18+e*8)
            for k in range(sc):
                for m in range(oc): st.add(p); p+=8
                p+=8*pc
        res.append((pos,size,st))
    return res
def build(B):
    n=len(B.tex); info=0x198
    stro=al(info+8*n,8)
    # strings
    sb=bytearray(struct.pack('<I',len(B.strs))+b'\0\0\0\0'); spos={'':stro+0x14}
    for s in B.strs:
        spos[s]=stro+0x10+len(sb); e=s.encode(); sb+=struct.pack('<H',len(e))+e+b'\0'
        if len(sb)%2: sb+=b'\0'
    dic=al(stro+0x10+len(sb),8)
    names=[t.name for t in B.tex]
    dg=dict_gen(names)
    db=bytearray(b'_DIC'+struct.pack('<I',n))
    keys=['']+names
    for (ref,l,r),k in zip(dg,keys): db+=struct.pack('<IHHq',ref,l,r,spos[k])
    brti0=dic+len(db)
    # BRTI positions
    pos=[];o=brti0
    for t in B.tex: pos.append(o); o+=0x2a0+8*len(t.rel)
    datablk=al(o+0x10,1<<B.align)-0x10
    # data
    d=datablk+0x10; offs=[]
    for t in B.tex:
        d=al(d,t.talign); offs.append(d); d+=len(t.data)
    rlt=al(d,1<<B.align)
    out=bytearray(rlt)
    out[0x20:0x58]=B.target+struct.pack('<Iqqqqqq',n,info,datablk,dic,0x58,0,0)
    p0=[];p1=[0x30]
    p0+=[0x28,0x38,0x40]
    for i,p in enumerate(pos): struct.pack_into('<q',out,info+8*i,p); p0.append(info+8*i)
    out[stro:stro+0x10]=b'_STR'+struct.pack('<Iq',brti0-stro,brti0-stro)
    out[stro+0x10:stro+0x10+len(sb)]=sb
    out[dic:dic+len(db)]=db
    for i in range(n+1): p0.append(dic+8+16*i+8)
    for i,(t,p) in enumerate(zip(B.tex,pos)):
        bs=0x2a0+8*len(t.rel)
        nx=bs if i<n-1 else datablk-p
        out[p:p+0x10]=b'BRTI'+struct.pack('<Iq',nx,nx)
        out[p+0x10:p+0x60]=t.hdr
        struct.pack_into('<8q',out,p+0x60,spos[t.name],0x20,p+0x2a0,0,p+0xa0,p+0x1a0,0,0)
        p0+=[p+0x60,p+0x68,p+0x70,p+0x80,p+0x88]
        for k,r in enumerate(t.rel): struct.pack_into('<q',out,p+0x2a0+8*k,offs[i]+r); p1.append(p+0x2a0+8*k)
        out[offs[i]:offs[i]+len(t.data)]=t.data
    out[datablk:datablk+0x10]=b'BRTD'+struct.pack('<Iq',0,rlt-datablk)
    e0=rlt_entries(p0); e1=rlt_entries(p1)
    r=bytearray(b'_RLT'+struct.pack('<III',rlt,2,0))
    r+=struct.pack('<qIIII',0,0,o,0,len(e0))+struct.pack('<qIIII',0,datablk,rlt-datablk,len(e0),len(e1))
    for e in e0+e1: r+=struct.pack('<IHBB',*e)
    out+=r
    out[0:0x20]=b'BNTX'+struct.pack('<IIHBBIHHII',0,B.ver,0xfeff,B.align,B.addr,spos[B.name]+2,B.flag,stro,rlt,len(out))
    return bytes(out)
FMT={0x02:'R8',0x07:'B5G6R5',0x09:'R8G8',0x0b:'RGBA8',0x0c:'BGRA8',0x1a:'BC1',0x1b:'BC2',0x1c:'BC3',0x1d:'BC4',0x1e:'BC5',0x1f:'BC6H',0x20:'BC7',0x2d:'ASTC4x4'}
def fmtname(f): return FMT.get(f>>8,hex(f>>8))+{1:'_UNORM',2:'_SNORM',6:'_SRGB'}.get(f&0xff,'_%x'%(f&0xff))
if __name__=='__main__':
    import sys
    for p in sys.argv[1:]:
        b=open(p,'rb').read(); B=parse(b)
        print(p,len(b),'ntex',len(B.tex),'name',B.name,'align',B.align,'nstr',len(B.strs))
        o=build(B); print('  roundtrip identical:',o==b, len(o))
        if o!=b:
            df=[i for i in range(min(len(o),len(b))) if o[i]!=b[i]]; print('  first diffs',[hex(x) for x in df[:20]],len(df), hex(B.rlt))
        from collections import Counter
        print('  formats',Counter(fmtname(t.fmt) for t in B.tex), 'mips',Counter(t.mips for t in B.tex),'talign',Counter(t.talign for t in B.tex),'lay2',Counter(hex(t.layout2) for t in B.tex),'flags',Counter((t.flags,t.dim,t.tile,t.swz,t.samples,t.access,t.d,t.arr,t.ttype) for t in B.tex))
        print('  str order == tex order?', B.strs[:6], [t.name for t in B.tex[:4]])
